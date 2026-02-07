import json
import tempfile
import unittest
from pathlib import Path

from tools import active_state
from tools import feature_ids


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


if __name__ == "__main__":
    unittest.main()
