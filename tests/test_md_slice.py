import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import cli_cmd, cli_env, ensure_project_root, write_file


def _resolve_report_path(project_root: Path, value: str) -> Path:
    raw = value.strip()
    if raw.startswith("aidd/"):
        raw = raw[len("aidd/") :]
    return project_root / raw


def _slice_path_from_stdout(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("slice_path="):
            return line.split("=", 1)[1].strip()
    raise AssertionError(f"slice_path not found in stdout: {stdout}")


class MdSliceTests(unittest.TestCase):
    def test_md_slice_extracts_aidd_section(self) -> None:
        with tempfile.TemporaryDirectory(prefix="md-slice-") as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            write_file(
                project_root,
                "docs/tasklist/demo.md",
                "\n".join(
                    [
                        "# Demo",
                        "",
                        "## AIDD:CONTEXT_PACK",
                        "- ticket: demo",
                        "",
                        "## AIDD:PROGRESS_LOG",
                        "- entry one",
                        "- entry two",
                        "",
                        "## AIDD:NEXT_3",
                        "- [ ] I1",
                    ]
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd("md-slice", "--ref", "docs/tasklist/demo.md#AIDD:PROGRESS_LOG", "--ticket", "DEMO"),
                cwd=project_root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            slice_rel = _slice_path_from_stdout(result.stdout)
            slice_path = _resolve_report_path(project_root, slice_rel)
            self.assertTrue(slice_path.exists(), f"slice not created: {slice_path}")
            content = slice_path.read_text(encoding="utf-8")
            self.assertIn("schema: aidd.md_slice.v1", content)
            self.assertIn("## AIDD:PROGRESS_LOG", content)
            self.assertIn("- entry one", content)
            self.assertNotIn("## AIDD:NEXT_3", content)

    def test_md_slice_extracts_handoff_block(self) -> None:
        with tempfile.TemporaryDirectory(prefix="md-slice-") as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            write_file(
                project_root,
                "docs/tasklist/demo.md",
                "\n".join(
                    [
                        "# Demo",
                        "",
                        "## AIDD:HANDOFF_INBOX",
                        "<!-- handoff:qa start (source: aidd/reports/qa/demo.json) -->",
                        "- [ ] QA fix one",
                        "<!-- handoff:qa end -->",
                    ]
                )
                + "\n",
            )

            result = subprocess.run(
                cli_cmd("md-slice", "--ref", "docs/tasklist/demo.md@handoff:qa", "--ticket", "DEMO"),
                cwd=project_root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            slice_rel = _slice_path_from_stdout(result.stdout)
            slice_path = _resolve_report_path(project_root, slice_rel)
            self.assertTrue(slice_path.exists(), f"slice not created: {slice_path}")
            content = slice_path.read_text(encoding="utf-8")
            self.assertIn("selector: @handoff:qa", content)
            self.assertIn("handoff:qa start", content)
            self.assertIn("QA fix one", content)
            self.assertIn("handoff:qa end", content)

    def test_md_slice_fails_on_missing_selector(self) -> None:
        with tempfile.TemporaryDirectory(prefix="md-slice-") as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            write_file(project_root, "docs/tasklist/demo.md", "# Demo\n")

            result = subprocess.run(
                cli_cmd("md-slice", "--ref", "docs/tasklist/demo.md#AIDD:PROGRESS_LOG", "--ticket", "DEMO"),
                cwd=project_root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("section not found", result.stderr)

    def test_md_patch_updates_section_body(self) -> None:
        with tempfile.TemporaryDirectory(prefix="md-slice-") as tmpdir:
            project_root = ensure_project_root(Path(tmpdir))
            write_file(
                project_root,
                "docs/tasklist/demo.md",
                "\n".join(
                    [
                        "# Demo",
                        "",
                        "## AIDD:PROGRESS_LOG",
                        "- stale",
                        "",
                        "## AIDD:NEXT_3",
                        "- [ ] I1",
                    ]
                )
                + "\n",
            )
            write_file(project_root, "reports/context/new-progress.md", "- new one\n- new two\n")

            result = subprocess.run(
                cli_cmd(
                    "md-patch",
                    "--ref",
                    "docs/tasklist/demo.md#AIDD:PROGRESS_LOG",
                    "--content",
                    "reports/context/new-progress.md",
                ),
                cwd=project_root,
                env=cli_env(),
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            content = (project_root / "docs/tasklist/demo.md").read_text(encoding="utf-8")
            self.assertIn("## AIDD:PROGRESS_LOG", content)
            self.assertIn("- new one", content)
            self.assertIn("- new two", content)
            self.assertNotIn("- stale", content)


if __name__ == "__main__":
    unittest.main()
