#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SCRIPT_GLOB = "skills/*/scripts/*.sh"
SIZE_LIMIT = 200_000  # bytes
STAGE_PYTHON_ENTRYPOINTS = {
    "aidd-init": "skills/aidd-init/runtime/init.py",
    "idea-new": "skills/idea-new/runtime/analyst_check.py",
    "researcher": "skills/researcher/runtime/research.py",
    "plan-new": "skills/plan-new/runtime/research_check.py",
    "review-spec": "skills/review-spec/runtime/prd_review_cli.py",
    "spec-interview": "skills/spec-interview/runtime/spec_interview.py",
    "tasks-new": "skills/tasks-new/runtime/tasks_new.py",
    "implement": "skills/implement/runtime/implement_run.py",
    "review": "skills/review/runtime/review_run.py",
    "qa": "skills/qa/runtime/qa_run.py",
    "status": "skills/status/runtime/status.py",
}


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

    scripts = sorted(ROOT.glob(SCRIPT_GLOB))
    for script in scripts:
        rel = script.relative_to(ROOT).as_posix()
        errors.append(f"{rel}: legacy skill shell wrapper is forbidden (python-only canon)")

    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        text = _read_text(skill_md)
        if not text:
            continue
        if not re.search(r"^user-invocable:\s*true\s*$", text, flags=re.MULTILINE):
            continue
        skill_dir = skill_md.parent
        stage = skill_dir.name
        runtime_rel = STAGE_PYTHON_ENTRYPOINTS.get(stage)
        if runtime_rel:
            runtime_entry = ROOT / runtime_rel
            if not runtime_entry.exists():
                errors.append(f"{runtime_rel}: missing canonical python entrypoint for user-invocable skill `{stage}`")
            runtime_ref = f"python3 ${{CLAUDE_PLUGIN_ROOT}}/{runtime_rel}"
            if runtime_ref not in text:
                errors.append(
                    f"{skill_md.relative_to(ROOT).as_posix()}: must reference canonical python entrypoint `{runtime_ref}`"
                )
        if "/scripts/" in text:
            errors.append(
                f"{skill_md.relative_to(ROOT).as_posix()}: legacy shell wrapper references are forbidden"
            )
        if re.search(r"^context:\s*fork\s*$", text, flags=re.MULTILINE):
            if not re.search(r"^agent:\s*[A-Za-z0-9_.-]+\s*$", text, flags=re.MULTILINE):
                errors.append(
                    f"{skill_md.relative_to(ROOT).as_posix()}: context: fork requires explicit `agent` owner"
                )

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
