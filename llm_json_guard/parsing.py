"""Explicit JSON extraction policies. No value coercion or automatic repair."""
import json
from math import isfinite
import re
from typing import Any, Iterable


class OutputParseError(ValueError):
    pass


def _pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise OutputParseError(f"Duplicate object key: {key}")
        obj[key] = value
    return obj


def _constant(value):
    raise OutputParseError(f"Non-JSON numeric constant: {value}")


def _float(value):
    number = float(value)
    if not isfinite(number):
        raise OutputParseError("Number exceeds finite floating-point range")
    return number


_DECODER = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=_constant, parse_float=_float)
_FENCE = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)\r?\n```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str, *, allow_prose: bool = False, max_chars: int = 1_000_000) -> Any:
    """Accept complete JSON or one fenced JSON block; prose scanning is opt-in.

    Multiple decoded objects/arrays are ambiguous and rejected. This function
    does not choose a result based on whether it happens to fit a schema.
    """
    if not isinstance(text, str):
        raise TypeError("Model output must be a string")
    if max_chars < 1 or len(text) > max_chars:
        raise OutputParseError("Output exceeds the configured character budget")
    text = text.strip()
    try:
        return _DECODER.decode(text)
    except json.JSONDecodeError:
        pass
    fences = _FENCE.findall(text)
    if fences:
        if len(fences) != 1:
            raise OutputParseError("Expected one JSON block, found multiple")
        try:
            return _DECODER.decode(fences[0].strip())
        except json.JSONDecodeError as exc:
            raise OutputParseError("Fenced block is not valid JSON") from exc
    if not allow_prose:
        raise OutputParseError("Expected complete JSON or one fenced JSON block")
    values = []
    pos = 0
    while pos < len(text):
        if text[pos] not in "[{":
            pos += 1
            continue
        try:
            value, end = _DECODER.raw_decode(text, pos)
        except json.JSONDecodeError:
            pos += 1
            continue
        values.append(value)
        pos = end
    if len(values) != 1:
        raise OutputParseError(f"Expected one embedded JSON value, found {len(values)}")
    return values[0]


def require_keys(value: Any, keys: Iterable[str]) -> dict:
    """Compatibility helper; use OutputGuard for full schema validation."""
    if not isinstance(value, dict):
        raise TypeError("Expected a JSON object")
    missing = [key for key in keys if key not in value]
    if missing:
        raise ValueError(f"Missing required keys: {', '.join(missing)}")
    return value
