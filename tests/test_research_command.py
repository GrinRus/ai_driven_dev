import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_ROOT = REPO_ROOT / "src" / "claude_workflow_cli" / "data" / "payload"
SRC_ROOT = REPO_ROOT / "src"


class ResearchCommandTest(unittest.TestCase):
    def test_research_command_materializes_summary(self):
        with tempfile.TemporaryDirectory(prefix="claude-workflow-research-") as tmpdir:
            env = os.environ.copy()
            env["CLAUDE_TEMPLATE_DIR"] = str(PAYLOAD_ROOT)
            subprocess.run(
                ["bash", str(PAYLOAD_ROOT / "init-claude-workflow.sh"), "--commit-mode", "ticket-prefix"],
                cwd=tmpdir,
                env=env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            command_env = env.copy()
            pythonpath = os.pathsep.join(filter(None, [str(SRC_ROOT), command_env.get("PYTHONPATH")]))
            command_env["PYTHONPATH"] = pythonpath
            subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "tools" / "run_cli.py"),
                    "research",
                    "--target",
                    tmpdir,
                    "--ticket",
                    "TEST-123",
                    "--limit",
                    "1",
                ],
                cwd=tmpdir,
                env=command_env,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            summary_path = Path(tmpdir) / "docs" / "research" / "TEST-123.md"
            self.assertTrue(summary_path.exists(), "Research summary should be materialised")


if __name__ == "__main__":
    unittest.main()
