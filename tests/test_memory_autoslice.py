import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root, write_active_state, write_json

from aidd_runtime import memory_autoslice


def _seed_memory_packs(project_root: Path, ticket: str) -> None:
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
            "source_path": f"aidd/docs/research/{ticket}.md",
            "terms": {
                "cols": ["term", "definition", "aliases", "scope", "confidence"],
                "rows": [["constraint", "must keep auth", [], "aidd/docs/plan", 0.8]],
            },
            "defaults": {
                "cols": ["key", "value", "source", "rationale"],
                "rows": [["timeout", "30", "aidd/docs/plan", "default"]],
            },
            "constraints": {
                "cols": ["id", "text", "source", "severity"],
                "rows": [["c1", "must validate token", "aidd/docs/plan", "high"]],
            },
            "invariants": {
                "cols": ["id", "text", "source"],
                "rows": [["i1", "never skip auth", "aidd/docs/plan"]],
            },
            "open_questions": ["decision scope?"],
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
                "cols": ["decision_id", "topic", "decision", "status", "ts", "scope_key", "stage", "source_path"],
                "rows": [["d1", "fallback", "use slices first", "active", "2026-02-25T00:00:00Z", ticket, "plan", "aidd/docs/plan"]],
            },
            "superseded_heads": {
                "cols": ["decision_id", "supersedes", "topic", "status", "ts"],
                "rows": [],
            },
            "conflicts": [],
            "stats": {},
        },
    )


class MemoryAutosliceTests(unittest.TestCase):
    def test_memory_autoslice_writes_stage_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="memory-autoslice-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "MEM-AUTO-1"
            write_active_state(project_root, ticket=ticket, stage="plan")
            _seed_memory_packs(project_root, ticket)

            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                rc = memory_autoslice.main(
                    [
                        "--ticket",
                        ticket,
                        "--stage",
                        "plan",
                        "--scope-key",
                        ticket,
                    ]
                )
            finally:
                os.chdir(old_cwd)

            self.assertEqual(rc, 0)
            manifest_path = project_root / "reports" / "context" / f"{ticket}-memory-slices.plan.{ticket}.pack.json"
            self.assertTrue(manifest_path.exists())
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("schema"), "aidd.memory.slices.manifest.v1")
            rows = ((payload.get("slices") or {}).get("rows") or [])
            self.assertGreaterEqual(len(rows), 1)

    def test_memory_autoslice_hard_mode_blocks_when_queries_fail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="memory-autoslice-hard-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "MEM-AUTO-HARD"
            write_active_state(project_root, ticket=ticket, stage="plan")

            write_json(
                project_root,
                "config/conventions.json",
                {
                    "memory": {
                        "slice_policy": {
                            "mode": "hard",
                            "enforce_stages": ["plan"],
                        }
                    }
                },
            )
            write_json(
                project_root,
                "config/gates.json",
                {
                    "memory": {
                        "slice_enforcement": "hard",
                        "enforce_stages": ["plan"],
                    }
                },
            )

            stdout = io.StringIO()
            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with contextlib.redirect_stdout(stdout):
                    rc = memory_autoslice.main(
                        [
                            "--ticket",
                            ticket,
                            "--stage",
                            "plan",
                            "--scope-key",
                            ticket,
                            "--format",
                            "json",
                        ]
                    )
            finally:
                os.chdir(old_cwd)

            self.assertEqual(rc, 2)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "memory_slice_missing")

    def test_memory_autoslice_normalizes_stage_alias_in_enforce_stages(self) -> None:
        with tempfile.TemporaryDirectory(prefix="memory-autoslice-alias-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "MEM-AUTO-ALIAS"
            write_active_state(project_root, ticket=ticket, stage="review-spec")

            write_json(
                project_root,
                "config/conventions.json",
                {
                    "memory": {
                        "slice_policy": {
                            "mode": "hard",
                            "enforce_stages": ["review_spec"],
                        }
                    }
                },
            )
            write_json(
                project_root,
                "config/gates.json",
                {
                    "memory": {
                        "slice_enforcement": "hard",
                        "enforce_stages": ["review_spec"],
                    }
                },
            )

            stdout = io.StringIO()
            old_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                with contextlib.redirect_stdout(stdout):
                    rc = memory_autoslice.main(
                        [
                            "--ticket",
                            ticket,
                            "--stage",
                            "review-spec",
                            "--scope-key",
                            ticket,
                            "--format",
                            "json",
                        ]
                    )
            finally:
                os.chdir(old_cwd)

            self.assertEqual(rc, 2)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "memory_slice_missing")


if __name__ == "__main__":
    unittest.main()
