from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[2]))

from aidd_runtime import cli  # noqa: E402

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
    def _make_args(workspace: Path, ticket: str) -> SimpleNamespace:
        return SimpleNamespace(
            target=str(workspace),
            ticket=ticket,
            slug_hint=None,
            branch=None,
        )

    def test_research_check_blocks_missing_report(self) -> None:
        workspace, project_root = self._setup_workspace()
        ticket = "demo-check"
        write_active_feature(project_root, ticket)

        args = self._make_args(workspace, ticket)
        with self.assertRaises(RuntimeError) as excinfo:
            cli._research_check_command(args)

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
        cli._research_check_command(args)


if __name__ == "__main__":
    unittest.main()
