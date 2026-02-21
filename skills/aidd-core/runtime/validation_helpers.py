from __future__ import annotations

from typing import Any, Iterable, List


def require_fields(obj: dict[str, Any], fields: Iterable[str], errors: List[str], *, prefix: str = "") -> None:
    for field in fields:
        if field not in obj:
            errors.append(f"{prefix}missing field: {field}")
