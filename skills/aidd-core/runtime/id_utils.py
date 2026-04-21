from __future__ import annotations

import hashlib


def stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha1()
    for part in parts:
        digest.update(str(part).encode("utf-8", errors="ignore"))
        digest.update(b"\x1f")
    return f"{prefix}:{digest.hexdigest()[:12]}"
