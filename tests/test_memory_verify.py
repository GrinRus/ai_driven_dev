import json
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import aidd_schemas, memory_verify


def _semantic_payload() -> dict:
    return {
        "schema": "aidd.memory.semantic.v1",
        "schema_version": "aidd.memory.semantic.v1",
        "pack_version": "v1",
        "type": "memory-semantic",
        "kind": "pack",
        "ticket": "MEM-1",
        "slug_hint": "mem-1",
        "generated_at": "2026-02-25T00:00:00Z",
        "source_path": "aidd/docs/plan/MEM-1.md",
        "terms": {
            "cols": ["term", "definition", "aliases", "scope", "confidence"],
            "rows": [["api", "Application API", [], "aidd/docs/plan/MEM-1.md", 0.7]],
        },
        "defaults": {
            "cols": ["key", "value", "source", "rationale"],
            "rows": [["timeout", "30", "aidd/docs/plan/MEM-1.md", "default"]],
        },
        "constraints": {
            "cols": ["id", "text", "source", "severity"],
            "rows": [["c1", "must use auth", "aidd/docs/plan/MEM-1.md", "high"]],
        },
        "invariants": {
            "cols": ["id", "text", "source"],
            "rows": [["i1", "always validate input", "aidd/docs/plan/MEM-1.md"]],
        },
        "open_questions": ["How is token refresh handled?"],
        "stats": {"source_files_count": 1},
    }


def _decision_payload() -> dict:
    return {
        "schema": "aidd.memory.decision.v1",
        "schema_version": "aidd.memory.decision.v1",
        "ts": "2026-02-25T00:00:00Z",
        "ticket": "MEM-1",
        "scope_key": "iteration_id_I1",
        "stage": "implement",
        "decision_id": "d1",
        "topic": "storage",
        "decision": "use sqlite",
        "alternatives": ["postgres"],
        "rationale": "local workflow",
        "source_path": "aidd/docs/plan/MEM-1.md",
        "status": "active",
    }


def _decisions_pack_payload() -> dict:
    return {
        "schema": "aidd.memory.decisions.pack.v1",
        "schema_version": "aidd.memory.decisions.pack.v1",
        "pack_version": "v1",
        "type": "memory-decisions",
        "kind": "pack",
        "ticket": "MEM-1",
        "slug_hint": "mem-1",
        "generated_at": "2026-02-25T00:00:00Z",
        "source_path": "aidd/reports/memory/MEM-1.decisions.jsonl",
        "active_decisions": {
            "cols": ["decision_id", "topic", "decision", "status", "ts", "scope_key", "stage", "source_path"],
            "rows": [["d1", "storage", "use sqlite", "active", "2026-02-25T00:00:00Z", "iteration_id_I1", "implement", "aidd/docs/plan/MEM-1.md"]],
        },
        "superseded_heads": {
            "cols": ["decision_id", "supersedes", "topic", "status", "ts"],
            "rows": [],
        },
        "conflicts": [],
        "stats": {"entries_total": 1},
    }


class MemoryVerifyTests(unittest.TestCase):
    def test_schema_registry_contains_memory_schemas(self) -> None:
        expected = {
            "aidd.memory.semantic.v1",
            "aidd.memory.decision.v1",
            "aidd.memory.decisions.pack.v1",
        }
        self.assertTrue(expected.issubset(set(aidd_schemas.SCHEMA_FILES)))
        for schema_name in expected:
            self.assertTrue(aidd_schemas.schema_path(schema_name).exists())

    def test_validate_semantic_payload_ok(self) -> None:
        errors = memory_verify.validate_memory_data(_semantic_payload(), max_chars=8000, max_lines=200)
        self.assertEqual(errors, [])

    def test_validate_decision_payload_rejects_bad_status(self) -> None:
        payload = _decision_payload()
        payload["status"] = "pending"
        errors = memory_verify.validate_decision_data(payload)
        self.assertTrue(any("memory_invalid_enum" in err for err in errors), errors)

    def test_validate_decisions_pack_budget(self) -> None:
        payload = _decisions_pack_payload()
        errors = memory_verify.validate_memory_data(payload, max_chars=120, max_lines=10)
        self.assertTrue(any("memory_budget_chars_exceeded" in err for err in errors), errors)

    def test_cli_validates_jsonl_decisions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="memory-verify-") as tmpdir:
            path = Path(tmpdir) / "decisions.jsonl"
            valid = json.dumps(_decision_payload(), ensure_ascii=False)
            invalid = "{bad json}"
            path.write_text(valid + "\n" + invalid + "\n", encoding="utf-8")
            rc = memory_verify.main(["--input", str(path)])
            self.assertEqual(rc, 2)

    def test_cli_print_supported_versions(self) -> None:
        rc = memory_verify.main(["--print-supported-versions"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()

