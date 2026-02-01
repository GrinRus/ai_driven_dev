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
            write_file(root, "reports/loops/DEMO-1/iteration_id_I1.loop.pack.md", loop_pack)
            report = {
                "ticket": "DEMO-1",
                "status": "READY",
                "findings": [
                    {"id": "review:F1", "severity": "minor", "title": "Update tests"},
                ],
            }
            write_file(root, "reports/reviewer/DEMO-1/iteration_id_I1.json", json.dumps(report, indent=2))

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

            pack_path = root / "reports" / "loops" / "DEMO-1" / "iteration_id_I1" / "review.latest.pack.md"
            self.assertTrue(pack_path.exists())
            pack_text = pack_path.read_text(encoding="utf-8")
            self.assertIn("schema: aidd.review_pack.v2", pack_text)
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
            write_file(root, "reports/loops/DEMO-2/iteration_id_I2.loop.pack.md", loop_pack)
            report = {"ticket": "DEMO-2", "status": "BLOCKED", "findings": []}
            write_file(root, "reports/reviewer/DEMO-2/iteration_id_I2.json", json.dumps(report, indent=2))

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

    def test_review_pack_message_fallback_and_dedupe(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_file(root, "docs/.active_ticket", "DEMO-3")
            write_file(root, "docs/.active_work_item", "iteration_id=I1")
            loop_pack = (
                "---\n"
                "schema: aidd.loop_pack.v1\n"
                "work_item_id: I1\n"
                "work_item_key: iteration_id=I1\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-3/iteration_id_I1.loop.pack.md", loop_pack)
            report = {
                "ticket": "DEMO-3",
                "status": "WARN",
                "findings": [
                    {"id": "review:F1", "severity": "major", "message": "Missing guard"},
                    {"id": "review:F1", "severity": "major", "message": "Missing guard"},
                ],
            }
            write_file(root, "reports/reviewer/DEMO-3/iteration_id_I1.json", json.dumps(report, indent=2))

            result = subprocess.run(
                cli_cmd("review-pack", "--ticket", "DEMO-3", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("verdict"), "REVISE")
            pack_path = root / "reports" / "loops" / "DEMO-3" / "iteration_id_I1" / "review.latest.pack.md"
            pack_text = pack_path.read_text(encoding="utf-8")
            self.assertIn("Missing guard", pack_text)
            top_section = pack_text.split("## Top findings", 1)[1].split("## Next actions", 1)[0]
            self.assertEqual(top_section.count("Missing guard"), 1)


if __name__ == "__main__":
    unittest.main()
