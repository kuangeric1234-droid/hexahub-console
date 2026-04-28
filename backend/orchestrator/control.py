"""In-memory pause/resume control for campaign workflows."""
from __future__ import annotations

_paused: set[str] = set()


def pause(campaign_id: str) -> None:
    _paused.add(campaign_id)


def resume(campaign_id: str) -> None:
    _paused.discard(campaign_id)


def is_paused(campaign_id: str) -> bool:
    return campaign_id in _paused
