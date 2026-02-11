import json
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import active_state
from aidd_runtime import feature_ids


class ActiveStateTests(unittest.TestCase):
    def test_normalize_review_id_keeps_current_iteration(self) -> None:
        normalized, report_id = active_state.normalize_work_item_for_stage(
            stage="review",
            requested_work_item="id=review:report-42",
            current_work_item="iteration_id=I7",
        )
        self.assertEqual(normalized, "iteration_id=I7")
        self.assertEqual(report_id, "review:report-42")

    def test_normalize_review_id_without_iteration_clears_work_item(self) -> None:
        normalized, report_id = active_state.normalize_work_item_for_stage(
            stage="implement",
            requested_work_item="id=review:report-42",
            current_work_item="",
        )
        self.assertEqual(normalized, "")
        self.assertEqual(report_id, "review:report-42")

    def test_write_active_state_stores_last_review_report_id(self) -> None:
        with tempfile.TemporaryDirectory(prefix="active-state-") as tmpdir:
            workspace = Path(tmpdir)
            aidd = workspace / "aidd"
            (aidd / "docs").mkdir(parents=True, exist_ok=True)

            feature_ids.write_active_state(aidd, ticket="DEMO-1", stage="review", work_item="iteration_id=I1")
            feature_ids.write_active_state(aidd, stage="review", work_item="id=review:report-99")

            payload = json.loads((aidd / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("work_item"), "iteration_id=I1")
            self.assertEqual(payload.get("last_review_report_id"), "review:report-99")

    def test_write_identifiers_normalizes_slug_token_from_note(self) -> None:
        with tempfile.TemporaryDirectory(prefix="active-state-") as tmpdir:
            workspace = Path(tmpdir)
            aidd = workspace / "aidd"
            (aidd / "docs").mkdir(parents=True, exist_ok=True)

            feature_ids.write_identifiers(
                aidd,
                ticket="TST-001",
                slug_hint="tst-001-demo Audit backend workflow determinism",
                scaffold_prd_file=False,
            )

            payload = json.loads((aidd / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("slug_hint"), "tst-001-demo")

    def test_write_identifiers_keeps_existing_slug_when_note_is_not_token(self) -> None:
        with tempfile.TemporaryDirectory(prefix="active-state-") as tmpdir:
            workspace = Path(tmpdir)
            aidd = workspace / "aidd"
            (aidd / "docs").mkdir(parents=True, exist_ok=True)

            feature_ids.write_identifiers(
                aidd,
                ticket="TST-001",
                slug_hint="slug=tst-001-demo",
                scaffold_prd_file=False,
            )
            feature_ids.write_identifiers(
                aidd,
                ticket="TST-001",
                slug_hint="AIDD:ANSWERS answer 1: proceed with defaults",
                scaffold_prd_file=False,
            )

            payload = json.loads((aidd / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(payload.get("slug_hint"), "tst-001-demo")

    def test_iteration_work_item_allows_i_and_m_prefixes(self) -> None:
        self.assertTrue(active_state.is_iteration_work_item_key("iteration_id=I1"))
        self.assertTrue(active_state.is_iteration_work_item_key("iteration_id=M4"))


if __name__ == "__main__":
    unittest.main()
