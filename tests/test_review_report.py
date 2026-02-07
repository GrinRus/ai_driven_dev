import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_active_state, write_file


class ReviewReportTests(unittest.TestCase):
    def test_review_report_creates_marker_and_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-report-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-R", work_item="iteration_id=I1")
            loop_pack = (
                "---\n"
                "schema: aidd.loop_pack.v1\n"
                "work_item_id: I1\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-R/iteration_id_I1.loop.pack.md", loop_pack)
            findings_path = root / "reports" / "reviewer" / "DEMO-R" / "iteration_id_I1.findings.json"
            findings_path.parent.mkdir(parents=True, exist_ok=True)
            findings_path.write_text(
                json.dumps(
                    {
                        "findings": [
                            {
                                "id": "review:F1",
                                "severity": "minor",
                                "summary": "Demo finding",
                                "details": "Demo details",
                            }
                        ]
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                cli_cmd(
                    "review-report",
                    "--ticket",
                    "DEMO-R",
                    "--findings-file",
                    str(findings_path),
                    "--status",
                    "READY",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            marker_path = root / "reports" / "reviewer" / "DEMO-R" / "iteration_id_I1.tests.json"
            self.assertTrue(marker_path.exists())
            pack_path = root / "reports" / "loops" / "DEMO-R" / "iteration_id_I1" / "review.latest.pack.md"
            self.assertTrue(pack_path.exists())


if __name__ == "__main__":
    unittest.main()
