import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, git_config_user, git_init, write_file


def write_loop_pack(root: Path, ticket: str, key: str, allowed: list[str], forbidden: list[str]) -> Path:
    lines = [
        "---",
        "schema: aidd.loop_pack.v1",
        "boundaries:",
    ]
    if allowed:
        lines.append("  allowed_paths:")
        lines.extend([f"    - {item}" for item in allowed])
    else:
        lines.append("  allowed_paths: []")
    if forbidden:
        lines.append("  forbidden_paths:")
        lines.extend([f"    - {item}" for item in forbidden])
    else:
        lines.append("  forbidden_paths: []")
    lines.append("---")
    pack_text = "\n".join(lines) + "\n"
    return write_file(root, f"reports/loops/{ticket}/{key}.loop.pack.md", pack_text)


class DiffBoundaryCheckTests(unittest.TestCase):
    def test_diff_boundary_allows_expected_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="boundary-check-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            git_init(root)
            git_config_user(root)
            write_file(root, "src/allowed/file.txt", "ok\n")
            subprocess.run(["git", "add", "src/allowed/file.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

            write_file(root, "docs/.active_ticket", "DEMO-1")
            write_file(root, "docs/.active_work_item", "iteration_id=I1")
            write_loop_pack(root, "DEMO-1", "iteration_id_I1", ["src/allowed/**"], [])

            write_file(root, "src/allowed/file.txt", "changed\n")

            result = subprocess.run(
                cli_cmd("diff-boundary-check", "--ticket", "DEMO-1"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_diff_boundary_warns_out_of_scope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="boundary-check-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            git_init(root)
            git_config_user(root)
            write_file(root, "src/allowed/file.txt", "ok\n")
            subprocess.run(["git", "add", "src/allowed/file.txt"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)

            write_file(root, "docs/.active_ticket", "DEMO-2")
            write_file(root, "docs/.active_work_item", "iteration_id=I2")
            write_loop_pack(root, "DEMO-2", "iteration_id_I2", ["src/allowed/**"], [])

            write_file(root, "src/disallowed/file.txt", "nope\n")
            subprocess.run(["git", "add", "src/disallowed/file.txt"], cwd=root, check=True)

            result = subprocess.run(
                cli_cmd("diff-boundary-check", "--ticket", "DEMO-2"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("OUT_OF_SCOPE src/disallowed/file.txt", result.stdout)

    def test_diff_boundary_empty_boundaries_warn(self) -> None:
        with tempfile.TemporaryDirectory(prefix="boundary-check-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            git_init(root)
            write_file(root, "docs/.active_ticket", "DEMO-3")
            write_file(root, "docs/.active_work_item", "iteration_id=I3")
            write_loop_pack(root, "DEMO-3", "iteration_id_I3", [], [])

            result = subprocess.run(
                cli_cmd("diff-boundary-check", "--ticket", "DEMO-3"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("NO_BOUNDARIES_DEFINED", result.stdout)

    def test_diff_boundary_ignores_dot_claude(self) -> None:
        with tempfile.TemporaryDirectory(prefix="boundary-check-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            git_init(root)
            git_config_user(root)
            write_file(root, "docs/.active_ticket", "DEMO-4")
            write_file(root, "docs/.active_work_item", "iteration_id=I4")
            write_loop_pack(root, "DEMO-4", "iteration_id_I4", ["src/allowed/**"], [])

            write_file(root, ".claude/settings.json", '{"ok": true}\n')
            subprocess.run(["git", "add", ".claude/settings.json"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=root, check=True, capture_output=True)
            write_file(root, ".claude/settings.json", '{"ok": false}\n')

            result = subprocess.run(
                cli_cmd("diff-boundary-check", "--ticket", "DEMO-4"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("OK", result.stdout)

    def test_diff_boundary_warns_untracked_out_of_scope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="boundary-check-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            git_init(root)
            git_config_user(root)
            write_file(root, "docs/.active_ticket", "DEMO-5")
            write_file(root, "docs/.active_work_item", "iteration_id=I5")
            write_loop_pack(root, "DEMO-5", "iteration_id_I5", ["src/allowed/**"], [])

            write_file(root, "src/disallowed/new.py", "print('nope')\n")

            result = subprocess.run(
                cli_cmd("diff-boundary-check", "--ticket", "DEMO-5"),
                text=True,
                capture_output=True,
                cwd=root,
                env=cli_env(),
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("OUT_OF_SCOPE src/disallowed/new.py", result.stdout)


if __name__ == "__main__":
    unittest.main()
