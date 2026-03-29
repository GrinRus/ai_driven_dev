import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import memory_extract
from tests.helpers import cli_cmd, cli_env


class MemoryExtractTests(unittest.TestCase):
    def test_memory_extract_generates_semantic_pack_for_ticket(self) -> None:
        with tempfile.TemporaryDirectory(prefix="memory-extract-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = workspace / "aidd"
            project_root.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                cli_cmd("init"),
                cwd=workspace,
                env=cli_env(),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            ticket = "MEM-EXTRACT-1"
            (project_root / "docs" / "prd" / f"{ticket}.prd.md").write_text(
                "\n".join(
                    [
                        "# PRD",
                        "",
                        "Status: READY",
                        "",
                        "## Constraints",
                        "- Must keep stage_result canonical",
                        "- Default mode is always_soft",
                        "",
                        "## AIDD:OPEN_QUESTIONS",
                        "- Should review gate become strict?",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (project_root / "docs" / "plan" / f"{ticket}.md").write_text(
                "# Plan\n\n- Invariant: output contract is deterministic\n",
                encoding="utf-8",
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rc = memory_extract.main(["--ticket", ticket])
            finally:
                os.chdir(old_cwd)
            self.assertEqual(rc, 0)

            semantic_path = project_root / "reports" / "memory" / f"{ticket}.semantic.pack.json"
            self.assertTrue(semantic_path.exists())
            payload = json.loads(semantic_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("ticket"), ticket)
            sections = payload.get("sections") or {}
            self.assertTrue(sections.get("constraints"))
            self.assertTrue(sections.get("open_questions"))


if __name__ == "__main__":
    unittest.main()
