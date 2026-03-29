import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests" / "repo_tools" / "silent-except-guard.py"


def _run_guard() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_silent_except_guard_clean_repo() -> None:
    result = _run_guard()
    assert result.returncode == 0
    assert "[silent-except-guard] OK" in result.stdout


def test_silent_except_guard_detects_new_violation() -> None:
    probe = ROOT / "hooks" / "__silent_except_guard_probe__.py"
    probe.write_text(
        "try:\n"
        "    raise RuntimeError('boom')\n"
        "except Exception:\n"
        "    pass\n",
        encoding="utf-8",
    )
    try:
        result = _run_guard()
    finally:
        probe.unlink(missing_ok=True)

    assert result.returncode != 0
    assert "hooks/__silent_except_guard_probe__.py" in result.stderr
    assert "silent except handler" in result.stderr
