"""
Asset routes.

POST /assets/upload     multipart upload → S3/MinIO + DB row
GET  /assets            list with filters
GET  /assets/{id}       detail
PATCH /assets/{id}      update tags/name
DELETE /assets/{id}     delete from storage + DB
"""
from __future__ import annotations

import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user, get_db
from backend.api.schemas.asset import AssetResponse, AssetUpdate
from backend.config import settings
from backend.db.models import Asset, AssetType, User

log    = structlog.get_logger()
router = APIRouter(prefix="/assets", tags=["assets"])

ALLOWED_TYPES   = {"image/jpeg", "image/png", "image/webp", "image/gif",
                   "video/mp4", "video/quicktime", "application/pdf"}
MAX_UPLOAD_MB   = 50
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def _s3_client():
    """Return a boto3 S3 client configured for MinIO/S3."""
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=settings.AWS_ENDPOINT_URL or None,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def _content_type_to_asset_type(content_type: str) -> AssetType:
    if content_type.startswith("image/"): return AssetType.image
    if content_type.startswith("video/"): return AssetType.video
    return AssetType.document


# ── POST /assets/upload ────────────────────────────────────────────────────────

@router.post("/upload", response_model=AssetResponse, status_code=status.HTTP_201_CREATED,
             summary="Upload asset to storage")
async def upload_asset(
    file:    UploadFile              = File(...),
    name:    Optional[str]           = Form(default=None),
    tags:    str                     = Form(default=""),   # comma-separated
    db:      AsyncSession            = Depends(get_db),
    current_user: User               = Depends(get_current_user),
) -> AssetResponse:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(415, f"File type '{file.content_type}' not allowed")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_MB} MB limit")

    asset_id = uuid.uuid4()
    ext      = (file.filename or "file").rsplit(".", 1)[-1]
    key      = f"assets/{asset_id}.{ext}"

    try:
        s3 = _s3_client()
        s3.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=key,
            Body=content,
            ContentType=file.content_type,
        )
        url = f"{settings.AWS_ENDPOINT_URL}/{settings.S3_BUCKET_NAME}/{key}"
    except Exception as exc:
        log.warning("s3_upload_failed", error=str(exc))
        raise HTTPException(502, f"Storage upload failed: {exc}")

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    asset = Asset(
        id=asset_id,
        type=_content_type_to_asset_type(file.content_type),
        url=url,
        name=name or file.filename,
        tags=tag_list,
    )
    db.add(asset)
    await db.flush()
    log.info("asset_uploaded", asset_id=str(asset_id), by=current_user.email)
    return AssetResponse.model_validate(asset)


# ── GET /assets ────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AssetResponse], summary="List assets")
async def list_assets(
    type:     Optional[str] = Query(default=None),
    tag:      Optional[str] = Query(default=None),
    search:   Optional[str] = Query(default=None),
    page:     int            = Query(default=1, ge=1),
    page_size:int            = Query(default=20, ge=1, le=100),
    db:       AsyncSession   = Depends(get_db),
    _:        User           = Depends(get_current_user),
) -> list[AssetResponse]:
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import ARRAY
    from sqlalchemy import String

    q = select(Asset).order_by(Asset.created_at.desc()) \
        .offset((page - 1) * page_size).limit(page_size)
    if type:
        try:    q = q.where(Asset.type == AssetType(type))
        except ValueError: pass
    if tag:
        q = q.where(Asset.tags.contains([tag]))
    if search:
        q = q.where(Asset.name.ilike(f"%{search}%"))
    result = await db.execute(q)
    return [AssetResponse.model_validate(a) for a in result.scalars().all()]


# ── GET /assets/{id} ──────────────────────────────────────────────────────────

@router.get("/{asset_id}", response_model=AssetResponse, summary="Asset detail")
async def get_asset(
    asset_id: uuid.UUID,
    db:       AsyncSession = Depends(get_db),
    _:        User         = Depends(get_current_user),
) -> AssetResponse:
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, f"Asset {asset_id} not found")
    return AssetResponse.model_validate(asset)


# ── PATCH /assets/{id} ────────────────────────────────────────────────────────

@router.patch("/{asset_id}", response_model=AssetResponse, summary="Update asset metadata")
async def update_asset(
    asset_id: uuid.UUID,
    body:     AssetUpdate,
    db:       AsyncSession = Depends(get_db),
    _:        User         = Depends(get_current_user),
) -> AssetResponse:
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, f"Asset {asset_id} not found")
    if body.name is not None: asset.name = body.name
    if body.tags is not None: asset.tags = body.tags
    await db.flush()
    return AssetResponse.model_validate(asset)


# ── DELETE /assets/{id} ───────────────────────────────────────────────────────

@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT,
               response_model=None, summary="Delete asset from storage and DB")
async def delete_asset(
    asset_id: uuid.UUID,
    db:       AsyncSession = Depends(get_db),
    _:        User         = Depends(get_current_user),
) -> None:
    asset = await db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(404, f"Asset {asset_id} not found")

    # Best-effort S3 delete
    key = asset.url.split(f"/{settings.S3_BUCKET_NAME}/")[-1] if settings.S3_BUCKET_NAME in asset.url else None
    if key:
        try:
            _s3_client().delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)
        except Exception as exc:
            log.warning("s3_delete_failed", asset_id=str(asset_id), error=str(exc))

    await db.delete(asset)
    await db.flush()
