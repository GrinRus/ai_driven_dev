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


if __name__ == "__main__":
    unittest.main()
