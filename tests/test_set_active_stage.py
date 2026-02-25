import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature
from aidd_runtime import context_map_validate, set_active_stage


class SetActiveStageTests(unittest.TestCase):
    def test_valid_stages_include_status(self) -> None:
        self.assertIn("status", set_active_stage.VALID_STAGES)

    def test_spec_alias_normalizes_to_spec_interview(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = ensure_project_root(root)
            write_active_feature(root, "DEMO-1")

            current = Path.cwd()
            try:
                os.chdir(project_root)
                code = set_active_stage.main(["spec"])
            finally:
                os.chdir(current)

            self.assertEqual(code, 0)
            payload = json.loads((project_root / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("stage"), "spec-interview")

    def test_stage_alias_flag_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            project_root = ensure_project_root(root)
            write_active_feature(root, "DEMO-1")

            current = Path.cwd()
            try:
                os.chdir(project_root)
                code = set_active_stage.main(["--stage", "implement"])
            finally:
                os.chdir(current)

            self.assertEqual(code, 0)
            payload = json.loads((project_root / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("stage"), "implement")

    def test_context_map_validator_accepts_legacy_aliases(self) -> None:
        readmap = {
            "schema": "aidd.readmap.v1",
            "ticket": "DEMO",
            "stage": "tasks",
            "scope_key": "iteration_id_I1",
            "work_item_key": "iteration_id=I1",
            "generated_at": "2024-01-01T00:00:00Z",
            "entries": [],
            "allowed_paths": ["src/feature/**"],
            "loop_allowed_paths": ["src/feature/**"],
        }
        self.assertEqual(context_map_validate.validate_context_map_data(readmap), [])

    def test_context_map_validator_rejects_unsupported_stage(self) -> None:
        readmap = {
            "schema": "aidd.readmap.v1",
            "ticket": "DEMO",
            "stage": "release",
            "scope_key": "iteration_id_I1",
            "work_item_key": "iteration_id=I1",
            "generated_at": "2024-01-01T00:00:00Z",
            "entries": [],
            "allowed_paths": ["src/feature/**"],
            "loop_allowed_paths": ["src/feature/**"],
        }
        errors = context_map_validate.validate_context_map_data(readmap)
        self.assertTrue(any("invalid stage: release" in item for item in errors), errors)

    def test_cli_rejects_non_contract_named_flags(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            set_active_stage.parse_args(["--ticket", "DEMO-1", "--stage", "implement"])
        self.assertEqual(int(exc.exception.code), 2)

    def test_cli_rejects_conflicting_positional_and_stage_flag(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            set_active_stage.parse_args(["implement", "--stage", "review"])
        self.assertEqual(int(exc.exception.code), 2)


if __name__ == "__main__":
    unittest.main()
