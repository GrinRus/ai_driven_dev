import tempfile
import unittest
from pathlib import Path

from aidd_runtime import tools_inventory


class ToolsInventoryTests(unittest.TestCase):
    def test_inventory_classifies_python_entrypoints_and_consumers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tools-inventory-") as tmpdir:
            root = Path(tmpdir)
            (root / "skills" / "aidd-init" / "runtime").mkdir(parents=True, exist_ok=True)
            (root / "skills" / "review" / "runtime").mkdir(parents=True, exist_ok=True)
            (root / "agents").mkdir(parents=True, exist_ok=True)
            (root / "hooks").mkdir(parents=True, exist_ok=True)
            (root / "AGENTS.md").write_text(
                "Runtime includes `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_pack.py`.\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text(
                "Use `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_pack.py` and "
                "`python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py`.\n",
                encoding="utf-8",
            )

            (root / "skills" / "aidd-init" / "runtime" / "init.py").write_text(
                "#!/usr/bin/env python3\nprint('ok')\n", encoding="utf-8"
            )
            (root / "skills" / "review" / "runtime" / "review_pack.py").write_text(
                "#!/usr/bin/env python3\nprint('ok')\n",
                encoding="utf-8",
            )
            (root / "skills" / "review" / "runtime" / "review_run.py").write_text(
                "#!/usr/bin/env python3\nprint('ok')\n",
                encoding="utf-8",
            )
            (root / "agents" / "reviewer.md").write_text("Use artifacts only.\n", encoding="utf-8")
            (root / "hooks" / "gate_workflow.py").write_text(
                "#!/usr/bin/env python3\nprint('ok')\n",
                encoding="utf-8",
            )
            (root / "hooks" / "gate.sh").write_text(
                "Use `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_pack.py`.\n",
                encoding="utf-8",
            )

            payload = tools_inventory._build_payload(root)
            self.assertEqual(payload.get("schema"), "aidd.tools_inventory.v3")
            self.assertIn("skills", payload.get("scan_dirs", []))
            self.assertIn("AGENTS.md", payload.get("scan_dirs", []))
            self.assertIn("hooks", payload.get("scan_dirs", []))

            entries = {entry["path"]: entry for entry in payload.get("entrypoints", [])}

            review_pack = entries.get("skills/review/runtime/review_pack.py")
            self.assertIsNotNone(review_pack)
            self.assertEqual(review_pack.get("classification"), "canonical_stage")
            self.assertEqual(review_pack.get("runtime_classification"), "python_entrypoint")
            self.assertEqual(review_pack.get("python_owner_path"), "skills/review/runtime/review_pack.py")
            self.assertIn("skills/review/runtime/review_pack.py", review_pack.get("python_owner_paths", []))
            by_type = review_pack.get("consumers_by_type") or {}
            self.assertIn("hook", by_type)
            self.assertIn("hooks/gate.sh", by_type.get("hook", []))

            init_entry = entries.get("skills/aidd-init/runtime/init.py")
            self.assertIsNotNone(init_entry)
            self.assertIn(init_entry.get("classification"), {"canonical_stage", "shared_skill"})
            self.assertEqual(init_entry.get("runtime_classification"), "python_entrypoint")
            self.assertFalse(init_entry.get("migration_deferred", False))

            hook_entry = entries.get("hooks/gate_workflow.py")
            self.assertIsNotNone(hook_entry)
            self.assertEqual(hook_entry.get("classification"), "hook_entrypoint")
            self.assertEqual(hook_entry.get("runtime_classification"), "python_entrypoint")
            self.assertEqual(hook_entry.get("python_owner_path"), "hooks/gate_workflow.py")


if __name__ == "__main__":
    unittest.main()
