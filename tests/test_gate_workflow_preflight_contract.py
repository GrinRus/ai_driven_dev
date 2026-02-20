import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aidd_runtime import gate_workflow
from tests.helpers import REPO_ROOT, ensure_project_root, run_hook, write_active_state, write_file

DOC_PAYLOAD = '{"tool_input":{"file_path":"docs/prd/demo-checkout.prd.md"}}'


class GateWorkflowPreflightContractTests(unittest.TestCase):
    def _prepare_fallback_root(self, tmpdir: str) -> tuple[Path, str, str]:
        root = ensure_project_root(Path(tmpdir))
        ticket = "DEMO-PREFLIGHT"
        stage = "review"
        scope_key = "iteration_id_I1"
        work_item_key = "iteration_id=I1"

        write_active_state(root, ticket=ticket, stage=stage, work_item=work_item_key)
        write_file(root, "docs/.active_mode", "loop\n")

        actions_dir = root / "reports" / "actions" / ticket / scope_key
        logs_dir = root / "reports" / "logs" / stage / ticket / scope_key
        actions_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        write_file(root, f"reports/actions/{ticket}/{scope_key}/review.actions.template.json", "{}\n")
        write_file(root, f"reports/actions/{ticket}/{scope_key}/review.actions.json", "{}\n")
        write_file(root, f"reports/actions/{ticket}/{scope_key}/readmap.json", "{}\n")
        write_file(root, f"reports/actions/{ticket}/{scope_key}/writemap.json", "{}\n")
        write_file(root, f"reports/actions/{ticket}/{scope_key}/stage.preflight.result.json", "{}\n")
        write_file(root, f"reports/logs/{stage}/{ticket}/{scope_key}/wrapper.preflight.fallback.log", "ok\n")
        write_file(root, f"reports/logs/{stage}/{ticket}/{scope_key}/wrapper.run.fallback.log", "ok\n")
        write_file(root, f"reports/logs/{stage}/{ticket}/{scope_key}/wrapper.postflight.fallback.log", "ok\n")
        return root, ticket, scope_key

    def _prepare_base(
        self,
        root: Path,
        *,
        ticket: str,
        stage: str,
        scope_key: str,
        work_item_key: str,
        loop_mode: bool = True,
    ) -> None:
        write_active_state(root, ticket=ticket, stage=stage, work_item=work_item_key)
        if loop_mode:
            write_file(root, "docs/.active_mode", "loop\n")

    def _write_required_artifacts(self, root: Path, *, ticket: str, stage: str, scope_key: str) -> None:
        actions_dir = root / "reports" / "actions" / ticket / scope_key
        context_dir = root / "reports" / "context" / ticket
        loops_dir = root / "reports" / "loops" / ticket / scope_key
        logs_dir = root / "reports" / "logs" / stage / ticket / scope_key

        actions_dir.mkdir(parents=True, exist_ok=True)
        context_dir.mkdir(parents=True, exist_ok=True)
        loops_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)

        write_file(root, f"reports/actions/{ticket}/{scope_key}/{stage}.actions.template.json", '{"actions":[]}\n')
        write_file(root, f"reports/actions/{ticket}/{scope_key}/{stage}.actions.json", '{"actions":[]}\n')
        write_file(root, f"reports/context/{ticket}/{scope_key}.readmap.json", "{}\n")
        write_file(root, f"reports/context/{ticket}/{scope_key}.readmap.md", "# readmap\n")
        write_file(root, f"reports/context/{ticket}/{scope_key}.writemap.json", "{}\n")
        write_file(root, f"reports/context/{ticket}/{scope_key}.writemap.md", "# writemap\n")
        write_file(
            root,
            f"reports/loops/{ticket}/{scope_key}/stage.preflight.result.json",
            json.dumps(
                {
                    "schema": "aidd.stage_result.v1",
                    "stage": "preflight",
                    "result": "done",
                    "status": "ok",
                    "ticket": ticket,
                    "scope_key": scope_key,
                    "work_item_key": (
                        f"iteration_id={scope_key.split('iteration_id_', 1)[-1]}"
                        if scope_key.startswith("iteration_id_")
                        else ""
                    ),
                    "updated_at": "2026-01-01T00:00:00Z",
                    "details": {"target_stage": stage, "artifacts": {}},
                }
            )
            + "\n",
        )
        write_file(root, f"reports/logs/{stage}/{ticket}/{scope_key}/wrapper.preflight.test.log", "ok\n")
        write_file(root, f"reports/logs/{stage}/{ticket}/{scope_key}/wrapper.run.test.log", "ok\n")
        write_file(root, f"reports/logs/{stage}/{ticket}/{scope_key}/wrapper.postflight.test.log", "ok\n")
        write_file(
            root,
            f"reports/loops/{ticket}/{scope_key}/output.contract.json",
            json.dumps(
                {
                    "status": "ok",
                    "actions_log": f"aidd/reports/actions/{ticket}/{scope_key}/{stage}.actions.json",
                }
            )
            + "\n",
        )

    def test_fallback_preflight_artifacts_are_blocked_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root, ticket, _ = self._prepare_fallback_root(tmpdir)
            env = {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}
            with mock.patch.dict(os.environ, env, clear=False):
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, "review", "fast")
            self.assertFalse(ok)
            self.assertIn("preflight_missing", message)
            self.assertIn("reports/context", message)

    def test_fallback_preflight_artifacts_allowed_with_explicit_env(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root, ticket, _ = self._prepare_fallback_root(tmpdir)
            env = {
                "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
                "AIDD_ALLOW_FALLBACK_PREFLIGHT": "1",
            }
            with mock.patch.dict(os.environ, env, clear=False):
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, "review", "fast")
            self.assertTrue(ok)
            self.assertIn("preflight_fallback_path", message)

    def test_loop_preflight_guard_accepts_complete_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PREFLIGHT"
            stage = "implement"
            scope_key = "iteration_id_M1"
            work_item_key = "iteration_id=M1"
            self._prepare_base(root, ticket=ticket, stage=stage, scope_key=scope_key, work_item_key=work_item_key)
            self._write_required_artifacts(root, ticket=ticket, stage=stage, scope_key=scope_key)

            env_backup = os.environ.get("CLAUDE_PLUGIN_ROOT")
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            try:
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, stage, "strict")
            finally:
                if env_backup is None:
                    os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
                else:
                    os.environ["CLAUDE_PLUGIN_ROOT"] = env_backup
            self.assertTrue(ok, msg=message)
            self.assertEqual(message, "")

    def test_loop_preflight_guard_blocks_when_wrapper_logs_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PREFLIGHT"
            stage = "implement"
            scope_key = "iteration_id_M1"
            work_item_key = "iteration_id=M1"
            self._prepare_base(root, ticket=ticket, stage=stage, scope_key=scope_key, work_item_key=work_item_key)
            self._write_required_artifacts(root, ticket=ticket, stage=stage, scope_key=scope_key)

            logs_dir = root / "reports" / "logs" / stage / ticket / scope_key
            for item in logs_dir.glob("wrapper.*.log"):
                item.unlink()

            env_backup = os.environ.get("CLAUDE_PLUGIN_ROOT")
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            try:
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, stage, "strict")
            finally:
                if env_backup is None:
                    os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
                else:
                    os.environ["CLAUDE_PLUGIN_ROOT"] = env_backup
            self.assertFalse(ok)
            self.assertIn("reason_code=preflight_missing", message)

    def test_loop_preflight_guard_blocks_when_actions_log_path_missing_in_strict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PREFLIGHT"
            stage = "implement"
            scope_key = "iteration_id_M1"
            work_item_key = "iteration_id=M1"
            self._prepare_base(root, ticket=ticket, stage=stage, scope_key=scope_key, work_item_key=work_item_key)
            self._write_required_artifacts(root, ticket=ticket, stage=stage, scope_key=scope_key)

            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/output.contract.json",
                json.dumps(
                    {
                        "status": "warn",
                        "actions_log": f"aidd/reports/actions/{ticket}/{scope_key}/missing.actions.json",
                    }
                )
                + "\n",
            )

            env_backup = os.environ.get("CLAUDE_PLUGIN_ROOT")
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            try:
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, stage, "strict")
            finally:
                if env_backup is None:
                    os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
                else:
                    os.environ["CLAUDE_PLUGIN_ROOT"] = env_backup
            self.assertFalse(ok)
            self.assertIn("reason_code=actions_missing", message)

    def test_loop_preflight_guard_blocks_on_output_contract_warn_in_strict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PREFLIGHT"
            stage = "implement"
            scope_key = "iteration_id_M1"
            work_item_key = "iteration_id=M1"
            self._prepare_base(root, ticket=ticket, stage=stage, scope_key=scope_key, work_item_key=work_item_key)
            self._write_required_artifacts(root, ticket=ticket, stage=stage, scope_key=scope_key)
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/output.contract.json",
                json.dumps(
                    {
                        "status": "warn",
                        "warnings": ["read_log_missing"],
                        "actions_log": f"aidd/reports/actions/{ticket}/{scope_key}/{stage}.actions.json",
                    }
                )
                + "\n",
            )

            env_backup = os.environ.get("CLAUDE_PLUGIN_ROOT")
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            try:
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, stage, "strict")
            finally:
                if env_backup is None:
                    os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
                else:
                    os.environ["CLAUDE_PLUGIN_ROOT"] = env_backup
            self.assertFalse(ok)
            self.assertIn("reason_code=output_contract_warn", message)

    def test_loop_preflight_guard_warns_on_output_contract_warn_in_fast(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PREFLIGHT"
            stage = "implement"
            scope_key = "iteration_id_M1"
            work_item_key = "iteration_id=M1"
            self._prepare_base(root, ticket=ticket, stage=stage, scope_key=scope_key, work_item_key=work_item_key)
            self._write_required_artifacts(root, ticket=ticket, stage=stage, scope_key=scope_key)
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/output.contract.json",
                json.dumps(
                    {
                        "status": "warn",
                        "warnings": ["read_log_missing"],
                        "actions_log": f"aidd/reports/actions/{ticket}/{scope_key}/{stage}.actions.json",
                    }
                )
                + "\n",
            )

            env_backup = os.environ.get("CLAUDE_PLUGIN_ROOT")
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            try:
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, stage, "fast")
            finally:
                if env_backup is None:
                    os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
                else:
                    os.environ["CLAUDE_PLUGIN_ROOT"] = env_backup
            self.assertTrue(ok)
            self.assertIn("reason_code=output_contract_warn", message)

    def test_loop_preflight_guard_enforces_contract_without_loop_mode_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PREFLIGHT"
            stage = "implement"
            scope_key = "iteration_id_M1"
            work_item_key = "iteration_id=M1"
            self._prepare_base(
                root,
                ticket=ticket,
                stage=stage,
                scope_key=scope_key,
                work_item_key=work_item_key,
                loop_mode=False,
            )

            env_backup = os.environ.get("CLAUDE_PLUGIN_ROOT")
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            try:
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, stage, "strict")
            finally:
                if env_backup is None:
                    os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
                else:
                    os.environ["CLAUDE_PLUGIN_ROOT"] = env_backup
            self.assertFalse(ok)
            self.assertIn("reason_code=preflight_missing", message)

    def test_loop_preflight_guard_blocks_on_skip_wrappers_in_strict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PREFLIGHT"
            stage = "implement"
            scope_key = "iteration_id_M1"
            work_item_key = "iteration_id=M1"
            self._prepare_base(root, ticket=ticket, stage=stage, scope_key=scope_key, work_item_key=work_item_key)
            self._write_required_artifacts(root, ticket=ticket, stage=stage, scope_key=scope_key)

            env_backup = os.environ.get("CLAUDE_PLUGIN_ROOT")
            skip_backup = os.environ.get("AIDD_SKIP_STAGE_WRAPPERS")
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            os.environ["AIDD_SKIP_STAGE_WRAPPERS"] = "1"
            try:
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, stage, "strict")
            finally:
                if env_backup is None:
                    os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
                else:
                    os.environ["CLAUDE_PLUGIN_ROOT"] = env_backup
                if skip_backup is None:
                    os.environ.pop("AIDD_SKIP_STAGE_WRAPPERS", None)
                else:
                    os.environ["AIDD_SKIP_STAGE_WRAPPERS"] = skip_backup
            self.assertFalse(ok)
            self.assertIn("reason_code=wrappers_skipped_unsafe", message)

    def test_loop_preflight_guard_warns_on_skip_wrappers_in_fast_implement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gate-preflight-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-PREFLIGHT"
            stage = "implement"
            scope_key = "iteration_id_M1"
            work_item_key = "iteration_id=M1"
            self._prepare_base(root, ticket=ticket, stage=stage, scope_key=scope_key, work_item_key=work_item_key)
            self._write_required_artifacts(root, ticket=ticket, stage=stage, scope_key=scope_key)

            env_backup = os.environ.get("CLAUDE_PLUGIN_ROOT")
            skip_backup = os.environ.get("AIDD_SKIP_STAGE_WRAPPERS")
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
            os.environ["AIDD_SKIP_STAGE_WRAPPERS"] = "1"
            try:
                ok, message = gate_workflow._loop_preflight_guard(root, ticket, stage, "fast")
            finally:
                if env_backup is None:
                    os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
                else:
                    os.environ["CLAUDE_PLUGIN_ROOT"] = env_backup
                if skip_backup is None:
                    os.environ.pop("AIDD_SKIP_STAGE_WRAPPERS", None)
                else:
                    os.environ["AIDD_SKIP_STAGE_WRAPPERS"] = skip_backup
            self.assertTrue(ok)
            self.assertIn("reason_code=wrappers_skipped_warn", message)


if __name__ == "__main__":
    unittest.main()
