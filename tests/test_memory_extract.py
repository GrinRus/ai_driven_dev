import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature, write_file

from aidd_runtime import memory_extract


class MemoryExtractTests(unittest.TestCase):
    def test_memory_extract_creates_semantic_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="memory-extract-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "MEM-EXT-1"
            write_active_feature(project_root, ticket)

            write_file(
                project_root,
                f"docs/plan/{ticket}.md",
                "\n".join(
                    [
                        "Status: READY",
                        "timeout: 30",
                        "API: gateway endpoint",
                        "must authenticate each request",
                        "always keep decision ids stable",
                        "How do we rotate secrets?",
                    ]
                )
                + "\n",
            )
            write_file(
                project_root,
                f"reports/context/{ticket}.pack.md",
                "\n".join(
                    [
                        "## AIDD:TLDR",
                        "- fallback: rg",
                        "- must not read full logs by default",
                    ]
                )
                + "\n",
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rc = memory_extract.main(["--ticket", ticket])
            finally:
                os.chdir(old_cwd)
            self.assertEqual(rc, 0)

            output_path = project_root / "reports" / "memory" / f"{ticket}.semantic.pack.json"
            self.assertTrue(output_path.exists())
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema_version"), "aidd.memory.semantic.v1")
            self.assertEqual(payload.get("ticket"), ticket)
            self.assertTrue(payload.get("terms", {}).get("rows"))
            self.assertTrue(payload.get("defaults", {}).get("rows"))
            self.assertTrue(payload.get("constraints", {}).get("rows"))
            self.assertTrue(payload.get("invariants", {}).get("rows"))
            self.assertLessEqual(int(payload.get("stats", {}).get("size", {}).get("chars", 0)), 8000)


if __name__ == "__main__":
    unittest.main()

