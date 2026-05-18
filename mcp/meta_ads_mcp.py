"""
Hexa Hub — Meta Ads MCP Server
================================
A Model Context Protocol server that exposes Meta Ads management tools to Claude.

All API calls go through the Hexa Hub FastAPI backend (localhost:8000),
never directly to Meta — so auth, rate limiting, and the PAUSED-by-default
safety guardrail are always enforced.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO ADD TO claude_desktop_config.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {
    "mcpServers": {
      "hexa-meta-ads": {
        "command": "python",
        "args": ["/absolute/path/to/hexa-hub-portal/mcp/meta_ads_mcp.py"],
        "env": {
          "HEXA_API_URL":   "http://localhost:8000/api/v1",
          "HEXA_API_TOKEN": "<your Bearer token from /api/v1/auth/token>"
        }
      }
    }
  }

HEXA_API_TOKEN: log in to the portal, open DevTools → Application → Local
Storage → hexa_portal_token, and paste the value here.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOOLS EXPOSED TO CLAUDE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  create_hexa_lead_campaign   — create a full paused lead gen campaign
  pause_campaign              — pause an existing campaign
  resume_campaign             — activate (un-pause) a campaign
  get_campaign_performance    — spend, leads, CPL, CTR for a campaign
  list_campaigns              — all campaigns with status + budget

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REQUIREMENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  pip install mcp httpx

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ── Configuration (from environment) ─────────────────────────────────────────

_API_URL   = os.environ.get("HEXA_API_URL",   "http://localhost:8000/api/v1")
_API_TOKEN = os.environ.get("HEXA_API_TOKEN", "")

mcp = FastMCP("Hexa Hub Meta Ads")


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    return {
        "Authorization":            f"Bearer {_API_TOKEN}",
        "Content-Type":             "application/json",
        "ngrok-skip-browser-warning": "true",
    }


async def _request(method: str, path: str, **kwargs: Any) -> dict:
    url = f"{_API_URL}{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await getattr(client, method)(url, headers=_headers(), **kwargs)
    if not resp.is_success:
        raise RuntimeError(f"Hexa API {method.upper()} {path} → {resp.status_code}: {resp.text}")
    return resp.json()


# ── Tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def create_hexa_lead_campaign(
    name:                str,
    daily_budget_aud:    float,
    targeting_location:  str = "AU",
    targeting_interests: str = "",
) -> dict:
    """
    Create a complete Meta Ads lead generation campaign (campaign + ad set).

    The campaign is created in PAUSED state — it will NOT spend money until
    you explicitly call resume_campaign().

    Args:
        name:                Campaign display name (e.g. "Hexa Hub Q3 Leads")
        daily_budget_aud:    Daily budget in Australian dollars (e.g. 50.0 for $50/day)
        targeting_location:  ISO country code(s), comma-separated (default: "AU")
        targeting_interests: Comma-separated interest keywords stored as targeting summary
    """
    payload = {
        "name":                name,
        "daily_budget_aud":    daily_budget_aud,
        "targeting_location":  targeting_location,
        "targeting_interests": targeting_interests,
    }
    result = await _request("post", "/ads/meta/campaigns", json=payload)
    return {
        "created":           True,
        "id":                result["id"],
        "meta_campaign_id":  result["meta_campaign_id"],
        "meta_adset_id":     result["meta_adset_id"],
        "status":            result["status"],
        "daily_budget_aud":  result["daily_budget_aud"],
        "targeting_summary": result["targeting_summary"],
        "message":           (
            f"Campaign '{name}' created successfully and is PAUSED. "
            f"Call resume_campaign('{result['meta_campaign_id']}') to activate it."
        ),
    }


@mcp.tool()
async def pause_campaign(meta_campaign_id: str) -> dict:
    """
    Pause a running Meta Ads campaign immediately.

    Args:
        meta_campaign_id: The Meta campaign ID (e.g. "120200000123456789")
    """
    # Find the internal AdCampaign row by meta_campaign_id
    campaigns = await _request("get", "/ads/meta/campaigns")
    match     = next((c for c in campaigns if c["meta_campaign_id"] == meta_campaign_id), None)
    if not match:
        return {"error": f"No campaign with meta_campaign_id '{meta_campaign_id}' found in Hexa Hub."}

    result = await _request("post", f"/ads/meta/campaigns/{match['id']}/pause")
    return {
        "paused":           True,
        "meta_campaign_id": meta_campaign_id,
        "status":           result["status"],
        "message":          f"Campaign {meta_campaign_id} is now PAUSED and will stop spending.",
    }


@mcp.tool()
async def resume_campaign(meta_campaign_id: str) -> dict:
    """
    Activate (un-pause) a Meta Ads campaign so it starts spending.

    Args:
        meta_campaign_id: The Meta campaign ID (e.g. "120200000123456789")
    """
    campaigns = await _request("get", "/ads/meta/campaigns")
    match     = next((c for c in campaigns if c["meta_campaign_id"] == meta_campaign_id), None)
    if not match:
        return {"error": f"No campaign with meta_campaign_id '{meta_campaign_id}' found in Hexa Hub."}

    result = await _request("post", f"/ads/meta/campaigns/{match['id']}/resume")
    return {
        "resumed":          True,
        "meta_campaign_id": meta_campaign_id,
        "status":           result["status"],
        "message":          f"Campaign {meta_campaign_id} is now ACTIVE and will begin spending up to ${match.get('daily_budget_aud', '?')}/day AUD.",
    }


@mcp.tool()
async def get_campaign_performance(
    meta_campaign_id: str,
    date_preset: str = "last_30d",
) -> dict:
    """
    Get performance metrics for a Meta Ads campaign.

    Args:
        meta_campaign_id: The Meta campaign ID
        date_preset:      Meta date preset — "last_7d", "last_30d", "last_90d",
                          "this_month", "last_month" (default: "last_30d")
    """
    campaigns = await _request("get", "/ads/meta/campaigns")
    match     = next((c for c in campaigns if c["meta_campaign_id"] == meta_campaign_id), None)
    if not match:
        return {"error": f"No campaign with meta_campaign_id '{meta_campaign_id}' found."}

    insights = await _request("get", f"/ads/meta/campaigns/{match['id']}/insights?date_preset={date_preset}")
    return {
        "meta_campaign_id": meta_campaign_id,
        "period":           date_preset,
        "reach":            insights["reach"],
        "impressions":      insights["impressions"],
        "clicks":           insights["clicks"],
        "ctr_pct":          round(insights["ctr"], 3),
        "spend_aud":        insights["spend_aud"],
        "leads":            insights["leads"],
        "cpl_aud":          insights["cpl_aud"],
        "summary": (
            f"In the {date_preset}: {insights['leads']} leads at "
            f"AUD ${insights['cpl_aud']:.2f} CPL, "
            f"${insights['spend_aud']:.2f} total spend, "
            f"{insights['impressions']:,} impressions, "
            f"{insights['ctr']:.2f}% CTR."
        ),
    }


@mcp.tool()
async def list_campaigns() -> list[dict]:
    """
    List all Meta Ads campaigns managed through Hexa Hub, with status and budget.
    """
    campaigns = await _request("get", "/ads/meta/campaigns")
    return [
        {
            "id":                c["id"],
            "meta_campaign_id":  c["meta_campaign_id"],
            "status":            c["status"],
            "daily_budget_aud":  c["daily_budget_aud"],
            "objective":         c["objective"],
            "targeting_summary": c["targeting_summary"],
            "synced_at":         c["synced_at"],
            "created_at":        c["created_at"],
        }
        for c in campaigns
    ]


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
