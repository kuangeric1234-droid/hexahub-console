"""
UTM parameter injection for hexahub.com.au URLs.

Scans generated copy for any hexahub.com.au link and appends UTM tracking
parameters. Runs post-generation so the LLM doesn't need to handle URL
construction — eliminates hallucinated or missing parameters.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse
from uuid import UUID

import structlog

from backend.db.models import Platform

log = structlog.get_logger()

# utm_source and utm_medium by platform
_PLATFORM_UTM: dict[str, tuple[str, str]] = {
    Platform.instagram.value:      ("instagram",    "social"),
    Platform.facebook.value:       ("facebook",     "social"),
    Platform.linkedin.value:       ("linkedin",     "social"),
    Platform.blog.value:           ("hexahub-blog", "organic"),
    Platform.xiaohongshu.value:    ("xiaohongshu",  "social"),
    Platform.wechat_moments.value: ("wechat",       "social"),
}

# Matches bare and scheme-prefixed hexahub.com.au URLs.
#
# Design notes:
#   - (?:https?://)? — optional http/https scheme
#   - (?:www\.)? — optional www subdomain
#   - (?:[/?#][^\s\)\]"'<>]*)? — optional path/query/fragment:
#       starts with /, ?, or # so bare domains without trailing chars are
#       matched cleanly; excludes ), ], ", ' so markdown [text](url) and
#       HTML href="url" links keep their delimiters outside the match.
#   Trailing prose punctuation (.,;:!?) that lands inside the path is stripped
#   in the _replace closure using rstrip before URL reconstruction.
_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?hexahub\.com\.au(?:[/?#][^\s\)\]\"'<>]*)?",
    re.IGNORECASE,
)

_TRAILING_PUNCT = ".,;:!?"


def _short_id(uid: UUID | str) -> str:
    """First 8 hex chars of a UUID — compact, DB-joinable content identifier."""
    return str(uid)[:8]


def _build_utm_url(
    raw_url: str,
    source: str,
    medium: str,
    campaign: str,
    content: str,
) -> str:
    """Return *raw_url* with UTM parameters appended, preserving any existing query params."""
    has_scheme = raw_url.startswith(("http://", "https://"))
    canonical  = raw_url if has_scheme else f"https://{raw_url}"

    parsed   = urlparse(canonical)
    existing = {k: v[0] for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
    merged   = existing | {
        "utm_source":   source,
        "utm_medium":   medium,
        "utm_campaign": campaign,
        "utm_content":  content,
    }
    new_url = urlunparse(parsed._replace(query=urlencode(merged)))

    return new_url if has_scheme else new_url.removeprefix("https://")


def inject_utm(
    text: str,
    platform: Platform,
    campaign_id: UUID | str,
    post_id: UUID | str,
) -> str:
    """
    Replace every hexahub.com.au URL in *text* with a UTM-tagged equivalent.

    Parameters
    ----------
    text:        Copy or ad text to process.
    platform:    Publishing platform — determines utm_source and utm_medium.
    campaign_id: Campaign UUID from CopyInput — first 8 hex chars become utm_campaign.
    post_id:     Post UUID from CopyInput — first 8 hex chars become utm_content,
                 giving a per-post identifier joinable back to DB records.

    Returns the modified text. If no hexahub.com.au URLs are found, the
    original text is returned unchanged and the log line records urls_found=0,
    which is the signal to investigate if URLs were expected.
    """
    source, medium = _PLATFORM_UTM.get(
        platform.value if hasattr(platform, "value") else str(platform),
        ("hexahub", "social"),  # safe fallback for any future platform additions
    )
    campaign = _short_id(campaign_id)
    content  = _short_id(post_id)
    count    = 0

    def _replace(m: re.Match) -> str:
        nonlocal count
        raw      = m.group(0)
        stripped = raw.rstrip(_TRAILING_PUNCT)
        trailing = raw[len(stripped):]
        tagged   = _build_utm_url(stripped, source, medium, campaign, content)
        count   += 1
        return tagged + trailing

    result = _URL_RE.sub(_replace, text)

    log.info(
        "utm_inject",
        post_id=str(post_id),
        platform=platform.value if hasattr(platform, "value") else str(platform),
        urls_found=count,
        urls_modified=count,
    )

    return result
