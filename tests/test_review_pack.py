import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_file


class ReviewPackTests(unittest.TestCase):
    def test_review_pack_generates_front_matter(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_ticket", "DEMO-1")
            write_file(root, "docs/.active_work_item", "iteration_id=I1")
            loop_pack = (
                "---\n"
                "schema: aidd.loop_pack.v1\n"
                "work_item_id: I1\n"
                "work_item_key: iteration_id=I1\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-1/iteration_id=I1.loop.pack.md", loop_pack)
            report = {
                "ticket": "DEMO-1",
                "status": "READY",
                "findings": [
                    {"id": "review:F1", "severity": "minor", "title": "Update tests"},
                ],
            }
            write_file(root, "reports/reviewer/DEMO-1.json", json.dumps(report, indent=2))

            result = subprocess.run(
                cli_cmd("review-pack", "--ticket", "DEMO-1", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("verdict"), "SHIP")
            self.assertEqual(payload.get("work_item_id"), "I1")
            self.assertEqual(payload.get("work_item_key"), "iteration_id=I1")

            pack_path = root / "reports" / "loops" / "DEMO-1" / "review.latest.pack.md"
            self.assertTrue(pack_path.exists())
            pack_text = pack_path.read_text(encoding="utf-8")
            self.assertIn("schema: aidd.review_pack.v1", pack_text)
            self.assertIn("verdict: SHIP", pack_text)

    def test_review_pack_blocked_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_ticket", "DEMO-2")
            write_file(root, "docs/.active_work_item", "iteration_id=I2")
            loop_pack = (
                "---\n"
                "schema: aidd.loop_pack.v1\n"
                "work_item_id: I2\n"
                "work_item_key: iteration_id=I2\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-2/iteration_id=I2.loop.pack.md", loop_pack)
            report = {"ticket": "DEMO-2", "status": "BLOCKED", "findings": []}
            write_file(root, "reports/reviewer/DEMO-2.json", json.dumps(report, indent=2))

            result = subprocess.run(
                cli_cmd("review-pack", "--ticket", "DEMO-2", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("verdict"), "BLOCKED")


if __name__ == "__main__":
    unittest.main()
