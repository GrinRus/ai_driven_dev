import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tests" / "repo_tools" / "runtime-module-guard.py"


def _run_guard(*, warn: int, error: int) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["AIDD_RUNTIME_MODULE_WARN_LINES"] = str(warn)
    env["AIDD_RUNTIME_MODULE_ERROR_LINES"] = str(error)
    return subprocess.run(
        ["python3", str(SCRIPT)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        env=env,
    )


def test_runtime_module_guard_scans_nested_runtime_files() -> None:
    result = _run_guard(warn=10, error=11)
    assert result.returncode != 0
    assert "skills/aidd-loop/runtime/loop_step_parts/core.py" in result.stderr


def test_runtime_module_guard_ignores_thin_runtime_adapters() -> None:
    result = _run_guard(warn=1, error=2)
    assert result.returncode != 0
    assert "skills/qa/runtime/qa.py" not in result.stderr
    assert "skills/aidd-loop/runtime/loop_step_parts/core.py" in result.stderr
