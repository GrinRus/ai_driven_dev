from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT

sys.path.append(str(REPO_ROOT))

from tools import research_check  # noqa: E402

from .helpers import ensure_gates_config, ensure_project_root, write_active_feature, write_file, write_json


def _timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class ResearchCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _setup_workspace(self) -> tuple[Path, Path]:
        workspace = self.tmp_path / "workspace"
        workspace.mkdir()
        project_root = ensure_project_root(workspace)
        ensure_gates_config(project_root)
        return workspace, project_root

    @staticmethod
    def _make_args(workspace: Path, ticket: str) -> list[str]:
        return ["--ticket", ticket]

    def test_research_check_blocks_missing_report(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-check"
        write_active_feature(project_root, ticket)

        args = self._make_args(workspace, ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            with self.assertRaises(RuntimeError) as excinfo:
                research_check.main(args)
        finally:
            os.chdir(old_cwd)

        self.assertIn("нет отчёта Researcher", str(excinfo.exception))

    def test_research_check_passes_with_reviewed_report(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-check"
        write_active_feature(project_root, ticket)
        write_file(project_root, f"docs/research/{ticket}.md", "# Research\n\nStatus: reviewed\n")
        write_json(
            project_root,
            f"reports/research/{ticket}-targets.json",
            {"paths": ["src/main"], "docs": [f"docs/research/{ticket}.md"]},
        )
        write_json(
            project_root,
            f"reports/research/{ticket}-context.json",
            {"ticket": ticket, "generated_at": _timestamp(), "profile": {}, "auto_mode": False},
        )

        args = self._make_args(workspace, ticket)
        old_cwd = Path.cwd()
        os.chdir(workspace)
        try:
            research_check.main(args)
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
