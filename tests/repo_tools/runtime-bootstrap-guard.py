#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable


MAIN_GUARD_RE = re.compile(r"""if\s+__name__\s*==\s*["']__main__["']\s*:""")
FORBIDDEN_TOP_LEVEL_BOOTSTRAP_RE = re.compile(r"""Path\(__file__\)\.resolve\(\)\.parents\[3\]""")
REQUIRED_BOOTSTRAP_CALL = "ensure_repo_root(__file__)"
ENV_STRIP_KEYS = ("CLAUDE_PLUGIN_ROOT", "AIDD_PLUGIN_DIR", "PYTHONPATH", "PYTHONHOME")


def _entrypoints(root: Path) -> list[Path]:
    candidates = sorted(root.glob("skills/*/runtime/*.py")) + sorted(root.glob("aidd_runtime/*.py"))
    out: list[Path] = []
    for path in candidates:
        if path.name.startswith("_"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if MAIN_GUARD_RE.search(text):
            out.append(path)
    return out


def _top_level_runtime_bootstrap_violations(root: Path) -> list[tuple[Path, str]]:
    violations: list[tuple[Path, str]] = []
    for path in sorted(root.glob("aidd_runtime/*.py")):
        if path.name.startswith("_"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if not MAIN_GUARD_RE.search(text):
            continue
        if FORBIDDEN_TOP_LEVEL_BOOTSTRAP_RE.search(text):
            violations.append((path, "forbidden_parents3_bootstrap"))
        if REQUIRED_BOOTSTRAP_CALL not in text:
            violations.append((path, "missing_ensure_repo_root_helper"))
    return violations


def _isolated_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ENV_STRIP_KEYS:
        env.pop(key, None)
    # Keep probe runs side-effect free for repo worktrees.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _tail(text: str, *, lines: int = 3) -> str:
    chunks = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not chunks:
        return ""
    return " | ".join(chunks[-lines:])


def _run_help(py_bin: str, entrypoint: Path, cwd: Path, env: dict[str, str]) -> tuple[int, str]:
    proc = subprocess.run(
        [py_bin, "-S", str(entrypoint), "--help"],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    details = _tail(proc.stderr) or _tail(proc.stdout)
    return proc.returncode, details


def run_guard(root: Path, *, python_bin: str) -> int:
    violations = _top_level_runtime_bootstrap_violations(root)
    if violations:
        print(
            f"[runtime-bootstrap-guard] ERROR: {len(violations)} top-level runtime bootstrap violations found.",
            file=sys.stderr,
        )
        for path, reason in violations:
            rel = path.relative_to(root).as_posix()
            print(f"[runtime-bootstrap-guard] {rel} -> {reason}", file=sys.stderr)
        return 1

    entrypoints = _entrypoints(root)
    if not entrypoints:
        print("[runtime-bootstrap-guard] WARN: no runtime entrypoints with __main__ guard found.")
        return 0

    env = _isolated_env()
    failures: list[tuple[Path, int, str]] = []
    with tempfile.TemporaryDirectory(prefix="aidd-bootstrap-guard-") as tmpdir:
        tmp = Path(tmpdir)
        for entrypoint in entrypoints:
            code, details = _run_help(python_bin, entrypoint, tmp, env)
            if code != 0:
                failures.append((entrypoint, code, details))

    if failures:
        print(
            f"[runtime-bootstrap-guard] ERROR: {len(failures)}/{len(entrypoints)} "
            "runtime entrypoints failed isolated --help bootstrap checks.",
            file=sys.stderr,
        )
        for path, code, details in failures:
            rel = path.relative_to(root).as_posix()
            suffix = f" :: {details}" if details else ""
            print(f"[runtime-bootstrap-guard] {rel} -> exit={code}{suffix}", file=sys.stderr)
        return 1

    print(
        f"[runtime-bootstrap-guard] OK: {len(entrypoints)} runtime entrypoints passed "
        "isolated bootstrap checks.",
    )
    return 0


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify runtime entrypoints self-bootstrap without CLAUDE_PLUGIN_ROOT/PYTHONPATH.",
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[2]),
        help="Repository root (defaults to current repo).",
    )
    parser.add_argument(
        "--python-bin",
        default="python3",
        help="Python executable to use for probe runs (default: python3).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    if not root.exists():
        print(f"[runtime-bootstrap-guard] ERROR: root not found: {root}", file=sys.stderr)
        return 1
    return run_guard(root, python_bin=str(args.python_bin))


if __name__ == "__main__":
    raise SystemExit(main())
