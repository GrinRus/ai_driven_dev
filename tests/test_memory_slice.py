import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_feature, write_json

from aidd_runtime import memory_slice


class MemorySliceTests(unittest.TestCase):
    def test_memory_slice_creates_pack_and_latest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="memory-slice-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "MEM-SLICE-1"
            write_active_feature(project_root, ticket)

            write_json(
                project_root,
                f"reports/memory/{ticket}.semantic.pack.json",
                {
                    "schema": "aidd.memory.semantic.v1",
                    "schema_version": "aidd.memory.semantic.v1",
                    "pack_version": "v1",
                    "type": "memory-semantic",
                    "kind": "pack",
                    "ticket": ticket,
                    "slug_hint": ticket.lower(),
                    "generated_at": "2026-02-25T00:00:00Z",
                    "source_path": f"aidd/docs/plan/{ticket}.md",
                    "terms": {
                        "cols": ["term", "definition", "aliases", "scope", "confidence"],
                        "rows": [["gateway", "entry API", [], "aidd/docs/plan", 0.7]],
                    },
                    "defaults": {
                        "cols": ["key", "value", "source", "rationale"],
                        "rows": [["timeout", "30", "aidd/docs/plan", "default"]],
                    },
                    "constraints": {
                        "cols": ["id", "text", "source", "severity"],
                        "rows": [["c1", "must authenticate", "aidd/docs/plan", "high"]],
                    },
                    "invariants": {
                        "cols": ["id", "text", "source"],
                        "rows": [["i1", "always validate", "aidd/docs/plan"]],
                    },
                    "open_questions": ["How to rotate secrets?"],
                    "stats": {},
                },
            )
            write_json(
                project_root,
                f"reports/memory/{ticket}.decisions.pack.json",
                {
                    "schema": "aidd.memory.decisions.pack.v1",
                    "schema_version": "aidd.memory.decisions.pack.v1",
                    "pack_version": "v1",
                    "type": "memory-decisions",
                    "kind": "pack",
                    "ticket": ticket,
                    "slug_hint": ticket.lower(),
                    "generated_at": "2026-02-25T00:00:00Z",
                    "source_path": f"aidd/reports/memory/{ticket}.decisions.jsonl",
                    "active_decisions": {
                        "cols": [
                            "decision_id",
                            "topic",
                            "decision",
                            "status",
                            "ts",
                            "scope_key",
                            "stage",
                            "source_path",
                        ],
                        "rows": [
                            [
                                "d1",
                                "storage",
                                "use sqlite",
                                "active",
                                "2026-02-25T00:00:00Z",
                                "iteration_id_I1",
                                "implement",
                                "aidd/docs/plan",
                            ]
                        ],
                    },
                    "superseded_heads": {
                        "cols": ["decision_id", "supersedes", "topic", "status", "ts"],
                        "rows": [],
                    },
                    "conflicts": [],
                    "stats": {},
                },
            )

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rc = memory_slice.main(["--ticket", ticket, "--query", "sqlite"])
                rc_stage = memory_slice.main(
                    [
                        "--ticket",
                        ticket,
                        "--query",
                        "sqlite",
                        "--stage",
                        "implement",
                        "--scope-key",
                        "iteration_id_I1",
                    ]
                )
            finally:
                os.chdir(old_cwd)
            self.assertEqual(rc, 0)
            self.assertEqual(rc_stage, 0)

            latest_path = project_root / "reports" / "context" / f"{ticket}-memory-slice.latest.pack.json"
            self.assertTrue(latest_path.exists())
            payload = json.loads(latest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("type"), "memory-slice")
            self.assertGreaterEqual(int(payload.get("stats", {}).get("hits", 0)), 1)
            matches = payload.get("matches", {}).get("rows", [])
            self.assertTrue(matches)
            stage_latest = (
                project_root / "reports" / "context" / f"{ticket}-memory-slice.implement.iteration_id_I1.latest.pack.json"
            )
            self.assertTrue(stage_latest.exists(), "stage-aware latest alias must be written")
            manifest = project_root / "reports" / "context" / f"{ticket}-memory-slices.implement.iteration_id_I1.pack.json"
            self.assertTrue(manifest.exists(), "stage-aware manifest must be written")
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest_payload.get("schema"), "aidd.memory.slices.manifest.v1")
            rows = ((manifest_payload.get("slices") or {}).get("rows") or [])
            self.assertTrue(any((isinstance(row, list) and row and row[0] == "sqlite") for row in rows))


if __name__ == "__main__":
    unittest.main()
