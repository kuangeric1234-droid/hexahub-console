"""
Google Drive asset browser.

GET  /drive/files          list files/folders in a Drive folder
POST /drive/import         download a Drive file → upload to MinIO → create Asset record
"""
from __future__ import annotations

import uuid
from typing import Optional

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.api.schemas.asset import AssetResponse
from backend.config import settings
from backend.db.models import Asset, AssetType, User

log    = structlog.get_logger()
router = APIRouter(prefix="/drive", tags=["drive"])

_DRIVE_API = "https://www.googleapis.com/drive/v3"
_FILE_FIELDS = "id,name,mimeType,size,modifiedTime,thumbnailLink"
_LIST_FIELDS = f"nextPageToken,files({_FILE_FIELDS})"


# ── Response models ────────────────────────────────────────────────────────────

class DriveFile(BaseModel):
    id:            str
    name:          str
    mimeType:      str
    size:          Optional[int]   = None
    modifiedTime:  Optional[str]   = None
    thumbnailLink: Optional[str]   = None
    is_folder:     bool            = False
    thumbnail_url: Optional[str]   = None  # constructed public thumbnail


class DriveFilesResponse(BaseModel):
    files:          list[DriveFile]
    next_page_token: Optional[str] = None
    folder_id:      str


class DriveImportRequest(BaseModel):
    file_id:   str
    file_name: str
    mime_type: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_drive_config() -> None:
    if not settings.GOOGLE_DRIVE_API_KEY:
        raise HTTPException(503, "GOOGLE_DRIVE_API_KEY not configured in backend/.env")
    if not settings.GOOGLE_DRIVE_FOLDER_ID:
        raise HTTPException(503, "GOOGLE_DRIVE_FOLDER_ID not configured in backend/.env")


def _public_thumbnail(file_id: str, mime_type: str) -> str:
    """Public thumbnail URL that works for files in a public Google Drive folder."""
    if mime_type.startswith("video/"):
        return f"https://drive.google.com/thumbnail?id={file_id}&sz=w320"
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w320"


def _s3_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_ENDPOINT_URL or None,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def _content_type_to_asset_type(mime: str) -> AssetType:
    if mime.startswith("image/"): return AssetType.image
    if mime.startswith("video/"): return AssetType.video
    return AssetType.document


# ── GET /drive/files ──────────────────────────────────────────────────────────

@router.get("/files", response_model=DriveFilesResponse, summary="Browse Google Drive folder")
async def list_drive_files(
    folder_id:  Optional[str] = Query(default=None, description="Subfolder ID; defaults to root folder"),
    page_token: Optional[str] = Query(default=None),
    type:       Optional[str] = Query(default=None, description="Filter: image | video | folder | all"),
    search:     Optional[str] = Query(default=None),
    page_size:  int           = Query(default=50, ge=1, le=100),
    _:          User          = Depends(get_current_user),
) -> DriveFilesResponse:
    _require_drive_config()

    target_folder = folder_id or settings.GOOGLE_DRIVE_FOLDER_ID

    # Build query
    q_parts = [f"'{target_folder}' in parents", "trashed = false"]
    if type == "image":
        q_parts.append("mimeType contains 'image/'")
    elif type == "video":
        q_parts.append("mimeType contains 'video/'")
    elif type == "folder":
        q_parts.append("mimeType = 'application/vnd.google-apps.folder'")
    if search:
        q_parts.append(f"name contains '{search}'")

    params: dict = {
        "q":        " and ".join(q_parts),
        "key":      settings.GOOGLE_DRIVE_API_KEY,
        "fields":   _LIST_FIELDS,
        "pageSize": page_size,
        "orderBy":  "folder,name",
    }
    if page_token:
        params["pageToken"] = page_token

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{_DRIVE_API}/files", params=params)

    if resp.status_code != 200:
        log.error("drive_list_failed", status=resp.status_code, body=resp.text)
        raise HTTPException(502, f"Google Drive API error: {resp.text}")

    data  = resp.json()
    files = []
    for f in data.get("files", []):
        is_folder = f["mimeType"] == "application/vnd.google-apps.folder"
        files.append(DriveFile(
            id           = f["id"],
            name         = f["name"],
            mimeType     = f["mimeType"],
            size         = int(f["size"]) if f.get("size") else None,
            modifiedTime = f.get("modifiedTime"),
            thumbnailLink= f.get("thumbnailLink"),
            is_folder    = is_folder,
            thumbnail_url= None if is_folder else _public_thumbnail(f["id"], f["mimeType"]),
        ))

    return DriveFilesResponse(
        files=files,
        next_page_token=data.get("nextPageToken"),
        folder_id=target_folder,
    )


# ── POST /drive/import ────────────────────────────────────────────────────────

@router.post("/import", response_model=AssetResponse, summary="Import Drive file to asset library")
async def import_drive_file(
    body: DriveImportRequest,
    db:   AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AssetResponse:
    _require_drive_config()

    # Stream file from Google Drive
    download_url = f"{_DRIVE_API}/files/{body.file_id}"
    params = {"alt": "media", "key": settings.GOOGLE_DRIVE_API_KEY}

    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        resp = await client.get(download_url, params=params)
        if resp.status_code != 200:
            raise HTTPException(502, f"Could not download from Drive: {resp.text[:200]}")
        content = resp.content

    if len(content) > 100 * 1024 * 1024:  # 100 MB cap
        raise HTTPException(413, "File exceeds 100 MB import limit")

    # Upload to MinIO
    asset_id = uuid.uuid4()
    ext      = body.file_name.rsplit(".", 1)[-1] if "." in body.file_name else "bin"
    key      = f"assets/{asset_id}.{ext}"

    try:
        s3 = _s3_client()
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=content,
            ContentType=body.mime_type,
        )
        url = f"{settings.PUBLIC_BACKEND_URL}/images/{key}"
    except Exception as exc:
        log.warning("drive_import_s3_failed", error=str(exc))
        raise HTTPException(502, f"Storage upload failed: {exc}")

    asset = Asset(
        id   = asset_id,
        type = _content_type_to_asset_type(body.mime_type),
        url  = url,
        name = body.file_name,
        tags = ["google-drive"],
    )
    db.add(asset)
    await db.flush()

    log.info("drive_imported", asset_id=str(asset_id), name=body.file_name, by=current_user.email)
    return AssetResponse.model_validate(asset)
