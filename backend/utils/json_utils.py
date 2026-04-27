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
    3. The raw text (after stripping whitespace)

    Raises json.JSONDecodeError if none succeed.
    """
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
                continue  # try next pattern

    return json.loads(text.strip())
