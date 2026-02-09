#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCRIPT_GLOB = "skills/*/scripts/*.sh"
REQUIRED_FLAGS = ["--ticket", "--scope-key", "--work-item-key", "--stage", "--actions"]
SIZE_LIMIT = 200_000  # bytes


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _is_binary(path: Path) -> bool:
    try:
        data = path.read_bytes()
    except Exception:
        return False
    return b"\x00" in data


def main() -> int:
    errors: list[str] = []

    wrapper_contract = ROOT / "skills" / "aidd-reference" / "wrapper_contract.md"
    if not wrapper_contract.exists():
        errors.append("missing skills/aidd-reference/wrapper_contract.md")

    scripts = sorted(ROOT.glob(SCRIPT_GLOB))
    if not scripts:
        errors.append("no stage scripts found in skills/*/scripts")

    for script in scripts:
        rel = script.relative_to(ROOT).as_posix()
        text = _read_text(script)
        lines = text.splitlines()
        if not lines or lines[0].strip() != "#!/usr/bin/env bash":
            errors.append(f"{rel}: missing '#!/usr/bin/env bash'")
        if "set -euo pipefail" not in text:
            errors.append(f"{rel}: missing 'set -euo pipefail'")
        if not os.access(script, os.X_OK):
            errors.append(f"{rel}: not executable")
        if "aidd_run_guarded" not in text:
            errors.append(f"{rel}: missing aidd_run_guarded output guard")
        if "aidd_log_path" not in text:
            errors.append(f"{rel}: missing aidd_log_path usage")

        if script.name in {"preflight.sh", "run.sh", "postflight.sh"}:
            for flag in REQUIRED_FLAGS:
                if flag not in text:
                    errors.append(f"{rel}: missing flag {flag}")
            if "actions_path=" not in text:
                errors.append(f"{rel}: missing actions_path output")
        if script.name == "postflight.sh" and "AIDD_APPLY_LOG" not in text:
            errors.append(f"{rel}: missing AIDD_APPLY_LOG usage")

        stage = script.parents[1].name
        references = []
        skill_md = ROOT / "skills" / stage / "SKILL.md"
        details_md = ROOT / "skills" / stage / "DETAILS.md"
        for path in (skill_md, details_md):
            if path.exists():
                references.append(_read_text(path))
        if references:
            if script.name not in "\n".join(references):
                errors.append(f"{rel}: not referenced in skills/{stage}/SKILL.md or DETAILS.md")
        else:
            errors.append(f"{rel}: missing SKILL.md for stage {stage}")

    for path in (ROOT / "skills").rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix in {".pyc", ".pyo"}:
            continue
        if _is_binary(path):
            errors.append(f"{rel}: binary file detected in skills")
            continue
        size = path.stat().st_size
        if size > SIZE_LIMIT:
            errors.append(f"{rel}: file too large ({size} bytes) in skills")

    if errors:
        for entry in errors:
            print(f"[skill-scripts-guard] {entry}", file=sys.stderr)
        return 2
    print("[skill-scripts-guard] OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
