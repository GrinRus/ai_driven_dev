import tempfile
import unittest
from pathlib import Path

from tools import tools_inventory


class ToolsInventoryTests(unittest.TestCase):
    def test_inventory_classifies_shim_canonical_and_deferred_core(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tools-inventory-") as tmpdir:
            root = Path(tmpdir)
            (root / "tools").mkdir(parents=True, exist_ok=True)
            (root / "skills" / "review" / "scripts").mkdir(parents=True, exist_ok=True)
            (root / "agents").mkdir(parents=True, exist_ok=True)
            (root / "hooks").mkdir(parents=True, exist_ok=True)

            (root / "tools" / "review-pack.sh").write_text(
                "#!/usr/bin/env bash\n"
                "printf '[aidd] DEPRECATED\\n' >&2\n"
                "exec \"${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-pack.sh\" \"$@\"\n",
                encoding="utf-8",
            )
            (root / "tools" / "init.sh").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
            (root / "skills" / "review" / "scripts" / "review-pack.sh").write_text(
                "#!/usr/bin/env bash\n", encoding="utf-8"
            )
            (root / "agents" / "reviewer.md").write_text(
                "Use `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh` and `${CLAUDE_PLUGIN_ROOT}/tools/init.sh`.\n",
                encoding="utf-8",
            )
            (root / "hooks" / "gate.sh").write_text(
                "Use `${CLAUDE_PLUGIN_ROOT}/skills/review/scripts/review-pack.sh`.\n",
                encoding="utf-8",
            )
            (root / "AGENTS.md").write_text(
                "Runtime includes `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh`.\n",
                encoding="utf-8",
            )

            payload = tools_inventory._build_payload(root)
            self.assertEqual(payload.get("schema"), "aidd.tools_inventory.v2")
            self.assertIn("skills", payload.get("scan_dirs", []))
            self.assertIn("AGENTS.md", payload.get("scan_dirs", []))

            entries = {entry["path"]: entry for entry in payload.get("entrypoints", [])}

            shim = entries.get("tools/review-pack.sh")
            self.assertIsNotNone(shim)
            self.assertEqual(shim.get("classification"), "shim")
            self.assertEqual(shim.get("canonical_replacement_path"), "skills/review/scripts/review-pack.sh")
            self.assertIn("agent", shim.get("consumer_types"))
            self.assertIn("docs", shim.get("consumer_types"))

            deferred = entries.get("tools/init.sh")
            self.assertIsNotNone(deferred)
            self.assertEqual(deferred.get("classification"), "core_api_deferred")
            self.assertTrue(deferred.get("core_api"))
            self.assertTrue(deferred.get("migration_deferred"))

            canonical = entries.get("skills/review/scripts/review-pack.sh")
            self.assertIsNotNone(canonical)
            self.assertEqual(canonical.get("classification"), "canonical_stage")
            by_type = canonical.get("consumers_by_type") or {}
            self.assertIn("hook", by_type)
            self.assertIn("hooks/gate.sh", by_type.get("hook", []))


if __name__ == "__main__":
    unittest.main()
