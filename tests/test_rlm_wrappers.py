import subprocess
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, cli_env


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
        for entrypoint in entrypoints:
            with self.subTest(entrypoint=entrypoint.name):
                self.assertTrue(entrypoint.exists())
                proc = subprocess.run(
                    ["python3", str(entrypoint), "--help"],
                    cwd=REPO_ROOT,
                    env=cli_env(),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
