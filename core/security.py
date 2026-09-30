"""Durable-runtime security boundary for sensitive values."""

from __future__ import annotations

import re
from typing import Any

_SENSITIVE_KEY = re.compile(
    r"(api[_-]?key|access[_-]?token|session[_-]?token|token|auth(?:orization)?|credential|"
    r"password|passwd|secret|private[_-]?key|session[_-]?token|cookie)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|"
    r"xox[baprs]-[A-Za-z0-9-]{12,}|Bearer\s+[A-Za-z0-9._~+/=-]{12,})\b"
)


def redact_sensitive(value: Any, *, key: str | None = None) -> Any:
    """Return a JSON-like value safe for durable runtime persistence."""
    if key and _SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(k): redact_sensitive(v, key=str(k))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(redact_sensitive(item) for item in value)
    if isinstance(value, str) and _SENSITIVE_VALUE.search(value):
        return _SENSITIVE_VALUE.sub("[REDACTED]", value)
    return value
