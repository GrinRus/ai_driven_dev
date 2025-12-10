#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import MutableMapping, Sequence

INSTALL_HINT = (
    "CLI 'claude-workflow' не найден. Установите его командой \n"
    "  uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git\n"
    "или\n"
    "  pipx install git+https://github.com/GrinRus/ai_driven_dev.git"
)

# repo root or site-packages root; runtime workflow lives in ./aidd relative to workspace
PROJECT_ROOT = Path(__file__).resolve().parents[5]
DEV_SRC = PROJECT_ROOT / "src"
VENDOR_DIR = PROJECT_ROOT / ".claude" / "hooks" / "_vendor"
HAS_VENDOR = VENDOR_DIR.exists()
DEV_SRC_OVERRIDE = Path(os.environ.get("CLAUDE_WORKFLOW_DEV_SRC", "")).expanduser()

if DEV_SRC.exists():
    sys.path.insert(0, str(DEV_SRC))
if DEV_SRC_OVERRIDE.is_dir():
    sys.path.insert(0, str(DEV_SRC_OVERRIDE))
if HAS_VENDOR:
    sys.path.insert(0, str(VENDOR_DIR))

class CliNotFoundError(RuntimeError):
    """Raised when the claude-workflow CLI cannot be located."""


@dataclass
class Runner:
    argv: list[str]
    uses_python: bool


def _module_available() -> bool:
    if DEV_SRC.exists() or HAS_VENDOR:
        return True
    try:
        import importlib.util

        return importlib.util.find_spec("claude_workflow_cli.cli") is not None
    except Exception:
        return False


def _cli_module_available() -> bool:
    try:
        import importlib.util

        return importlib.util.find_spec("claude_workflow_cli.cli") is not None
    except Exception:
        return False


def _enhance_env(env: MutableMapping[str, str], runner: Runner) -> MutableMapping[str, str]:
    if not runner.uses_python:
        return env
    python_path_parts = []
    if DEV_SRC.exists():
        python_path_parts.append(str(DEV_SRC))
    if DEV_SRC_OVERRIDE.is_dir():
        python_path_parts.append(str(DEV_SRC_OVERRIDE))
    if VENDOR_DIR.exists():
        python_path_parts.append(str(VENDOR_DIR))
    if python_path_parts:
        existing = env.get("PYTHONPATH")
        python_path_parts.append(existing or "")
        env["PYTHONPATH"] = os.pathsep.join([p for p in python_path_parts if p])
    return env


def _resolve_runner() -> Runner:
    override_bin = os.environ.get("CLAUDE_WORKFLOW_BIN")
    if override_bin:
        candidate = Path(override_bin)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return Runner([str(candidate)], False)
    override_python = os.environ.get("CLAUDE_WORKFLOW_PYTHON")
    if override_python:
        return Runner([override_python, "-m", "claude_workflow_cli.cli"], True)
    if DEV_SRC.exists() or _cli_module_available():
        return Runner([sys.executable, "-m", "claude_workflow_cli.cli"], True)
    discovered = shutil.which("claude-workflow")
    if discovered:
        return Runner([discovered], False)
    raise CliNotFoundError(INSTALL_HINT)


def _print_hint() -> None:
    print(f"[claude-workflow] {INSTALL_HINT}", file=sys.stderr)


def run_cli(
    args: Sequence[str], *, check: bool = True, env: MutableMapping[str, str] | None = None, cwd: str | None = None
) -> subprocess.CompletedProcess:
    runner = _resolve_runner()
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    run_env = _enhance_env(run_env, runner)
    if runner.uses_python and not _module_available():
        raise CliNotFoundError(INSTALL_HINT)
    cmd = runner.argv + list(args)
    try:
        return subprocess.run(cmd, check=check, env=run_env, cwd=cwd)
    except FileNotFoundError as exc:
        raise CliNotFoundError(INSTALL_HINT) from exc


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(argv or sys.argv[1:])
    if not arguments:
        print("Usage: python -m run_cli <command> [args...]", file=sys.stderr)
        return 64
    try:
        result = run_cli(arguments, check=False)
    except CliNotFoundError:
        _print_hint()
        return 127
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
