import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_file
from tools.io_utils import parse_front_matter


class ReviewReportTests(unittest.TestCase):
    def test_review_report_idempotent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-report-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_ticket", "DEMO-REPORT")
            findings_path = root / "reports" / "reviewer" / "DEMO-REPORT-findings.json"
            findings_path.parent.mkdir(parents=True, exist_ok=True)
            findings_path.write_text(
                json.dumps(
                    [
                        {
                            "severity": "major",
                            "scope": "api",
                            "title": "Review coverage",
                            "recommendation": "Add regression checks",
                        }
                    ],
                    indent=2,
                ),
                encoding="utf-8",
            )

            cmd = cli_cmd(
                "review-report",
                "--ticket",
                "DEMO-REPORT",
                "--work-item-key",
                "iteration_id=I1",
                "--findings-file",
                str(findings_path),
                "--status",
                "warn",
            )
            result = subprocess.run(cmd, text=True, capture_output=True, cwd=root, env=cli_env())
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            report_path = root / "reports" / "reviewer" / "DEMO-REPORT" / "iteration_id_I1.json"
            report_payload = json.loads(report_path.read_text(encoding="utf-8"))
            first_updated_at = report_payload.get("updated_at")
            self.assertTrue(first_updated_at)

            result = subprocess.run(cmd, text=True, capture_output=True, cwd=root, env=cli_env())
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            report_payload = json.loads(report_path.read_text(encoding="utf-8"))
            second_updated_at = report_payload.get("updated_at")
            self.assertEqual(first_updated_at, second_updated_at)

    def test_review_report_autogenerates_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-report-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_ticket", "DEMO-PACK")
            write_file(root, "docs/.active_work_item", "iteration_id=I2")
            loop_pack = (
                "---\n"
                "schema: aidd.loop_pack.v1\n"
                "work_item_id: I2\n"
                "work_item_key: iteration_id=I2\n"
                "scope_key: iteration_id_I2\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-PACK/iteration_id_I2.loop.pack.md", loop_pack)

            cmd = cli_cmd(
                "review-report",
                "--ticket",
                "DEMO-PACK",
                "--work-item-key",
                "iteration_id=I2",
                "--status",
                "ready",
            )
            result = subprocess.run(cmd, text=True, capture_output=True, cwd=root, env=cli_env())
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            report_path = root / "reports" / "reviewer" / "DEMO-PACK" / "iteration_id_I2.json"
            report_payload = json.loads(report_path.read_text(encoding="utf-8"))
            report_updated_at = report_payload.get("updated_at")
            self.assertTrue(report_updated_at)

            pack_path = root / "reports" / "loops" / "DEMO-PACK" / "iteration_id_I2" / "review.latest.pack.md"
            self.assertTrue(pack_path.exists())
            pack_front = parse_front_matter(pack_path.read_text(encoding="utf-8"))
            self.assertEqual(pack_front.get("review_report_updated_at"), report_updated_at)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(unittest.main())
