import errno
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import ensure_project_root, write_active_feature, write_active_state
from aidd_runtime import launcher


class RuntimeLauncherTests(unittest.TestCase):
    def test_resolve_workflow_root_or_fallback_uses_env_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="launcher-fallback-") as tmpdir:
            root = Path(tmpdir)
            cwd = root / "outside"
            cwd.mkdir(parents=True, exist_ok=True)
            fallback = root / "fallback-logs"
            prev = os.environ.get("AIDD_WRAPPER_LOG_ROOT")
            try:
                os.environ["AIDD_WRAPPER_LOG_ROOT"] = str(fallback)
                resolved = launcher.resolve_workflow_root_or_fallback(cwd)
            finally:
                if prev is None:
                    os.environ.pop("AIDD_WRAPPER_LOG_ROOT", None)
                else:
                    os.environ["AIDD_WRAPPER_LOG_ROOT"] = prev
            self.assertEqual(resolved, fallback.resolve())
            self.assertTrue(fallback.exists())

    def test_resolve_context_uses_active_state_defaults(self) -> None:
        with tempfile.TemporaryDirectory(prefix="launcher-context-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            write_active_feature(workspace, "DEMO-1")
            write_active_state(workspace, stage="review")
            write_active_state(workspace, work_item="iteration_id=I2")

            context = launcher.resolve_context(cwd=project_root)
            self.assertEqual(context.ticket, "DEMO-1")
            self.assertEqual(context.stage, "review")
            self.assertEqual(context.work_item_key, "iteration_id=I2")
            self.assertEqual(context.scope_key, "iteration_id_I2")

    def test_log_path_and_actions_paths(self) -> None:
        with tempfile.TemporaryDirectory(prefix="launcher-paths-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            write_active_feature(workspace, "DEMO-2")
            write_active_state(workspace, stage="implement")
            write_active_state(workspace, work_item="iteration_id=I1")

            context = launcher.resolve_context(cwd=project_root)
            log = launcher.log_path(context.root, context.stage, context.ticket, context.scope_key, "run")
            self.assertIn("/reports/logs/implement/DEMO-2/iteration_id_I1/wrapper.run.", log.as_posix())
            self.assertTrue(log.parent.exists())

            paths = launcher.actions_paths(context)
            self.assertTrue(str(paths["actions_path"]).endswith("/reports/actions/DEMO-2/iteration_id_I1/implement.actions.json"))
            self.assertTrue(str(paths["preflight_result"]).endswith("/reports/loops/DEMO-2/iteration_id_I1/stage.preflight.result.json"))

    def test_run_guarded_passes_through_output_and_exit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="launcher-run-") as tmpdir:
            root = Path(tmpdir)
            log = root / "reports" / "logs" / "wrapper.log"

            def runner() -> int:
                print("hello launcher")
                return 3

            result = launcher.run_guarded(runner, log_path_value=log)
            self.assertEqual(result.exit_code, 3)
            self.assertFalse(result.output_limited)
            self.assertIn("hello launcher", result.stdout)
            log_text = log.read_text(encoding="utf-8")
            self.assertIn("[stdout]", log_text)
            self.assertIn("hello launcher", log_text)

    def test_run_guarded_enforces_output_limits(self) -> None:
        with tempfile.TemporaryDirectory(prefix="launcher-limit-") as tmpdir:
            root = Path(tmpdir)
            log = root / "reports" / "logs" / "wrapper.log"

            def runner() -> int:
                print("line")
                print("line")
                print("line")
                return 0

            result = launcher.run_guarded(
                runner,
                log_path_value=log,
                stdout_max_lines=2,
                stdout_max_bytes=1024,
                stderr_max_lines=50,
            )
            self.assertEqual(result.exit_code, launcher.OUTPUT_LIMIT_EXIT_CODE)
            self.assertTrue(result.output_limited)
            self.assertEqual(result.stdout, "")
            self.assertIn("output exceeded limits", result.stderr)
            self.assertTrue(log.exists())

    def test_run_guarded_handles_exceptions_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(prefix="launcher-error-") as tmpdir:
            root = Path(tmpdir)
            log = root / "reports" / "logs" / "wrapper.log"

            def runner() -> int:
                raise RuntimeError("boom")

            result = launcher.run_guarded(runner, log_path_value=log)
            self.assertEqual(result.exit_code, launcher.RUNTIME_FAILURE_EXIT_CODE)
            self.assertIn("boom", result.stderr)
            log_text = log.read_text(encoding="utf-8")
            self.assertIn("boom", log_text)

    def test_run_guarded_marks_enospc_launcher_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="launcher-enospc-") as tmpdir:
            root = Path(tmpdir)
            log = root / "reports" / "logs" / "wrapper.log"

            def runner() -> int:
                print("hello")
                return 0

            with patch("aidd_runtime.launcher._append_log", return_value=OSError(errno.ENOSPC, "No space left on device")):
                result = launcher.run_guarded(runner, log_path_value=log)

            self.assertEqual(result.exit_code, launcher.RUNTIME_FAILURE_EXIT_CODE)
            self.assertEqual(result.launcher_error_reason, "launcher_io_enospc")
            self.assertIn("reason_code=launcher_io_enospc", result.stderr)


if __name__ == "__main__":
    unittest.main()
