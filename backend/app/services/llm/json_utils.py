"""Shared helpers for providers' ``structured()`` JSON calls."""

from __future__ import annotations

import json
from typing import Any


def with_schema_instruction(prompt: str, schema: dict) -> str:
    """Append the JSON-only instruction and schema every provider sends."""
    return (
        f"{prompt}\n\nRespond ONLY with valid JSON matching this schema:\n"
        f"{json.dumps(schema, indent=2)}"
    )


def loads_first_json(text: str) -> Any:
    """Parse JSON, tolerating leading prose or trailing data the model may emit.

    Models sometimes return a valid JSON value followed by extra text (a bare
    ``json.loads`` then raises "Extra data"). Fall back to decoding the first complete
    JSON value found, ignoring anything after it.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for i, ch in enumerate(text):
            if ch in "{[":
                try:
                    obj, _ = decoder.raw_decode(text[i:])
                    return obj
                except json.JSONDecodeError:
                    continue
        raise


def parse_json_response(text: str) -> Any:
    """Strip markdown code fences, then parse tolerantly."""
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(
            lines[1:-1] if lines[-1].startswith("```") else lines[1:]
        )
    return loads_first_json(text)
