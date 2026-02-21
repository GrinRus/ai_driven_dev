import io
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from aidd_runtime import launcher
from aidd_runtime import stage_actions_run


class StageActionsRunTests(unittest.TestCase):
    def test_main_emits_launcher_reason_marker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-actions-run-") as tmpdir:
            root = Path(tmpdir)
            context = launcher.LaunchContext(
                root=root,
                ticket="DEMO-1",
                scope_key="iteration_id_I1",
                work_item_key="iteration_id=I1",
                stage="implement",
            )
            launch_result = launcher.LaunchResult(
                exit_code=launcher.RUNTIME_FAILURE_EXIT_CODE,
                wrapped_exit_code=launcher.RUNTIME_FAILURE_EXIT_CODE,
                stdout="",
                stderr="",
                log_path=root / "reports" / "logs" / "wrapper.log",
                output_limited=False,
                stdout_lines=0,
                stdout_bytes=0,
                stderr_lines=0,
                launcher_error_reason="launcher_io_enospc",
            )
            stderr = io.StringIO()
            parsed_args = Namespace(
                ticket=None,
                scope_key=None,
                work_item_key=None,
                stage=None,
                actions=None,
            )
            with (
                patch("aidd_runtime.stage_actions_run.parse_args", return_value=parsed_args),
                patch("aidd_runtime.stage_actions_run.launcher.resolve_context", return_value=context),
                patch("aidd_runtime.stage_actions_run.launcher.log_path", return_value=launch_result.log_path),
                patch("aidd_runtime.stage_actions_run.launcher.run_guarded", return_value=launch_result),
                redirect_stderr(stderr),
            ):
                code = stage_actions_run.main([], default_stage="implement", description="test")

            self.assertEqual(code, launcher.RUNTIME_FAILURE_EXIT_CODE)
            self.assertIn("reason_code=launcher_io_enospc", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
