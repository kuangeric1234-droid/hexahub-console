"""
Main API router — aggregates all sub-routers under /api/v1.
"""
from fastapi import APIRouter

from backend.api.routes.auth       import router as auth_router
from backend.api.routes.campaigns  import router as campaigns_router
from backend.api.routes.posts      import router as posts_router
from backend.api.routes.approvals  import router as approvals_router
from backend.api.routes.compliance import router as compliance_router
from backend.api.routes.ad_creative import router as ad_creative_router
from backend.api.routes.assets     import router as assets_router
from backend.api.routes.brand      import router as brand_router
from backend.api.routes.logs       import router as logs_router
from backend.api.routes.webhooks   import router as webhooks_router
from backend.api.routes.create      import router as create_router
from backend.api.routes.social_auth import router as social_router
from backend.api.routes.ads_meta    import router as ads_meta_router
from backend.api.routes.drive      import router as drive_router

# Repurpose endpoint from the existing tools module (preserved)
from backend.api.tools import router as tools_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(campaigns_router)
api_router.include_router(posts_router)
api_router.include_router(approvals_router)
api_router.include_router(compliance_router)
api_router.include_router(ad_creative_router)
api_router.include_router(assets_router)
api_router.include_router(brand_router)
api_router.include_router(logs_router)
api_router.include_router(webhooks_router)
api_router.include_router(create_router)
api_router.include_router(social_router)
api_router.include_router(ads_meta_router)
api_router.include_router(tools_router)   # /repurpose endpoint
api_router.include_router(drive_router)
