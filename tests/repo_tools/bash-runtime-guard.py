#!/usr/bin/env python3
"""Guard hook shell entrypoints and enforce no skill shell wrappers."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SKILL_SCRIPTS_GLOB = "skills/*/scripts/*.sh"
FORBIDDEN_RUNTIME_SHELL_GLOBS = ("tools/*.sh", "hooks/*.sh")
HOOK_PY_GLOB = "hooks/*.py"
REPO_TOOLS_SH_GLOB = "tests/repo_tools/*.sh"


def _shebang(path: Path) -> str:
    try:
        first = path.read_text(encoding="utf-8").splitlines()[0].strip()
    except Exception:
        return ""
    return first


def _python_shebang_runtime() -> list[str]:
    hits: list[str] = []
    for path in sorted(ROOT.glob(HOOK_PY_GLOB)):
        if path.name == "__init__.py":
            continue
        if _shebang(path) != "#!/usr/bin/env python3":
            hits.append(path.relative_to(ROOT).as_posix())
    return sorted(hits)

def main() -> int:
    errors: list[str] = []

    skill_scripts = sorted(ROOT.glob(SKILL_SCRIPTS_GLOB))
    for script in skill_scripts:
        rel = script.relative_to(ROOT).as_posix()
        errors.append(f"{rel}: skill shell wrapper is forbidden (python-only canon)")

    for pattern in FORBIDDEN_RUNTIME_SHELL_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            rel = path.relative_to(ROOT).as_posix()
            errors.append(f"{rel}: runtime shell entrypoints are forbidden (use *.py entrypoints)")

    invalid_hook_shebang = _python_shebang_runtime()
    for rel in invalid_hook_shebang:
        errors.append(
            f"{rel}: hook python entrypoint must use '#!/usr/bin/env python3' shebang"
        )

    for script in sorted(ROOT.glob(REPO_TOOLS_SH_GLOB)):
        rel = script.relative_to(ROOT).as_posix()
        if _shebang(script) != "#!/usr/bin/env bash":
            errors.append(f"{rel}: repo tooling shell script must use '#!/usr/bin/env bash'")

    if errors:
        for entry in errors:
            print(f"[bash-runtime-guard] {entry}", file=sys.stderr)
        return 2

    print("[bash-runtime-guard] OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
