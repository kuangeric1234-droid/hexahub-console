"""
MetaAdsService — wraps the Meta Marketing API v21.0.

Token resolution order (mirrors the scheduler's _load_meta_creds pattern):
  1. social_connections table (provider = "meta") → page_access_token
  2. META_ACCESS_TOKEN env var fallback

All campaigns are created with status PAUSED.  Activate only on explicit
user action via resume_campaign().

Daily budget is accepted in AUD and converted to cents for the API.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.models import SocialConnection

log = structlog.get_logger()

_GRAPH = "https://graph.facebook.com/v21.0"


# ── Data classes returned from service methods ─────────────────────────────────

@dataclass
class CreatedCampaign:
    meta_campaign_id: str


@dataclass
class CreatedAdSet:
    meta_adset_id: str


@dataclass
class CreatedAd:
    meta_ad_id: str


@dataclass
class CampaignInsights:
    meta_campaign_id: str
    reach:            int
    impressions:      int
    clicks:           int
    ctr:              float   # percentage
    spend_aud:        float
    leads:            int
    cpl_aud:          float   # cost per lead


# ── Service ───────────────────────────────────────────────────────────────────

class MetaAdsService:
    """
    Thin async wrapper around the Meta Marketing API.
    Instantiate via from_db() to auto-resolve the stored access token.
    """

    def __init__(self, access_token: str, ad_account_id: str) -> None:
        self._token      = access_token
        self._account_id = ad_account_id  # e.g. "act_123456789"

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    async def from_db(cls, db: AsyncSession) -> "MetaAdsService":
        """
        Build a MetaAdsService from DB-stored OAuth credentials.
        Falls back to META_ACCESS_TOKEN env var (same pattern as scheduler).
        Raises ValueError if neither source is available.
        """
        result = await db.execute(
            select(SocialConnection).where(SocialConnection.provider == "meta")
        )
        conn = result.scalar_one_or_none()

        token = (conn.page_access_token if conn else None) or settings.META_ACCESS_TOKEN
        if not token:
            raise ValueError(
                "Meta not connected — visit /publish/integrations to connect your Facebook account."
            )

        account_id = settings.META_AD_ACCOUNT_ID
        if not account_id:
            raise ValueError(
                "META_AD_ACCOUNT_ID not configured — add it to backend/.env (format: act_XXXXXXXXXX)."
            )

        return cls(access_token=token, ad_account_id=account_id)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _params(self, extra: dict | None = None) -> dict:
        base = {"access_token": self._token}
        if extra:
            base.update(extra)
        return base

    async def _post(self, path: str, data: dict, client: httpx.AsyncClient) -> dict:
        resp = await client.post(f"{_GRAPH}{path}", data={**data, "access_token": self._token})
        body = resp.json()
        if resp.status_code not in (200, 201) or "error" in body:
            err = body.get("error", {}).get("message", resp.text)
            raise RuntimeError(f"Meta API error on POST {path}: {err}")
        return body

    async def _patch(self, path: str, data: dict, client: httpx.AsyncClient) -> dict:
        resp = await client.post(f"{_GRAPH}{path}", data={**data, "access_token": self._token})
        body = resp.json()
        if "error" in body:
            err = body.get("error", {}).get("message", resp.text)
            raise RuntimeError(f"Meta API error on PATCH {path}: {err}")
        return body

    async def _get(self, path: str, params: dict, client: httpx.AsyncClient) -> dict:
        resp = await client.get(f"{_GRAPH}{path}", params={**params, "access_token": self._token})
        body = resp.json()
        if resp.status_code != 200 or "error" in body:
            err = body.get("error", {}).get("message", resp.text)
            raise RuntimeError(f"Meta API error on GET {path}: {err}")
        return body

    # ── Campaign CRUD ─────────────────────────────────────────────────────────

    async def create_campaign(
        self,
        name:      str,
        objective: str = "OUTCOME_LEADS",
    ) -> CreatedCampaign:
        """
        Create a Meta Ads campaign in PAUSED state.
        Returns the Meta campaign ID.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            body = await self._post(
                f"/{self._account_id}/campaigns",
                {
                    "name":                  name,
                    "objective":             objective,
                    "status":                "PAUSED",
                    "special_ad_categories": "[]",
                },
                client,
            )
        meta_id = body.get("id")
        log.info("meta_campaign_created", meta_campaign_id=meta_id, name=name)
        return CreatedCampaign(meta_campaign_id=meta_id)

    async def create_adset(
        self,
        name:             str,
        meta_campaign_id: str,
        daily_budget_aud: float,
        targeting_location: str = "AU",
        targeting_interests: str = "",
    ) -> CreatedAdSet:
        """
        Create an ad set under a campaign, PAUSED, optimised for leads.
        daily_budget_aud: AUD dollars (e.g. 50.0 → 5000 cents sent to API).
        targeting_location: ISO country code or comma-separated codes.
        """
        daily_budget_cents = int(daily_budget_aud * 100)
        countries          = [c.strip().upper() for c in targeting_location.split(",") if c.strip()]
        if not countries:
            countries = ["AU"]

        targeting = {
            "geo_locations": {"countries": countries},
            "age_min": 18,
            "age_max": 65,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            body = await self._post(
                f"/{self._account_id}/adsets",
                {
                    "name":              name,
                    "campaign_id":       meta_campaign_id,
                    "daily_budget":      str(daily_budget_cents),
                    "billing_event":     "IMPRESSIONS",
                    "optimization_goal": "LEAD_GENERATION",
                    "bid_strategy":      "LOWEST_COST_WITHOUT_CAP",
                    "targeting":         str(targeting).replace("'", '"'),
                    "status":            "PAUSED",
                },
                client,
            )
        meta_id = body.get("id")
        log.info("meta_adset_created", meta_adset_id=meta_id)
        return CreatedAdSet(meta_adset_id=meta_id)

    async def create_ad(
        self,
        name:            str,
        meta_adset_id:   str,
        meta_creative_id: str,
    ) -> CreatedAd:
        """
        Create an ad using a pre-built creative ID, PAUSED.
        The creative must already exist in the Meta Ads account.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            body = await self._post(
                f"/{self._account_id}/ads",
                {
                    "name":     name,
                    "adset_id": meta_adset_id,
                    "creative": f'{{"creative_id": "{meta_creative_id}"}}',
                    "status":   "PAUSED",
                },
                client,
            )
        meta_id = body.get("id")
        log.info("meta_ad_created", meta_ad_id=meta_id)
        return CreatedAd(meta_ad_id=meta_id)

    async def pause_campaign(self, meta_campaign_id: str) -> bool:
        async with httpx.AsyncClient(timeout=15) as client:
            await self._patch(f"/{meta_campaign_id}", {"status": "PAUSED"}, client)
        log.info("meta_campaign_paused", meta_campaign_id=meta_campaign_id)
        return True

    async def resume_campaign(self, meta_campaign_id: str) -> bool:
        async with httpx.AsyncClient(timeout=15) as client:
            await self._patch(f"/{meta_campaign_id}", {"status": "ACTIVE"}, client)
        log.info("meta_campaign_resumed", meta_campaign_id=meta_campaign_id)
        return True

    # ── Insights ──────────────────────────────────────────────────────────────

    async def get_insights(
        self,
        meta_campaign_id: str,
        date_preset: str = "last_30d",
    ) -> CampaignInsights:
        """
        Fetch campaign performance from the Insights API.
        Returns a CampaignInsights dataclass with spend in AUD.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            body = await self._get(
                f"/{meta_campaign_id}/insights",
                {
                    "fields":      "reach,impressions,clicks,ctr,spend,actions",
                    "date_preset": date_preset,
                },
                client,
            )

        data = (body.get("data") or [{}])[0]

        reach       = int(data.get("reach", 0) or 0)
        impressions = int(data.get("impressions", 0) or 0)
        clicks      = int(data.get("clicks", 0) or 0)
        ctr         = float(data.get("ctr", 0) or 0)
        spend_aud   = float(data.get("spend", 0) or 0)

        # Extract lead actions (action_type = "lead" or "onsite_conversion.lead_grouped")
        leads = 0
        for action in data.get("actions") or []:
            if action.get("action_type") in ("lead", "onsite_conversion.lead_grouped"):
                leads += int(action.get("value", 0))

        cpl_aud = round(spend_aud / leads, 2) if leads > 0 else 0.0

        return CampaignInsights(
            meta_campaign_id=meta_campaign_id,
            reach=reach,
            impressions=impressions,
            clicks=clicks,
            ctr=ctr,
            spend_aud=spend_aud,
            leads=leads,
            cpl_aud=cpl_aud,
        )


# ── Standalone sync task (called by APScheduler and the /sync endpoint) ───────

async def sync_all_ad_metrics() -> int:
    """
    Sync insights for every active/paused AdCampaign row into the metrics table.
    Returns the number of campaigns synced.
    Called daily by APScheduler and on-demand via POST /ads/meta/campaigns/{id}/sync.
    """
    from backend.db.database import AsyncSessionLocal
    from backend.db.models import AdCampaign, Metric, Platform, Post

    async with AsyncSessionLocal() as db:
        try:
            svc = await MetaAdsService.from_db(db)
        except ValueError as exc:
            log.warning("meta_ads_sync_skipped", reason=str(exc))
            return 0

        result  = await db.execute(select(AdCampaign))
        ad_rows = result.scalars().all()

        synced = 0
        for ad in ad_rows:
            try:
                insights = await svc.get_insights(ad.meta_campaign_id)

                # Write into the metrics table — find or create a synthetic post row
                # (we use a placeholder post linked to the same campaign)
                from sqlalchemy import select as _sel
                existing = await db.execute(
                    _sel(Metric).where(
                        Metric.post_id == ad.id  # type: ignore[arg-type]  # reused as ad ref
                    )
                )
                # For ad metrics we store at the AdCampaign level using campaign_id as post ref
                # Find any post in this campaign to attach metrics to, or skip if none
                if ad.campaign_id:
                    post_q = await db.execute(
                        _sel(Post).where(Post.campaign_id == ad.campaign_id).limit(1)
                    )
                    post = post_q.scalar_one_or_none()
                    if post:
                        metric = Metric(
                            post_id    = post.id,
                            platform   = Platform.facebook,
                            reach      = insights.reach,
                            engagement = insights.clicks,
                            ctr        = insights.ctr,
                            conversions= insights.leads,
                            fetched_at = datetime.now(timezone.utc),
                        )
                        db.add(metric)

                ad.synced_at = datetime.now(timezone.utc)
                ad.status    = await _fetch_campaign_status(svc, ad.meta_campaign_id)
                synced += 1

            except Exception as exc:
                log.error("meta_ads_sync_failed", meta_campaign_id=ad.meta_campaign_id, error=str(exc))

        await db.commit()
        log.info("meta_ads_sync_complete", synced=synced)
        return synced


async def _fetch_campaign_status(svc: MetaAdsService, meta_campaign_id: str) -> str:
    """Pull current status string from Meta for a campaign."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            body = await svc._get(
                f"/{meta_campaign_id}",
                {"fields": "status"},
                client,
            )
        return body.get("status", "UNKNOWN")
    except Exception:
        return "UNKNOWN"
