import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from aidd_runtime import launcher
from aidd_runtime import stage_actions_run


class StageActionsRunTests(unittest.TestCase):
    def test_run_sets_docs_only_env_for_current_invocation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-actions-run-") as tmpdir:
            root = Path(tmpdir)
            context = launcher.LaunchContext(
                root=root,
                ticket="DEMO-1",
                scope_key="iteration_id_I1",
                work_item_key="iteration_id=I1",
                stage="implement",
            )
            args = Namespace(actions=None, docs_only=True)
            log_path = root / "reports" / "loops" / "DEMO-1" / "iteration_id_I1" / "run.log"
            stdout = io.StringIO()

            with (
                patch.dict(os.environ, {}, clear=False),
                patch("aidd_runtime.stage_actions_run._enforce_single_scope_guard", return_value=(True, "")),
                patch("aidd_runtime.stage_actions_run.actions_validate.main", return_value=0),
                redirect_stdout(stdout),
            ):
                os.environ.pop("AIDD_DOCS_ONLY_MODE", None)
                rc = stage_actions_run._run(args, context=context, log_path=log_path)
                env_value = os.environ.get("AIDD_DOCS_ONLY_MODE")

            self.assertEqual(rc, 0)
            self.assertEqual(env_value, "1")
            self.assertIn("docs_only_mode=1", stdout.getvalue())

    def test_single_scope_guard_blocks_cross_iteration_in_same_stage_run_lock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-actions-run-") as tmpdir:
            root = Path(tmpdir)
            lock_env = {"AIDD_STAGE_RUN_LOCK_ID": "06_implement_run1"}
            context_i1 = launcher.LaunchContext(
                root=root,
                ticket="DEMO-1",
                scope_key="iteration_id_I1",
                work_item_key="iteration_id=I1",
                stage="implement",
            )
            context_i2 = launcher.LaunchContext(
                root=root,
                ticket="DEMO-1",
                scope_key="iteration_id_I2",
                work_item_key="iteration_id=I2",
                stage="implement",
            )

            with (
                patch.dict(os.environ, lock_env, clear=False),
                patch("aidd_runtime.stage_actions_run.stage_result_runtime.main", return_value=0) as stage_result_main,
            ):
                ok_i1, diag_i1 = stage_actions_run._enforce_single_scope_guard(context_i1)
                ok_i2, diag_i2 = stage_actions_run._enforce_single_scope_guard(context_i2)

            self.assertTrue(ok_i1)
            self.assertEqual(diag_i1, "")
            self.assertFalse(ok_i2)
            self.assertIn("expected iteration_id_I1/iteration_id=I1", diag_i2)
            self.assertIn("got iteration_id_I2/iteration_id=I2", diag_i2)
            stage_result_main.assert_called_once()
            emitted_args = stage_result_main.call_args.args[0]
            self.assertIn("--reason-code", emitted_args)
            self.assertIn("seed_scope_cascade_detected", emitted_args)

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

    def test_actions_contract_diagnostics_include_supported_types_and_first_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-actions-run-") as tmpdir:
            root = Path(tmpdir)
            actions_path = root / "reports" / "actions" / "DEMO-1" / "iteration_id_I1" / "implement.actions.json"
            actions_path.parent.mkdir(parents=True, exist_ok=True)
            actions_path.write_text(
                json.dumps(
                    {
                        "schema_version": "aidd.actions.v1",
                        "stage": "implement",
                        "ticket": "DEMO-1",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "allowed_action_types": ["tasklist_ops.add_handoff_item"],
                        "actions": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            context = launcher.LaunchContext(
                root=root,
                ticket="DEMO-1",
                scope_key="iteration_id_I1",
                work_item_key="iteration_id=I1",
                stage="implement",
            )

            diagnostics = stage_actions_run._build_actions_contract_diagnostics(actions_path, context=context)

            self.assertTrue(any(line.startswith("supported_action_types=") for line in diagnostics))
            self.assertIn(
                "first_action_type_mismatch=allowed_action_types[0]='tasklist_ops.add_handoff_item':unsupported_type",
                diagnostics,
            )
            self.assertTrue(any("canonical_example_aidd_actions_v1=" in line for line in diagnostics))

    def test_canonicalize_actions_payload_rejects_non_list_actions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stage-actions-run-") as tmpdir:
            root = Path(tmpdir)
            actions_path = root / "reports" / "actions" / "DEMO-1" / "iteration_id_I1" / "implement.actions.json"
            actions_path.parent.mkdir(parents=True, exist_ok=True)
            original_payload = {
                "schema_version": "aidd.actions.v1",
                "stage": "implement",
                "ticket": "DEMO-1",
                "scope_key": "iteration_id_I1",
                "work_item_key": "iteration_id=I1",
                "allowed_action_types": ["tasklist_ops.append_progress_log"],
                "actions": {"type": "tasklist_ops.append_progress_log"},
            }
            actions_path.write_text(
                json.dumps(original_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            context = launcher.LaunchContext(
                root=root,
                ticket="DEMO-1",
                scope_key="iteration_id_I1",
                work_item_key="iteration_id=I1",
                stage="implement",
            )

            changed, reason, recovered_fields = stage_actions_run._canonicalize_actions_payload_once(
                actions_path,
                context=context,
            )

            self.assertFalse(changed)
            self.assertEqual(reason, "actions_not_list")
            self.assertEqual(recovered_fields, [])
            persisted = json.loads(actions_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted, original_payload)


if __name__ == "__main__":
    unittest.main()
