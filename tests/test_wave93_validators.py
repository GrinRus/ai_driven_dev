import json
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT
from aidd_runtime import (
    aidd_schemas,
    actions_validate,
    context_map_validate,
    preflight_result_validate,
    set_active_stage,
    skill_contract_validate,
)


class Wave93SchemaAndValidatorTests(unittest.TestCase):
    EXPECTED_SCHEMAS = {
        "aidd.actions.v0",
        "aidd.actions.v1",
        "aidd.skill_contract.v1",
        "aidd.readmap.v1",
        "aidd.writemap.v1",
        "aidd.stage_result.v1",
        "aidd.stage_result.preflight.v1",
    }

    def test_schema_registry_contains_wave93_schemas(self) -> None:
        self.assertTrue(self.EXPECTED_SCHEMAS.issubset(set(aidd_schemas.SCHEMA_FILES.keys())))
        for name in self.EXPECTED_SCHEMAS:
            path = aidd_schemas.schema_path(name)
            self.assertTrue(path.exists(), f"missing schema file for {name}")

    def test_actions_validate_supports_v0_and_v1(self) -> None:
        supported = set(actions_validate.SUPPORTED_SCHEMA_VERSIONS)
        self.assertEqual(supported, {"aidd.actions.v0", "aidd.actions.v1"})

        v0 = {
            "schema_version": "aidd.actions.v0",
            "stage": "implement",
            "ticket": "DEMO",
            "scope_key": "iteration_id_I1",
            "work_item_key": "iteration_id=I1",
            "actions": [],
        }
        self.assertEqual(actions_validate.validate_actions_data(v0), [])

        v1 = {
            "schema_version": "aidd.actions.v1",
            "stage": "implement",
            "ticket": "DEMO",
            "scope_key": "iteration_id_I1",
            "work_item_key": "iteration_id=I1",
            "allowed_action_types": [
                "tasklist_ops.set_iteration_done",
                "tasklist_ops.append_progress_log",
                "tasklist_ops.next3_recompute",
                "context_pack_ops.context_pack_update",
            ],
            "actions": [],
        }
        self.assertEqual(actions_validate.validate_actions_data(v1), [])

        invalid = dict(v1)
        invalid.pop("allowed_action_types")
        errors = actions_validate.validate_actions_data(invalid)
        self.assertIn("missing field: allowed_action_types", errors)

    def test_preflight_result_validate_schema(self) -> None:
        payload = {
            "schema": "aidd.stage_result.v1",
            "schema_version": "aidd.stage_result.v1",
            "ticket": "DEMO",
            "stage": "preflight",
            "scope_key": "iteration_id_I1",
            "work_item_key": "iteration_id=I1",
            "result": "done",
            "status": "ok",
            "updated_at": "2024-01-01T00:00:00Z",
            "details": {
                "preflight_status": "ok",
                "target_stage": "implement",
                "artifacts": {
                    "actions_template": "aidd/reports/actions/DEMO/iteration_id_I1/implement.actions.template.json",
                    "readmap_json": "aidd/reports/context/DEMO/iteration_id_I1.readmap.json",
                    "readmap_md": "aidd/reports/context/DEMO/iteration_id_I1.readmap.md",
                    "writemap_json": "aidd/reports/context/DEMO/iteration_id_I1.writemap.json",
                    "writemap_md": "aidd/reports/context/DEMO/iteration_id_I1.writemap.md",
                    "loop_pack": "aidd/reports/loops/DEMO/iteration_id_I1.loop.pack.md",
                },
            },
        }
        self.assertEqual(preflight_result_validate.validate_preflight_result_data(payload), [])

        legacy_payload = {
            "schema": "aidd.stage_result.preflight.v1",
            "ticket": "DEMO",
            "stage": "implement",
            "scope_key": "iteration_id_I1",
            "work_item_key": "iteration_id=I1",
            "status": "ok",
            "generated_at": "2024-01-01T00:00:00Z",
            "artifacts": {
                "actions_template": "aidd/reports/actions/DEMO/iteration_id_I1/implement.actions.template.json",
                "readmap_json": "aidd/reports/context/DEMO/iteration_id_I1.readmap.json",
                "readmap_md": "aidd/reports/context/DEMO/iteration_id_I1.readmap.md",
                "writemap_json": "aidd/reports/context/DEMO/iteration_id_I1.writemap.json",
                "writemap_md": "aidd/reports/context/DEMO/iteration_id_I1.writemap.md",
                "loop_pack": "aidd/reports/loops/DEMO/iteration_id_I1.loop.pack.md",
            },
        }
        self.assertEqual(preflight_result_validate.validate_preflight_result_data(legacy_payload), [])

        broken = dict(payload)
        broken["schema"] = "aidd.stage_result.vX"
        errors = preflight_result_validate.validate_preflight_result_data(broken)
        self.assertTrue(any("schema must be one of" in err for err in errors))

        path_drift = dict(payload)
        path_drift["details"] = dict(payload["details"])
        path_drift["details"]["artifacts"] = dict(payload["details"]["artifacts"])
        path_drift["details"]["artifacts"]["readmap_json"] = "aidd/reports/readmap.json"
        errors = preflight_result_validate.validate_preflight_result_data(path_drift)
        self.assertTrue(any("artifacts.readmap_json must be one of" in err for err in errors))

    def test_context_map_validate_schema(self) -> None:
        readmap = {
            "schema": "aidd.readmap.v1",
            "ticket": "DEMO",
            "stage": "implement",
            "scope_key": "iteration_id_I1",
            "work_item_key": "iteration_id=I1",
            "generated_at": "2024-01-01T00:00:00Z",
            "entries": [
                {
                    "ref": "aidd/reports/loops/DEMO/iteration_id_I1.loop.pack.md#AIDD:WORK_ITEM",
                    "path": "aidd/reports/loops/DEMO/iteration_id_I1.loop.pack.md",
                    "selector": "#AIDD:WORK_ITEM",
                    "required": True,
                    "reason": "loop-pack",
                }
            ],
            "allowed_paths": ["src/feature/**"],
            "loop_allowed_paths": ["src/feature/**"],
        }
        self.assertEqual(context_map_validate.validate_context_map_data(readmap), [])

        writemap = {
            "schema": "aidd.writemap.v1",
            "ticket": "DEMO",
            "stage": "implement",
            "scope_key": "iteration_id_I1",
            "work_item_key": "iteration_id=I1",
            "generated_at": "2024-01-01T00:00:00Z",
            "allowed_paths": ["src/feature/**"],
            "loop_allowed_paths": ["src/feature/**"],
            "docops_only_paths": ["aidd/docs/tasklist/DEMO.md"],
            "always_allow": ["aidd/reports/**", "aidd/reports/actions/**"],
        }
        self.assertEqual(context_map_validate.validate_context_map_data(writemap), [])

        broken = dict(readmap)
        broken["entries"] = "invalid"
        errors = context_map_validate.validate_context_map_data(broken)
        self.assertTrue(any("entries" in err for err in errors))

    def test_review_spec_stage_is_allowed_for_runtime_and_context_maps(self) -> None:
        self.assertIn("review-spec", set_active_stage.VALID_STAGES)
        self.assertIn("review-spec", context_map_validate.VALID_STAGES)
        self.assertIn("status", set_active_stage.VALID_STAGES)
        self.assertIn("tasks", context_map_validate.VALID_STAGES)

    def test_skill_contracts_validate(self) -> None:
        for stage in ("implement", "review", "qa"):
            path = REPO_ROOT / "skills" / stage / "CONTRACT.yaml"
            payload = skill_contract_validate.load_contract(path)
            errors = skill_contract_validate.validate_contract_data(payload, contract_path=path)
            self.assertEqual(errors, [], f"contract {path} failed: {errors}")

    def test_loop_stage_contract_requires_canonical_stage_result_entrypoint(self) -> None:
        path = REPO_ROOT / "skills" / "implement" / "CONTRACT.yaml"
        payload = skill_contract_validate.load_contract(path)
        payload["entrypoints"] = [
            item
            for item in payload.get("entrypoints", [])
            if item != "skills/aidd-flow-state/runtime/stage_result.py"
        ]
        errors = skill_contract_validate.validate_contract_data(payload, contract_path=path)
        self.assertTrue(
            any("canonical stage-result entrypoint" in err for err in errors),
            errors,
        )

    def test_loop_stage_contract_rejects_non_canonical_stage_result_entrypoint(self) -> None:
        path = REPO_ROOT / "skills" / "review" / "CONTRACT.yaml"
        payload = skill_contract_validate.load_contract(path)
        entrypoints = list(payload.get("entrypoints", []))
        entrypoints.append("skills/aidd-loop/runtime/stage_result.py")
        payload["entrypoints"] = entrypoints
        errors = skill_contract_validate.validate_contract_data(payload, contract_path=path)
        self.assertTrue(
            any("non-canonical stage-result entrypoint" in err for err in errors),
            errors,
        )

    def test_actions_schema_files_are_json(self) -> None:
        for schema in ("aidd.actions.v0", "aidd.actions.v1"):
            path = aidd_schemas.schema_path(schema)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("schema_version"), schema)

    def test_all_wave93_schema_versions_match_registry_names(self) -> None:
        for schema in sorted(self.EXPECTED_SCHEMAS):
            path = aidd_schemas.schema_path(schema)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("schema_version"), schema, f"{path} schema_version mismatch")
            self.assertEqual(data.get("$id"), schema, f"{path} $id mismatch")

    def test_validators_supported_versions_match_schema_registry(self) -> None:
        self.assertEqual(
            set(actions_validate.SUPPORTED_SCHEMA_VERSIONS),
            set(aidd_schemas.supported_schema_versions("aidd.actions.v")),
        )
        expected_preflight_versions = (
            set(aidd_schemas.supported_schema_versions("aidd.stage_result.preflight.v"))
            | set(aidd_schemas.supported_schema_versions("aidd.stage_result.v"))
        )
        self.assertEqual(
            set(preflight_result_validate.SUPPORTED_SCHEMA_VERSIONS),
            expected_preflight_versions,
        )
        expected_map_versions = (
            set(aidd_schemas.supported_schema_versions("aidd.readmap.v"))
            | set(aidd_schemas.supported_schema_versions("aidd.writemap.v"))
        )
        self.assertEqual(set(context_map_validate.SUPPORTED_SCHEMA_VERSIONS), expected_map_versions)
        self.assertEqual(
            set(skill_contract_validate.SUPPORTED_SCHEMA_VERSIONS),
            set(aidd_schemas.supported_schema_versions("aidd.skill_contract.v")),
        )


if __name__ == "__main__":
    unittest.main()
