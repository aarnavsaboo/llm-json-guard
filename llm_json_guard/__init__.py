import json
import re
from typing import Any, Iterable

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_json(text: str) -> Any:
    """Extract the first JSON object or array from a model response."""
    text = text.strip()
    fenced = _FENCE.search(text)

    if fenced:
        text = fenced.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    starts = [i for i in (text.find("{"), text.find("[")) if i >= 0]

    if not starts:
        raise ValueError("No JSON object or array found")

    start = min(starts)
    decoder = json.JSONDecoder()

    try:
        value, _ = decoder.raw_decode(text[start:])
        return value
    except json.JSONDecodeError as exc:
        raise ValueError("Could not parse JSON from model output") from exc


def require_keys(value: Any, keys: Iterable[str]) -> dict:
    if not isinstance(value, dict):
        raise TypeError("Expected a JSON object")

    missing = [key for key in keys if key not in value]

    if missing:
        raise ValueError(f"Missing required keys: {', '.join(missing)}")

    return value
