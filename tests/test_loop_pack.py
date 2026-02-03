import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_file


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "loop_pack"


def seed_loop_pack_fixture(root: Path, ticket: str = "DEMO-1") -> None:
    tasklist = (FIXTURES / "tasklist.md").read_text(encoding="utf-8")
    write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
    profile = (FIXTURES / "docs" / "architecture" / "profile.md").read_text(encoding="utf-8")
    write_file(root, "docs/architecture/profile.md", profile)


class LoopPackTests(unittest.TestCase):
    def test_loop_pack_selects_next3(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            seed_loop_pack_fixture(root)

            result = subprocess.run(
                cli_cmd("loop-pack", "--ticket", "DEMO-1", "--stage", "implement", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("work_item_id"), "I1")
            self.assertEqual(payload.get("work_item_key"), "iteration_id=I1")
            self.assertTrue(payload.get("updated_at"))
            self.assertIn("src/feature/**", payload.get("boundaries", {}).get("allowed_paths", []))
            self.assertIn("pytest -q", payload.get("commands_required", []))
            self.assertIn("pytest -q", payload.get("tests_required", []))

            pack_path = root / "reports" / "loops" / "DEMO-1" / "iteration_id=I1.loop.pack.md"
            self.assertTrue(pack_path.exists(), "loop pack file should exist")
            handoff_pack = root / "reports" / "loops" / "DEMO-1" / "id=review_F6.loop.pack.md"
            self.assertTrue(handoff_pack.exists(), "loop pack should prewarm NEXT_3 handoff items")
            pack_text = pack_path.read_text(encoding="utf-8")
            self.assertRegex(pack_text, re.compile(r"^updated_at:\s+\S+", re.MULTILINE))
            self.assertIn("DoD:", pack_text)
            self.assertIn("Boundaries:", pack_text)
            self.assertIn("Acceptance mapping:", pack_text)
            active_work_item = (root / "docs" / ".active_work_item").read_text(encoding="utf-8").strip()
            self.assertEqual(active_work_item, "iteration_id=I1")

    def test_loop_pack_skips_done_active_item(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            seed_loop_pack_fixture(root)
            tasklist_path = root / "docs" / "tasklist" / "DEMO-1.md"
            tasklist_text = tasklist_path.read_text(encoding="utf-8")
            tasklist_text = tasklist_text.replace("- [ ] I1:", "- [x] I1:", 1)
            write_file(root, "docs/tasklist/DEMO-1.md", tasklist_text)
            write_file(root, "docs/.active_ticket", "DEMO-1")
            write_file(root, "docs/.active_work_item", "iteration_id=I1")

            result = subprocess.run(
                cli_cmd("loop-pack", "--ticket", "DEMO-1", "--stage", "implement", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("selection"), "next3")
            self.assertEqual(payload.get("work_item_id"), "review:F6")
            self.assertEqual(payload.get("work_item_key"), "id=review_F6")

    def test_loop_pack_review_falls_back_to_progress(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            seed_loop_pack_fixture(root)
            write_file(root, "docs/.active_ticket", "OTHER")
            write_file(root, "docs/.active_work_item", "iteration_id=I2")

            result = subprocess.run(
                cli_cmd("loop-pack", "--ticket", "DEMO-1", "--stage", "review", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("selection"), "progress")
            self.assertEqual(payload.get("work_item_id"), "I1")

    def test_loop_pack_override_handoff(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            seed_loop_pack_fixture(root)

            result = subprocess.run(
                cli_cmd(
                    "loop-pack",
                    "--ticket",
                    "DEMO-1",
                    "--stage",
                    "implement",
                    "--work-item",
                    "id=review:F6",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("work_item_id"), "review:F6")
            self.assertEqual(payload.get("work_item_key"), "id=review_F6")

    def test_loop_pack_prefers_review_pack_on_revise(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            seed_loop_pack_fixture(root)
            review_pack = (
                "---\n"
                "schema: aidd.review_pack.v1\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: REVISE\n"
                "work_item_key: iteration_id=I1\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-1/review.latest.pack.md", review_pack)
            write_file(root, "docs/.active_ticket", "DEMO-1")
            write_file(root, "docs/.active_work_item", "iteration_id=I2")

            result = subprocess.run(
                cli_cmd("loop-pack", "--ticket", "DEMO-1", "--stage", "implement", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("work_item_id"), "I1")
            self.assertEqual(payload.get("selection"), "review-pack")

    def test_loop_pack_prefers_review_handoff_on_revise(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            seed_loop_pack_fixture(root)
            review_pack = (
                "---\n"
                "schema: aidd.review_pack.v1\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: REVISE\n"
                "work_item_key: iteration_id=I9\n"
                "---\n"
                "\n"
                "# Review Pack — DEMO-1\n"
                "\n"
                "## References\n"
                "- review_report: aidd/reports/reviewer/DEMO-1.json\n"
                "- handoff_ids:\n"
                "  - F6\n"
            )
            write_file(root, "reports/loops/DEMO-1/review.latest.pack.md", review_pack)

            result = subprocess.run(
                cli_cmd("loop-pack", "--ticket", "DEMO-1", "--stage", "implement", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("work_item_id"), "review:F6")
            self.assertEqual(payload.get("selection"), "review-handoff")

    def test_loop_pack_ignores_invalid_review_pack_schema(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-pack-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            seed_loop_pack_fixture(root)
            review_pack = (
                "---\n"
                "schema: aidd.review_pack.v0\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: REVISE\n"
                "work_item_key: iteration_id=I2\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-1/review.latest.pack.md", review_pack)

            result = subprocess.run(
                cli_cmd("loop-pack", "--ticket", "DEMO-1", "--stage", "implement", "--format", "json"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("work_item_id"), "I1")
            self.assertEqual(payload.get("selection"), "next3")


if __name__ == "__main__":
    unittest.main()
