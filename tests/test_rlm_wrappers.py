import os
import subprocess
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT


class RlmWrapperTests(unittest.TestCase):
    def test_wrappers_help_smoke(self) -> None:
        wrappers = [
            REPO_ROOT / "skills" / "aidd-core" / "scripts" / "rlm-slice.sh",
            REPO_ROOT / "skills" / "researcher" / "scripts" / "rlm-nodes-build.sh",
            REPO_ROOT / "skills" / "researcher" / "scripts" / "rlm-verify.sh",
            REPO_ROOT / "skills" / "researcher" / "scripts" / "rlm-links-build.sh",
            REPO_ROOT / "skills" / "researcher" / "scripts" / "rlm-jsonl-compact.sh",
            REPO_ROOT / "skills" / "researcher" / "scripts" / "rlm-finalize.sh",
            REPO_ROOT / "skills" / "researcher" / "scripts" / "reports-pack.sh",
        ]
        for wrapper in wrappers:
            with self.subTest(wrapper=wrapper.name):
                self.assertTrue(wrapper.exists())
                self.assertTrue(os.access(wrapper, os.X_OK))
                proc = subprocess.run(
                    [str(wrapper), "--help"],
                    cwd=REPO_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
