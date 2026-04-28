"""
Utilities for extracting JSON from LLM text output.

LLMs sometimes wrap JSON in markdown code fences; this module handles all
common formats so agent code stays clean.
"""
from __future__ import annotations

import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """
    Parse JSON from LLM output.

    Tries, in order:
    1. ```json ... ``` code fence
    2. ``` ... ``` code fence
    3. First { ... } or [ ... ] block found in the text
    4. The raw text (after stripping whitespace)

    Raises ValueError on empty input; json.JSONDecodeError if none succeed.
    """
    if not text or not text.strip():
        raise ValueError("LLM returned empty response — cannot extract JSON")

    fences = [
        r"```json\s*([\s\S]*?)\s*```",
        r"```\s*([\s\S]*?)\s*```",
    ]
    for pattern in fences:
        m = re.search(pattern, text, re.MULTILINE)
        if m:
            candidate = m.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    # Try to extract the first JSON object or array from prose
    for brace_pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        m = re.search(brace_pattern, text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                continue

    return json.loads(text.strip())
