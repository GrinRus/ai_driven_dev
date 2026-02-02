import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_gates_config, ensure_project_root, write_file
from tools import runtime


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
            write_file(
                root,
                "reports/tests/DEMO-1/iteration_id_I1.jsonl",
                json.dumps(
                    {
                        "schema": "aidd.tests_log.v1",
                        "updated_at": "2024-01-02T00:00:00Z",
                        "ticket": "DEMO-1",
                        "stage": "review",
                        "scope_key": "iteration_id_I1",
                        "status": "pass",
                    }
                )
                + "\n",
            )

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
            self.assertEqual(payload.get("blocking_findings_count"), 0)
            self.assertEqual(payload.get("findings")[0].get("summary"), "Update tests")
            self.assertEqual(payload.get("findings")[0].get("severity"), "minor")

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

    def test_review_pack_missing_tests_revises(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "soft"})
            write_file(root, "docs/.active_ticket", "DEMO-4")
            write_file(root, "docs/.active_work_item", "iteration_id=I4")
            loop_pack = (
                "---\n"
                "schema: aidd.loop_pack.v1\n"
                "work_item_id: I4\n"
                "work_item_key: iteration_id=I4\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-4/iteration_id_I4.loop.pack.md", loop_pack)
            report = {"ticket": "DEMO-4", "status": "READY", "findings": []}
            write_file(root, "reports/reviewer/DEMO-4/iteration_id_I4.json", json.dumps(report, indent=2))

            result = subprocess.run(
                cli_cmd("review-pack", "--ticket", "DEMO-4", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("verdict"), "REVISE")
            self.assertEqual(payload.get("findings"), [])
            self.assertTrue(payload.get("fix_plan_json"))
            fix_plan_path = runtime.resolve_path_for_target(Path(payload.get("fix_plan_json")), root)
            self.assertTrue(fix_plan_path.exists())
            fix_plan_payload = json.loads(fix_plan_path.read_text(encoding="utf-8"))
            steps = fix_plan_payload.get("fix_plan", {}).get("steps", [])
            self.assertTrue(steps)
            self.assertTrue(any("test" in step.lower() for step in steps))

    def test_review_pack_skipped_tests_revises(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "soft"})
            write_file(root, "docs/.active_ticket", "DEMO-5")
            write_file(root, "docs/.active_work_item", "iteration_id=I5")
            loop_pack = (
                "---\n"
                "schema: aidd.loop_pack.v1\n"
                "work_item_id: I5\n"
                "work_item_key: iteration_id=I5\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-5/iteration_id_I5.loop.pack.md", loop_pack)
            report = {"ticket": "DEMO-5", "status": "READY", "findings": []}
            write_file(root, "reports/reviewer/DEMO-5/iteration_id_I5.json", json.dumps(report, indent=2))
            write_file(
                root,
                "reports/tests/DEMO-5/iteration_id_I5.jsonl",
                json.dumps(
                    {
                        "schema": "aidd.tests_log.v1",
                        "updated_at": "2024-01-02T00:00:00Z",
                        "ticket": "DEMO-5",
                        "stage": "review",
                        "scope_key": "iteration_id_I5",
                        "status": "skipped",
                    }
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd("review-pack", "--ticket", "DEMO-5", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("verdict"), "REVISE")
            self.assertTrue(payload.get("fix_plan_json"))
            fix_plan_path = runtime.resolve_path_for_target(Path(payload.get("fix_plan_json")), root)
            self.assertTrue(fix_plan_path.exists())

    def test_review_pack_prefers_last_pass_over_skip(self) -> None:
        with tempfile.TemporaryDirectory(prefix="review-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ensure_gates_config(root, {"tests_required": "hard"})
            write_file(root, "docs/.active_ticket", "DEMO-6")
            write_file(root, "docs/.active_work_item", "iteration_id=I6")
            loop_pack = (
                "---\n"
                "schema: aidd.loop_pack.v1\n"
                "work_item_id: I6\n"
                "work_item_key: iteration_id=I6\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-6/iteration_id_I6.loop.pack.md", loop_pack)
            report = {"ticket": "DEMO-6", "status": "READY", "findings": []}
            write_file(root, "reports/reviewer/DEMO-6/iteration_id_I6.json", json.dumps(report, indent=2))
            write_file(
                root,
                "reports/tests/DEMO-6/iteration_id_I6.jsonl",
                "\n".join(
                    [
                        json.dumps(
                            {
                                "schema": "aidd.tests_log.v1",
                                "updated_at": "2024-01-02T00:00:00Z",
                                "ticket": "DEMO-6",
                                "stage": "implement",
                                "scope_key": "iteration_id_I6",
                                "status": "pass",
                            }
                        ),
                        json.dumps(
                            {
                                "schema": "aidd.tests_log.v1",
                                "updated_at": "2024-01-03T00:00:00Z",
                                "ticket": "DEMO-6",
                                "stage": "review",
                                "scope_key": "iteration_id_I6",
                                "status": "skipped",
                            }
                        ),
                    ]
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd("review-pack", "--ticket", "DEMO-6", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("verdict"), "SHIP")

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
            findings_section = pack_text.split("## Findings", 1)[1].split("## Next actions", 1)[0]
            self.assertEqual(findings_section.count("Missing guard"), 2)


if __name__ == "__main__":
    unittest.main()
