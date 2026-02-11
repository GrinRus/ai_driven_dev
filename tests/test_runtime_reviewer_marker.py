import json
import tempfile
import unittest
from pathlib import Path

from aidd_runtime import runtime


class RuntimeReviewerMarkerMigrationTests(unittest.TestCase):
    def _project_root(self, tmpdir: str) -> Path:
        root = Path(tmpdir) / "aidd"
        root.mkdir(parents=True, exist_ok=True)
        return root

    def test_reviewer_marker_migration_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-reviewer-marker-") as tmpdir:
            root = self._project_root(tmpdir)
            fallback_path = root / "reports" / "reviewer" / "DEMO" / "iteration_id_I1.json"
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"ticket": "DEMO", "tests": "required"}
            fallback_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            template = "aidd/reports/reviewer/{ticket}/{scope_key}.tests.json"
            marker_path = runtime.reviewer_marker_path(
                root,
                template,
                "DEMO",
                None,
                scope_key="iteration_id=I1",
            )
            self.assertTrue(marker_path.exists(), "canonical marker path should be created")
            self.assertFalse(fallback_path.exists(), "fallback marker should be removed after migration")
            migrated_payload = json.loads(marker_path.read_text(encoding="utf-8"))
            self.assertEqual(migrated_payload.get("tests"), "required")

            marker_path_second = runtime.reviewer_marker_path(
                root,
                template,
                "DEMO",
                None,
                scope_key="iteration_id=I1",
            )
            self.assertEqual(marker_path_second, marker_path)
            self.assertTrue(marker_path_second.exists())
            self.assertFalse(fallback_path.exists())

    def test_reviewer_marker_migration_skips_review_reports(self) -> None:
        with tempfile.TemporaryDirectory(prefix="runtime-reviewer-marker-") as tmpdir:
            root = self._project_root(tmpdir)
            fallback_path = root / "reports" / "reviewer" / "DEMO" / "iteration_id_I1.json"
            fallback_path.parent.mkdir(parents=True, exist_ok=True)
            fallback_path.write_text(
                json.dumps({"kind": "review", "findings": []}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            marker_path = runtime.reviewer_marker_path(
                root,
                "aidd/reports/reviewer/{ticket}/{scope_key}.tests.json",
                "DEMO",
                None,
                scope_key="iteration_id=I1",
            )
            self.assertFalse(marker_path.exists(), "review reports must not be migrated into tests marker")
            self.assertTrue(fallback_path.exists(), "review report payload must remain at fallback path")


if __name__ == "__main__":
    unittest.main()
