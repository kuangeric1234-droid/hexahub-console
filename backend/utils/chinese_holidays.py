"""
Chinese marketing calendar: major holidays and shopping festivals.

Used by CalendarAgent to:
- Warn when posts are scheduled during sensitive periods
- Suggest holiday-adjacent content boosts (especially for XHS and WeChat)
- Mark PostSlot.is_holiday_adjacent

Not an exhaustive public holiday list — focused on dates that materially
affect content strategy for brands targeting Chinese consumers.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import NamedTuple


class Holiday(NamedTuple):
    name:     str   # English name
    name_zh:  str   # Chinese name
    start:    date
    end:      date
    is_major: bool  # affects posting volume/strategy


# ── 2025 ──────────────────────────────────────────────────────────────────────
_2025: list[Holiday] = [
    Holiday("Chinese New Year",      "春节",  date(2025, 1, 28),  date(2025, 2, 4),   True),
    Holiday("Lantern Festival",      "元宵节", date(2025, 2, 12),  date(2025, 2, 12),  False),
    Holiday("Qingming",              "清明节", date(2025, 4, 4),   date(2025, 4, 6),   False),
    Holiday("Labour Day Golden Week","劳动节", date(2025, 5, 1),   date(2025, 5, 5),   False),
    Holiday("Dragon Boat Festival",  "端午节", date(2025, 5, 31),  date(2025, 6, 2),   False),
    Holiday("618 Shopping Festival", "618",   date(2025, 6, 1),   date(2025, 6, 18),  True),
    Holiday("Qixi (Valentine's)",    "七夕",  date(2025, 8, 29),  date(2025, 8, 29),  False),
    Holiday("Mid-Autumn Festival",   "中秋节", date(2025, 10, 6),  date(2025, 10, 6),  False),
    Holiday("National Day Golden Week","国庆", date(2025, 10, 1),  date(2025, 10, 7),  True),
    Holiday("Double 11",             "双11",  date(2025, 11, 1),  date(2025, 11, 11), True),
    Holiday("Double 12",             "双12",  date(2025, 12, 12), date(2025, 12, 12), False),
]

# ── 2026 ──────────────────────────────────────────────────────────────────────
_2026: list[Holiday] = [
    Holiday("Chinese New Year",      "春节",  date(2026, 2, 17),  date(2026, 2, 23),  True),
    Holiday("Lantern Festival",      "元宵节", date(2026, 3, 3),   date(2026, 3, 3),   False),
    Holiday("Qingming",              "清明节", date(2026, 4, 5),   date(2026, 4, 7),   False),
    Holiday("Labour Day Golden Week","劳动节", date(2026, 5, 1),   date(2026, 5, 5),   False),
    Holiday("Dragon Boat Festival",  "端午节", date(2026, 6, 19),  date(2026, 6, 21),  False),
    Holiday("618 Shopping Festival", "618",   date(2026, 6, 1),   date(2026, 6, 18),  True),
    Holiday("Qixi (Valentine's)",    "七夕",  date(2026, 8, 19),  date(2026, 8, 19),  False),
    Holiday("Mid-Autumn Festival",   "中秋节", date(2026, 9, 25),  date(2026, 9, 25),  False),
    Holiday("National Day Golden Week","国庆", date(2026, 10, 1),  date(2026, 10, 7),  True),
    Holiday("Double 11",             "双11",  date(2026, 11, 1),  date(2026, 11, 11), True),
    Holiday("Double 12",             "双12",  date(2026, 12, 12), date(2026, 12, 12), False),
]

# ── 2027 ──────────────────────────────────────────────────────────────────────
_2027: list[Holiday] = [
    Holiday("Chinese New Year",      "春节",  date(2027, 2, 6),   date(2027, 2, 12),  True),
    Holiday("618 Shopping Festival", "618",   date(2027, 6, 1),   date(2027, 6, 18),  True),
    Holiday("National Day Golden Week","国庆", date(2027, 10, 1),  date(2027, 10, 7),  True),
    Holiday("Double 11",             "双11",  date(2027, 11, 1),  date(2027, 11, 11), True),
]

ALL_HOLIDAYS: list[Holiday] = _2025 + _2026 + _2027

_ADJACENCY_DAYS = 3  # flag a slot if within this many days of a holiday


def get_holidays_in_range(start: date, end: date) -> list[Holiday]:
    """Return all holidays that overlap with [start, end]."""
    return [h for h in ALL_HOLIDAYS if h.start <= end and h.end >= start]


def is_holiday_adjacent(d: date, major_only: bool = False) -> bool:
    """True if `d` falls within or within _ADJACENCY_DAYS of any (or major) holiday."""
    for h in ALL_HOLIDAYS:
        if major_only and not h.is_major:
            continue
        window_start = h.start - timedelta(days=_ADJACENCY_DAYS)
        window_end   = h.end   + timedelta(days=_ADJACENCY_DAYS)
        if window_start <= d <= window_end:
            return True
    return False


def format_holidays_for_prompt(holidays: list[Holiday]) -> str:
    """Render a holiday list as a readable block for injection into LLM prompts."""
    if not holidays:
        return "No major Chinese holidays in this date range."
    lines = []
    for h in holidays:
        flag = " ⭐ MAJOR — boost volume" if h.is_major else ""
        lines.append(f"- {h.name} ({h.name_zh}): {h.start} to {h.end}{flag}")
    return "\n".join(lines)
