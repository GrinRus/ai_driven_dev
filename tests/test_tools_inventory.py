import tempfile
import unittest
from pathlib import Path

from tools import tools_inventory


class ToolsInventoryTests(unittest.TestCase):
    def test_inventory_counts_skill_and_root_consumers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tools-inventory-") as tmpdir:
            root = Path(tmpdir)
            (root / "tools").mkdir(parents=True, exist_ok=True)
            (root / "tools" / "review-pack.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (root / "skills" / "review").mkdir(parents=True, exist_ok=True)
            (root / "skills" / "review" / "SKILL.md").write_text(
                "Use `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh` for report packing.\n",
                encoding="utf-8",
            )
            (root / "AGENTS.md").write_text(
                "Runtime includes `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh`.\n",
                encoding="utf-8",
            )

            payload = tools_inventory._build_payload(root)
            self.assertIn("skills", payload.get("scan_dirs", []))
            self.assertIn("AGENTS.md", payload.get("scan_dirs", []))

            tools = {entry["tool"]: entry for entry in payload.get("tools", [])}
            review_pack = tools.get("tools/review-pack.sh")
            self.assertIsNotNone(review_pack, "tool entry must be present")
            consumers = set(review_pack.get("consumers") or [])
            self.assertIn("skills/review/SKILL.md", consumers)
            self.assertIn("AGENTS.md", consumers)


if __name__ == "__main__":
    unittest.main()
