import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from aidd_runtime import launcher
from aidd_runtime import review_run


class ReviewRunTests(unittest.TestCase):
    def test_main_fails_when_review_report_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-run-") as tmpdir:
            root = Path(tmpdir)
            context = launcher.LaunchContext(
                root=root,
                ticket="DEMO-1",
                scope_key="iteration_id_I1",
                work_item_key="iteration_id=I1",
                stage="review",
            )
            report_path = root / "reports" / "reviewer" / "DEMO-1" / "iteration_id_I1.json"

            stderr = io.StringIO()
            with (
                patch("aidd_runtime.review_run.launcher.resolve_context", return_value=context),
                patch("aidd_runtime.review_run._resolve_review_report_path", return_value=report_path),
                patch("aidd_runtime.review_run.stage_actions_run.main") as stage_actions_main,
                redirect_stderr(stderr),
            ):
                code = review_run.main(["--ticket", "DEMO-1"])

            self.assertEqual(code, 2)
            stage_actions_main.assert_not_called()
            output = stderr.getvalue()
            self.assertIn("reason_code=review_report_missing", output)
            self.assertIn("diagnostics=canonical_review_report_required", output)

    def test_main_delegates_to_stage_actions_when_report_exists(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-run-") as tmpdir:
            root = Path(tmpdir)
            context = launcher.LaunchContext(
                root=root,
                ticket="DEMO-1",
                scope_key="iteration_id_I1",
                work_item_key="iteration_id=I1",
                stage="review",
            )
            report_path = root / "reports" / "reviewer" / "DEMO-1" / "iteration_id_I1.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("{}", encoding="utf-8")

            with (
                patch("aidd_runtime.review_run.launcher.resolve_context", return_value=context),
                patch("aidd_runtime.review_run._resolve_review_report_path", return_value=report_path),
                patch("aidd_runtime.review_run.stage_actions_run.main", return_value=0) as stage_actions_main,
            ):
                code = review_run.main(["--ticket", "DEMO-1"])

            self.assertEqual(code, 0)
            stage_actions_main.assert_called_once()


if __name__ == "__main__":
    unittest.main()
