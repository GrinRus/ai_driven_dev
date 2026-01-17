import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_file


class ContextPackTests(unittest.TestCase):
    def test_context_pack_collects_anchors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="context-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(
                root,
                "docs/prd/DEMO-1.prd.md",
                "# PRD\n\n## AIDD:GOALS\n- goal\n",
            )
            write_file(
                root,
                "docs/plan/DEMO-1.md",
                "# Plan\n\n## AIDD:FILES_TOUCHED\n- src/app.py\n",
            )
            write_file(
                root,
                "docs/tasklist/DEMO-1.md",
                "# Tasklist\n\n## AIDD:CONTEXT_PACK\n- Focus: demo\n",
            )
            result = subprocess.run(
                cli_cmd(
                    "context-pack",
                    "--ticket",
                    "DEMO-1",
                    "--agent",
                    "implementer",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            pack_path = root / "reports" / "context" / "DEMO-1-implementer.md"
            self.assertTrue(pack_path.exists())
            text = pack_path.read_text(encoding="utf-8")
            self.assertIn("AIDD:CONTEXT_PACK", text)
            self.assertIn("AIDD:FILES_TOUCHED", text)
            self.assertIn("AIDD:GOALS", text)


if __name__ == "__main__":
    unittest.main()
