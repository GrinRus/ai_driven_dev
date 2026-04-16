from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.helpers import REPO_ROOT


ANALYST_CHECK_PATH = REPO_ROOT / "skills" / "idea-new" / "runtime" / "analyst_check.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class IdeaNewAnalystCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module(ANALYST_CHECK_PATH, "idea_new_runtime_analyst_check")

    def test_main_syncs_index_on_success(self) -> None:
        with tempfile.TemporaryDirectory(prefix="idea-analyst-check-") as tmpdir:
            target = Path(tmpdir) / "aidd"
            target.mkdir(parents=True, exist_ok=True)
            context = SimpleNamespace(slug_hint="demo-slug", resolved_ticket="TST-001")
            summary = SimpleNamespace(status="READY", question_count=1)
            stdout = io.StringIO()

            with patch.object(self.module.runtime, "require_workflow_root", return_value=(target.parent, target)), patch.object(
                self.module.runtime,
                "require_ticket",
                return_value=("TST-001", context),
            ), patch.object(
                self.module,
                "load_settings",
                return_value={},
            ), patch.object(
                self.module,
                "validate_prd",
                return_value=summary,
            ), patch.object(
                self.module.runtime,
                "maybe_sync_index",
                return_value=None,
            ) as sync_mock, redirect_stdout(stdout):
                exit_code = self.module.main(["--ticket", "TST-001"])

        self.assertEqual(exit_code, 0)
        sync_mock.assert_called_once_with(target, "TST-001", "demo-slug", reason="idea-analyst-check")
        self.assertIn("analyst dialog ready", stdout.getvalue())

    def test_main_syncs_index_before_rethrowing_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="idea-analyst-check-") as tmpdir:
            target = Path(tmpdir) / "aidd"
            target.mkdir(parents=True, exist_ok=True)
            context = SimpleNamespace(slug_hint="demo-slug", resolved_ticket="TST-001")

            with patch.object(self.module.runtime, "require_workflow_root", return_value=(target.parent, target)), patch.object(
                self.module.runtime,
                "require_ticket",
                return_value=("TST-001", context),
            ), patch.object(
                self.module,
                "load_settings",
                return_value={},
            ), patch.object(
                self.module,
                "validate_prd",
                side_effect=self.module.AnalystValidationError("missing dialog question"),
            ), patch.object(
                self.module.runtime,
                "maybe_sync_index",
                return_value=None,
            ) as sync_mock:
                with self.assertRaises(RuntimeError) as excinfo:
                    self.module.main(["--ticket", "TST-001"])

        sync_mock.assert_called_once_with(target, "TST-001", "demo-slug", reason="idea-analyst-check")
        self.assertIn("missing dialog question", str(excinfo.exception))

    def test_main_docs_only_softens_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="idea-analyst-check-") as tmpdir:
            target = Path(tmpdir) / "aidd"
            target.mkdir(parents=True, exist_ok=True)
            context = SimpleNamespace(slug_hint="demo-slug", resolved_ticket="TST-001")
            stderr = io.StringIO()

            with patch.object(self.module.runtime, "require_workflow_root", return_value=(target.parent, target)), patch.object(
                self.module.runtime,
                "require_ticket",
                return_value=("TST-001", context),
            ), patch.object(
                self.module,
                "load_settings",
                return_value={},
            ), patch.object(
                self.module,
                "validate_prd",
                side_effect=self.module.AnalystValidationError("missing dialog question"),
            ), patch.object(
                self.module.runtime,
                "maybe_sync_index",
                return_value=None,
            ) as sync_mock, redirect_stderr(stderr):
                exit_code = self.module.main(["--ticket", "TST-001", "--docs-only"])

        self.assertEqual(exit_code, 0)
        sync_mock.assert_called_once_with(target, "TST-001", "demo-slug", reason="idea-analyst-check")
        self.assertIn("docs-only rewrite mode bypasses analyst validation blocker", stderr.getvalue())

if __name__ == "__main__":
    unittest.main()
