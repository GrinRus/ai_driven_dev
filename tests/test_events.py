import json
import tempfile
import unittest
from pathlib import Path

from aidd_runtime.reports import events


class EventReasonCodeTests(unittest.TestCase):
    def test_append_event_normalizes_optional_ast_fallback_to_warn(self) -> None:
        with tempfile.TemporaryDirectory(prefix="events-ast-soft-") as tmpdir:
            root = Path(tmpdir) / "aidd"
            root.mkdir(parents=True, exist_ok=True)
            events.append_event(
                root,
                ticket="EV-AST-SOFT",
                slug_hint="ev-ast-soft",
                event_type="research",
                status="ok",
                details={
                    "ast_required": False,
                    "ast_reason_code": "AST_INDEX_BINARY_MISSING",
                    "ast_next_action": "ast-index rebuild",
                },
                source="test",
            )

            payload = json.loads((root / "reports" / "events" / "EV-AST-SOFT.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(payload.get("status"), "warn")
            self.assertEqual(payload.get("reason_code"), "ast_index_binary_missing")
            details = payload.get("details") or {}
            self.assertEqual(details.get("ast_reason_code"), "ast_index_binary_missing")
            self.assertEqual(details.get("ast_fallback_policy"), "warn")

    def test_append_event_required_ast_fallback_sets_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="events-ast-hard-") as tmpdir:
            root = Path(tmpdir) / "aidd"
            root.mkdir(parents=True, exist_ok=True)
            events.append_event(
                root,
                ticket="EV-AST-HARD",
                slug_hint="ev-ast-hard",
                event_type="research",
                status="ok",
                details={
                    "ast_required": True,
                    "ast_reason_code": "AST_INDEX_INDEX_MISSING",
                    "ast_next_action": "ast-index rebuild",
                },
                source="test",
            )

            payload = json.loads((root / "reports" / "events" / "EV-AST-HARD.jsonl").read_text(encoding="utf-8").splitlines()[-1])
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "ast_index_index_missing")
            details = payload.get("details") or {}
            self.assertEqual(details.get("ast_fallback_policy"), "blocked")
            self.assertEqual(details.get("next_action"), "ast-index rebuild")

    def test_append_event_applies_extended_context_quality_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="events-context-quality-") as tmpdir:
            root = Path(tmpdir) / "aidd"
            root.mkdir(parents=True, exist_ok=True)
            events.append_event(
                root,
                ticket="EV-CQ-1",
                slug_hint="ev-cq-1",
                event_type="loop",
                status="ok",
                details={
                    "context_quality": {
                        "pack_reads": 1,
                        "slice_reads": 1,
                        "memory_slice_reads": 1,
                        "full_reads": 0,
                        "retrieval_events": 1,
                        "fallback_events": 0,
                        "rg_invocations": 2,
                        "rg_without_slice": 1,
                        "decisions_pack_stale_events": 1,
                    }
                },
                source="test",
            )

            quality_path = root / "reports" / "observability" / "EV-CQ-1.context-quality.json"
            payload = json.loads(quality_path.read_text(encoding="utf-8"))
            metrics = payload.get("metrics") or {}
            self.assertGreaterEqual(int(metrics.get("memory_slice_reads") or 0), 1)
            self.assertGreaterEqual(int(metrics.get("rg_invocations") or 0), 2)
            self.assertGreaterEqual(int(metrics.get("rg_without_slice") or 0), 1)
            self.assertGreaterEqual(int(metrics.get("decisions_pack_stale_events") or 0), 1)


if __name__ == "__main__":
    unittest.main()
