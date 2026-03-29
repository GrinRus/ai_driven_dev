import json
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import aidd_schemas, memory_verify


class MemoryVerifyTests(unittest.TestCase):
    def test_schema_registry_contains_memory_schemas(self) -> None:
        expected = {
            "aidd.memory.semantic.v1",
            "aidd.memory.decision.v1",
            "aidd.memory.decisions.pack.v1",
        }
        self.assertTrue(expected.issubset(set(aidd_schemas.SCHEMA_FILES.keys())))
        for schema in expected:
            path = aidd_schemas.schema_path(schema)
            self.assertTrue(path.exists(), f"missing schema file: {schema}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema_version"), schema)
            self.assertEqual(payload.get("$id"), schema)

    def test_validate_semantic_payload(self) -> None:
        payload = {
            "schema": memory_verify.SEMANTIC_SCHEMA,
            "schema_version": memory_verify.SEMANTIC_SCHEMA,
            "ticket": "TST-MEM-1",
            "generated_at": "2026-03-16T00:00:00Z",
            "status": "ok",
            "source_paths": ["aidd/docs/prd/TST-MEM-1.prd.md"],
            "sections": {
                "terms": ["AIDD"],
                "defaults": ["Default gate mode is soft."],
                "constraints": ["Must write artifacts under aidd/."],
                "invariants": ["stage_result schema is canonical."],
                "open_questions": ["Should memory gate be strict by default?"],
            },
        }
        self.assertEqual(memory_verify.validate_semantic_data(payload), [])

        broken = dict(payload)
        broken["sections"] = {}
        errors = memory_verify.validate_semantic_data(broken)
        self.assertTrue(any("sections.terms" in err for err in errors), errors)

    def test_validate_decision_payload(self) -> None:
        payload = {
            "schema": memory_verify.DECISION_SCHEMA,
            "schema_version": memory_verify.DECISION_SCHEMA,
            "ticket": "TST-MEM-2",
            "decision_id": "DEC-001",
            "created_at": "2026-03-16T00:00:00Z",
            "stage": "review",
            "scope_key": "iteration_id_I1",
            "source": "loop",
            "title": "Use canonical stage result",
            "decision": "Disallow manual stage_result writes",
            "rationale": "Prevent drift and hidden recovery paths",
            "tags": ["stage-result", "policy"],
            "supersedes": [],
            "conflicts_with": [],
            "status": "active",
            "content_hash": "sha256:deadbeef",
            "prev_hash": "sha256:prev",
            "entry_hash": "sha256:entry",
        }
        self.assertEqual(memory_verify.validate_decision_data(payload), [])

        broken = dict(payload)
        broken["status"] = "unknown"
        errors = memory_verify.validate_decision_data(broken)
        self.assertTrue(any("status must be" in err for err in errors), errors)

    def test_validate_decisions_pack_payload(self) -> None:
        decision = {
            "schema": memory_verify.DECISION_SCHEMA,
            "schema_version": memory_verify.DECISION_SCHEMA,
            "ticket": "TST-MEM-3",
            "decision_id": "DEC-002",
            "created_at": "2026-03-16T00:00:00Z",
            "stage": "plan",
            "scope_key": "ticket",
            "source": "loop",
            "title": "Plan soft mode",
            "decision": "Allow pending soft mode in plan",
            "rationale": "Temporal rollout",
            "tags": ["research", "rollout"],
            "supersedes": [],
            "conflicts_with": [],
            "status": "active",
            "content_hash": "sha256:c0ffee",
            "prev_hash": "",
            "entry_hash": "sha256:cafe",
        }
        payload = {
            "schema": memory_verify.DECISIONS_PACK_SCHEMA,
            "schema_version": memory_verify.DECISIONS_PACK_SCHEMA,
            "ticket": "TST-MEM-3",
            "generated_at": "2026-03-16T00:00:00Z",
            "status": "ok",
            "active": [decision],
            "superseded": [],
            "top": [decision],
            "conflicts": [],
            "counts": {"active_total": 1},
        }
        self.assertEqual(memory_verify.validate_decisions_pack_data(payload), [])

        broken = dict(payload)
        broken["active"] = [dict(decision, status="invalid-status")]
        errors = memory_verify.validate_decisions_pack_data(broken)
        self.assertTrue(any("active[0] invalid decision" in err for err in errors), errors)

    def test_cli_validate_single_file(self) -> None:
        payload = {
            "schema": memory_verify.SEMANTIC_SCHEMA,
            "schema_version": memory_verify.SEMANTIC_SCHEMA,
            "ticket": "TST-MEM-CLI",
            "generated_at": "2026-03-16T00:00:00Z",
            "status": "ok",
            "source_paths": ["aidd/docs/research/TST-MEM-CLI.md"],
            "sections": {
                "terms": ["TERM"],
                "defaults": ["default"],
                "constraints": ["must"],
                "invariants": ["always"],
                "open_questions": ["question"],
            },
        }
        with tempfile.TemporaryDirectory(prefix="memory-verify-") as tmpdir:
            path = Path(tmpdir) / "semantic.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            rc = memory_verify.main(["--semantic", str(path), "--quiet"])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
