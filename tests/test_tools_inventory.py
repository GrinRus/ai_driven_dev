import tempfile
import unittest
from pathlib import Path

from aidd_runtime import tools_inventory


class ToolsInventoryTests(unittest.TestCase):
    def test_inventory_classifies_canonical_skill_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tools-inventory-") as tmpdir:
            root = Path(tmpdir)
            (root / "skills" / "aidd-init" / "scripts").mkdir(parents=True, exist_ok=True)
            (root / "skills" / "review" / "scripts").mkdir(parents=True, exist_ok=True)
            (root / "agents").mkdir(parents=True, exist_ok=True)
            (root / "hooks").mkdir(parents=True, exist_ok=True)
            (root / "AGENTS.md").write_text(
                "Runtime includes `${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-pack.sh`.\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text(
                "Use `${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-pack.sh` and "
                "`${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/scripts/init.sh`.\n",
                encoding="utf-8",
            )

            (root / "skills" / "aidd-init" / "scripts" / "init.sh").write_text(
                "#!/usr/bin/env bash\n", encoding="utf-8"
            )
            (root / "skills" / "review" / "scripts" / "review-pack.sh").write_text(
                "#!/usr/bin/env bash\n", encoding="utf-8"
            )
            (root / "agents" / "reviewer.md").write_text("Use artifacts only.\n", encoding="utf-8")
            (root / "hooks" / "gate.sh").write_text(
                "Use `${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-pack.sh`.\n",
                encoding="utf-8",
            )

            payload = tools_inventory._build_payload(root)
            self.assertEqual(payload.get("schema"), "aidd.tools_inventory.v2")
            self.assertIn("skills", payload.get("scan_dirs", []))
            self.assertIn("AGENTS.md", payload.get("scan_dirs", []))

            entries = {entry["path"]: entry for entry in payload.get("entrypoints", [])}

            canonical = entries.get("skills/review/scripts/review-pack.sh")
            self.assertIsNotNone(canonical)
            self.assertEqual(canonical.get("classification"), "canonical_stage")
            by_type = canonical.get("consumers_by_type") or {}
            self.assertIn("hook", by_type)
            self.assertIn("hooks/gate.sh", by_type.get("hook", []))

            init_entry = entries.get("skills/aidd-init/scripts/init.sh")
            self.assertIsNotNone(init_entry)
            self.assertIn(init_entry.get("classification"), {"canonical_stage", "shared_skill"})
            self.assertFalse(init_entry.get("migration_deferred", False))


if __name__ == "__main__":
    unittest.main()
