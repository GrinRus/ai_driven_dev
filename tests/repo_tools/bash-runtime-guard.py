#!/usr/bin/env python3
"""Guard hook shell entrypoints and enforce no skill shell wrappers."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_SCRIPTS_GLOB = "skills/*/scripts/*.sh"
RUNTIME_GLOBS = ("tools/*.sh", "hooks/*.sh")
ALLOWLIST_PATH = ROOT / "tests" / "repo_tools" / "python-shebang-allowlist.txt"


def _read_allowlist(path: Path) -> list[str]:
    if not path.exists():
        return []
    items: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        items.append(value)
    return sorted(set(items))


def _shebang(path: Path) -> str:
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0].strip()
    except Exception:
        return ""
    return first


def _python_shebang_runtime() -> list[str]:
    hits: list[str] = []
    for pattern in RUNTIME_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if _shebang(path) == "#!/usr/bin/env python3":
                hits.append(path.relative_to(ROOT).as_posix())
    return sorted(hits)

def main() -> int:
    errors: list[str] = []

    skill_scripts = sorted(ROOT.glob(SKILL_SCRIPTS_GLOB))
    for script in skill_scripts:
        rel = script.relative_to(ROOT).as_posix()
        errors.append(f"{rel}: skill shell wrapper is forbidden (python-only canon)")

    allowed = _read_allowlist(ALLOWLIST_PATH)
    current = _python_shebang_runtime()

    unexpected = sorted(set(current) - set(allowed))
    stale = sorted(set(allowed) - set(current))
    for rel in unexpected:
        errors.append(
            f"{rel}: python-shebang .sh is not allowlisted "
            f"(move to canonical bash script or update allowlist)"
        )
    for rel in stale:
        errors.append(
            f"{rel}: stale allowlist entry (no longer python-shebang); "
            "remove from tests/repo_tools/python-shebang-allowlist.txt"
        )

    if errors:
        for entry in errors:
            print(f"[bash-runtime-guard] {entry}", file=sys.stderr)
        return 2

    print("[bash-runtime-guard] OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
