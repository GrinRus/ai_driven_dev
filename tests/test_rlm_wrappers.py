import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT


class RlmWrapperTests(unittest.TestCase):
    def test_wrappers_help_smoke(self) -> None:
        wrappers = [
            REPO_ROOT / "tools" / "rlm-slice.sh",
            REPO_ROOT / "tools" / "rlm-verify.sh",
            REPO_ROOT / "tools" / "rlm-links-build.sh",
            REPO_ROOT / "tools" / "rlm-jsonl-compact.sh",
        ]
        for wrapper in wrappers:
            with self.subTest(wrapper=wrapper.name):
                self.assertTrue(wrapper.exists())
                self.assertTrue(os.access(wrapper, os.X_OK))
                proc = subprocess.run(
                    [sys.executable, str(wrapper), "--help"],
                    cwd=REPO_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
                self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
