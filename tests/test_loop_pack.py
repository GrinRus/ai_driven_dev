import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_file


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "loop_pack"


def seed_loop_pack_fixture(root: Path, ticket: str = "DEMO-1") -> None:
    tasklist = (FIXTURES / "tasklist.md").read_text(encoding="utf-8")
    write_file(root, f"docs/tasklist/{ticket}.md", tasklist)
    skills_index = (FIXTURES / "skills" / "index.yaml").read_text(encoding="utf-8")
    write_file(root, "skills/index.yaml", skills_index)
    skill = (FIXTURES / "skills" / "testing-pytest" / "SKILL.md").read_text(encoding="utf-8")
    write_file(root, "skills/testing-pytest/SKILL.md", skill)
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
            self.assertIn("src/feature/**", payload.get("boundaries", {}).get("allowed_paths", []))
            self.assertIn("testing-pytest", payload.get("skills_required", []))

            pack_path = root / "reports" / "loops" / "DEMO-1" / "iteration_id=I1.loop.pack.md"
            self.assertTrue(pack_path.exists(), "loop pack file should exist")
            active_work_item = (root / "docs" / ".active_work_item").read_text(encoding="utf-8").strip()
            self.assertEqual(active_work_item, "iteration_id=I1")

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


if __name__ == "__main__":
    unittest.main()
