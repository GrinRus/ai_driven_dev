import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT


def _isolated_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in ("CLAUDE_PLUGIN_ROOT", "AIDD_PLUGIN_DIR", "PYTHONPATH", "PYTHONHOME"):
        env.pop(key, None)
    return env


class RlmWrapperTests(unittest.TestCase):
    def test_runtime_entrypoints_help_smoke(self) -> None:
        entrypoints = [
            REPO_ROOT / "skills" / "aidd-rlm" / "runtime" / "rlm_slice.py",
            REPO_ROOT / "skills" / "aidd-rlm" / "runtime" / "rlm_nodes_build.py",
            REPO_ROOT / "skills" / "aidd-rlm" / "runtime" / "rlm_verify.py",
            REPO_ROOT / "skills" / "aidd-rlm" / "runtime" / "rlm_links_build.py",
            REPO_ROOT / "skills" / "aidd-rlm" / "runtime" / "rlm_jsonl_compact.py",
            REPO_ROOT / "skills" / "aidd-rlm" / "runtime" / "rlm_finalize.py",
            REPO_ROOT / "skills" / "aidd-rlm" / "runtime" / "reports_pack.py",
        ]
        with tempfile.TemporaryDirectory(prefix="rlm-help-smoke-") as tmpdir:
            for entrypoint in entrypoints:
                with self.subTest(entrypoint=entrypoint.name):
                    self.assertTrue(entrypoint.exists())
                    proc = subprocess.run(
                        ["python3", "-S", str(entrypoint), "--help"],
                        cwd=tmpdir,
                        env=_isolated_env(),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)

    def test_critical_entrypoints_help_without_external_env(self) -> None:
        entrypoints = [
            REPO_ROOT / "skills" / "aidd-flow-state" / "runtime" / "set_active_stage.py",
            REPO_ROOT / "skills" / "aidd-rlm" / "runtime" / "rlm_links_build.py",
        ]
        with tempfile.TemporaryDirectory(prefix="runtime-help-smoke-") as tmpdir:
            for entrypoint in entrypoints:
                with self.subTest(entrypoint=entrypoint.name):
                    self.assertTrue(entrypoint.exists())
                    proc = subprocess.run(
                        ["python3", "-S", str(entrypoint), "--help"],
                        cwd=tmpdir,
                        env=_isolated_env(),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)


if __name__ == "__main__":
    unittest.main()
