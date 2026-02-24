import subprocess
import tempfile
from pathlib import Path

from tests.helpers import REPO_ROOT, cli_env


GUARD_SCRIPT = REPO_ROOT / "tests" / "repo_tools" / "cli-adapter-guard.py"


def _run_guard(root: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(GUARD_SCRIPT), "--root", str(root), *extra_args],
        text=True,
        capture_output=True,
        check=False,
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_cli_adapter_guard_repo_smoke() -> None:
    result = subprocess.run(
        ["python3", str(GUARD_SCRIPT)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        env=cli_env(),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "[cli-adapter-guard] SUMMARY:" in result.stdout


def test_cli_adapter_guard_blocks_missing_help_sections() -> None:
    with tempfile.TemporaryDirectory(prefix="cli-adapter-guard-") as tmpdir:
        root = Path(tmpdir)
        _write(
            root / "skills" / "demo" / "runtime" / "tool.py",
            """#!/usr/bin/env python3
import argparse

def main() -> int:
    parser = argparse.ArgumentParser(description="Demo CLI.")
    parser.add_argument("--ticket", default="DEMO-1")
    parser.parse_args()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
""",
        )

        result = _run_guard(root)
        assert result.returncode == 2
        assert "must include an Examples section" in result.stderr
        assert "must include an Outputs section" in result.stderr
        assert "must include an Exit codes section" in result.stderr


def test_cli_adapter_guard_blocks_hook_signals_inside_skills_runtime() -> None:
    with tempfile.TemporaryDirectory(prefix="cli-adapter-guard-") as tmpdir:
        root = Path(tmpdir)
        _write(
            root / "skills" / "demo" / "runtime" / "bad.py",
            """#!/usr/bin/env python3
from hooks import hooklib
import argparse

def main() -> int:
    parser = argparse.ArgumentParser(description="Bad runtime with hook signal.")
    parser.parse_args()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
""",
        )

        result = _run_guard(root)
        assert result.returncode == 2
        assert "hook-runtime signal in skills runtime" in result.stderr


def test_cli_adapter_guard_blocks_stale_help_missing_declared_option() -> None:
    with tempfile.TemporaryDirectory(prefix="cli-adapter-guard-") as tmpdir:
        root = Path(tmpdir)
        _write(
            root / "skills" / "demo" / "runtime" / "stale.py",
            """#!/usr/bin/env python3
import argparse

def main() -> int:
    parser = argparse.ArgumentParser(description="Demo CLI.")
    parser.add_argument("--ticket", required=True)
    parser.parse_args()
    return 0

if __name__ == "__main__":
    import sys
    if "--help" in sys.argv:
        print("usage: stale.py [-h]")
        print("")
        print("Demo CLI.")
        print("")
        print("Examples:")
        print("  python3 ${CLAUDE_PLUGIN_ROOT}/skills/demo/runtime/stale.py --help")
        print("")
        print("Outputs:")
        print("  stdout: status.")
        print("")
        print("Exit codes:")
        print("  0 - success.")
        print("  1 - failure.")
        raise SystemExit(0)
    raise SystemExit(main())
""",
        )

        result = _run_guard(root)
        assert result.returncode == 2
        assert "missing declared argparse options" in result.stderr


def test_cli_adapter_guard_blocks_help_with_unknown_option() -> None:
    with tempfile.TemporaryDirectory(prefix="cli-adapter-guard-") as tmpdir:
        root = Path(tmpdir)
        _write(
            root / "skills" / "demo" / "runtime" / "ghost.py",
            """#!/usr/bin/env python3
import argparse
import sys

def main() -> int:
    parser = argparse.ArgumentParser(description="Demo CLI.")
    parser.add_argument("--ticket")
    parser.parse_args()
    return 0

if __name__ == "__main__":
    if "--help" in sys.argv:
        print("usage: ghost.py [-h] [--ticket TICKET]")
        print("")
        print("Demo CLI.")
        print("")
        print("options:")
        print("  -h, --help        show this help message and exit")
        print("  --ticket TICKET   ticket")
        print("  --ghost GHOST     missing option in source")
        print("")
        print("Examples:")
        print("  python3 ${CLAUDE_PLUGIN_ROOT}/skills/demo/runtime/ghost.py --help")
        print("")
        print("Outputs:")
        print("  stdout: status.")
        print("")
        print("Exit codes:")
        print("  0 - success.")
        print("  1 - failure.")
        raise SystemExit(0)
    raise SystemExit(main())
""",
        )

        result = _run_guard(root)
        assert result.returncode == 2
        assert "lists options not declared in source" in result.stderr


def test_cli_adapter_guard_allows_library_runtime_modules() -> None:
    with tempfile.TemporaryDirectory(prefix="cli-adapter-guard-") as tmpdir:
        root = Path(tmpdir)
        _write(
            root / "skills" / "demo" / "runtime" / "lib.py",
            """def meaning() -> int:
    return 42
""",
        )

        result = _run_guard(root)
        assert result.returncode == 0, result.stderr
        assert "library=1" in result.stdout


def test_cli_adapter_guard_accepts_complete_help_contract() -> None:
    with tempfile.TemporaryDirectory(prefix="cli-adapter-guard-") as tmpdir:
        root = Path(tmpdir)
        _write(
            root / "skills" / "demo" / "runtime" / "ok.py",
            """#!/usr/bin/env python3
import argparse

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Demo CLI for strict contract.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=\"\"\"Examples:
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/demo/runtime/ok.py --help
  python3 ${CLAUDE_PLUGIN_ROOT}/skills/demo/runtime/ok.py --ticket DEMO-1

Outputs:
  stdout: validation summary.

Exit codes:
  0 - success.
  1 - runtime failure.
  2 - CLI usage error.\"\"\",
    )
    parser.add_argument("--ticket", required=True, help="Ticket identifier.")
    return parser.parse_args(argv)

def main() -> int:
    parse_args()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
""",
        )

        result = _run_guard(root, "--fail-on-warn")
        assert result.returncode == 0, result.stderr
