import json
import io
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from aidd_runtime import loop_step as loop_step_module
from tests.helpers import REPO_ROOT, cli_cmd, cli_env, ensure_project_root, write_active_state, write_file, write_json, write_tasklist_ready


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "loop_step"


def _fixture_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class LoopStepTests(unittest.TestCase):
    def _seed_stage_chain_baseline(self, root: Path, ticket: str) -> None:
        write_active_state(root, ticket=ticket)
        if not (root / "docs" / "tasklist" / f"{ticket}.md").exists():
            write_tasklist_ready(root, ticket)
        if not (root / "docs" / "prd" / f"{ticket}.prd.md").exists():
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")

    def run_loop_step(self, root: Path, ticket: str, log_path: Path, extra_env: dict | None = None, *args: str):
        self._seed_stage_chain_baseline(root, ticket)
        runner = FIXTURES / "runner.sh"
        env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(log_path)})
        if extra_env:
            env.update(extra_env)
        return subprocess.run(
            cli_cmd("loop-step", "--ticket", ticket, "--runner", f"bash {runner}", *args),
            text=True,
            capture_output=True,
            cwd=root,
            env=env,
        )

    def test_marker_semantics_scan_filters_template_backup_noise(self) -> None:
        payload = _fixture_json("tst001_stage_result_missing_diag.json")
        signal, noise = loop_step_module._scan_marker_semantics(
            [
                ("stage_result_diagnostics", str(payload.get("diag") or "")),
            ]
        )
        self.assertTrue(any("aidd/reports/loops/TST-001/iteration_id_I1/stage.implement.result.json" in item for item in signal))
        self.assertTrue(any("aidd/docs/tasklist/templates/loop.seed.md" in item for item in noise))
        self.assertTrue(any("aidd/docs/tasklist/TST-001.md.bak" in item for item in noise))
        self.assertFalse(any("aidd/docs/tasklist/templates/loop.seed.md" in item for item in signal))
        self.assertFalse(any(".bak" in item for item in signal))

    def test_loop_step_runs_implement_when_stage_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-1",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-1/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-1", log_path)
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertTrue(log_path.exists())
            log_text = log_path.read_text(encoding="utf-8")
            self.assertIn("-p /feature-dev-aidd:implement DEMO-1", log_text)
            self.assertIn("--plugin-dir", log_text)
            self.assertIn("--add-dir", log_text)
            self.assertEqual((root / "docs" / ".active_mode").read_text(encoding="utf-8").strip(), "loop")
            cli_logs = list((root / "reports" / "loops" / "DEMO-1").glob("cli.loop-step.*.log"))
            self.assertTrue(cli_logs, "cli.loop-step log should be written")

    def test_loop_step_user_approval_required_blocks_same_stage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-APPROVAL", stage="implement", work_item="iteration_id=M4")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-APPROVAL",
                "stage": "implement",
                "scope_key": "iteration_id_M4",
                "result": "continue",
                "reason_code": "user_approval_required",
                "reason": "manual approval is required",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-APPROVAL/iteration_id_M4/stage.implement.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-APPROVAL", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("stage"), "implement")
            self.assertEqual(payload.get("reason_code"), "user_approval_required")
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_loop_step_tripwire_blocks_runtime_path_missing_or_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-tripwire-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-TRIPWIRE-MISSING"
            write_active_state(root, ticket=ticket, work_item="iteration_id=I1")
            self._seed_stage_chain_baseline(root, ticket)
            runner_script = root.parent / "runner_tripwire_missing.sh"
            runner_script.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        "echo \"$*\" >> \"${AIDD_LOOP_RUNNER_LOG:?}\"",
                        "echo \"python3 skills/implement/runtime/preflight.py --ticket DEMO-TRIPWIRE-MISSING\"",
                        "echo \"can't open file '/tmp/work/skills/implement/runtime/preflight.py': [Errno 2] No such file or directory\" >&2",
                        "exit 1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            runner_script.chmod(0o755)
            log_path = root / "runner.log"
            env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(log_path)})
            result = subprocess.run(
                cli_cmd(
                    "loop-step",
                    "--ticket",
                    ticket,
                    "--runner",
                    f"bash {runner_script}",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=env,
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "runtime_path_missing_or_drift")
            self.assertEqual(payload.get("drift_tripwire_hit"), True)
            self.assertIn("can't open file", str(payload.get("reason") or ""))
            self.assertEqual(payload.get("runner_source"), "cli_arg")

    def test_loop_step_tripwire_blocks_manual_preflight_prepare_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-tripwire-manual-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-TRIPWIRE-PREFLIGHT"
            write_active_state(root, ticket=ticket, work_item="iteration_id=I1")
            self._seed_stage_chain_baseline(root, ticket)
            runner_script = root.parent / "runner_tripwire_manual.sh"
            runner_script.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        "echo \"$*\" >> \"${AIDD_LOOP_RUNNER_LOG:?}\"",
                        "echo \"$ python3 /tmp/work/skills/aidd-loop/runtime/preflight_prepare.py --ticket DEMO-TRIPWIRE-PREFLIGHT --stage qa\"",
                        "exit 0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            runner_script.chmod(0o755)
            log_path = root / "runner.log"
            env = cli_env({"AIDD_LOOP_RUNNER_LOG": str(log_path)})
            result = subprocess.run(
                cli_cmd(
                    "loop-step",
                    "--ticket",
                    ticket,
                    "--runner",
                    f"bash {runner_script}",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=env,
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "runtime_path_missing_or_drift")
            self.assertEqual(payload.get("drift_tripwire_hit"), True)
            self.assertIn("manual preflight path is forbidden", str(payload.get("reason") or ""))

    def test_loop_step_ignore_legacy_skip_flag_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-SKIP", work_item="iteration_id=I1")
            write_file(root, "reports/loops/DEMO-SKIP/iteration_id_I1/stage.implement.result.json", json.dumps(
                {
                    "schema": "aidd.stage_result.v1",
                    "ticket": "DEMO-SKIP",
                    "stage": "implement",
                    "scope_key": "iteration_id_I1",
                    "work_item_key": "iteration_id=I1",
                    "result": "continue",
                    "updated_at": "2024-01-02T00:00:00Z",
                }
            ))
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                "DEMO-SKIP",
                log_path,
                {"AIDD_HOOKS_MODE": "strict"},
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("stage"), "implement")
            self.assertEqual(payload.get("reason_code"), "output_contract_warn")
            self.assertNotIn("stage_chain_disabled", str(payload.get("reason_code") or ""))
            self.assertTrue(log_path.exists())

    def test_loop_step_blocks_on_output_contract_warn_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-wrap-strict-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-WRAP-STRICT"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": "implement",
                "scope_key": scope_key,
                "work_item_key": work_item_key,
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                ticket,
                log_path,
                {"AIDD_HOOKS_MODE": "strict"},
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "output_contract_warn")
            self.assertEqual(payload.get("output_contract_status"), "warn")
            self.assertTrue(payload.get("output_contract_path"))

    def test_loop_step_runner_with_stage_chain_produces_required_artifacts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-wrap-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-WRAP"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": "implement",
                "scope_key": scope_key,
                "work_item_key": work_item_key,
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(stage_result),
            )

            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                ticket,
                log_path,
                None,
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            payload = json.loads(result.stdout)
            actions_log_rel = str(payload.get("actions_log_path") or "")
            self.assertTrue(actions_log_rel)
            actions_log_abs = (root.parent / actions_log_rel).resolve()
            self.assertTrue(actions_log_abs.exists())

            actions_dir = root / "reports" / "actions" / ticket / scope_key
            self.assertTrue((actions_dir / "implement.actions.template.json").exists())
            self.assertTrue((actions_dir / "implement.actions.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.readmap.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.readmap.md").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.writemap.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.writemap.md").exists())
            self.assertTrue((root / "reports" / "loops" / ticket / scope_key / "stage.preflight.result.json").exists())
            stage_chain_logs = list((root / "reports" / "logs" / "implement" / ticket / scope_key).glob("stage.*.log"))
            self.assertGreaterEqual(len(stage_chain_logs), 3)

    def test_loop_step_preflight_calls_set_active_stage_with_positional_stage_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-wrap-set-stage-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-SET-STAGE"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "implement",
                        "scope_key": scope_key,
                        "work_item_key": work_item_key,
                        "result": "continue",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                ticket,
                log_path,
                None,
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            stage_chain_logs = sorted(
                (root / "reports" / "logs" / "implement" / ticket / scope_key).glob("stage.preflight.*.log")
            )
            self.assertTrue(stage_chain_logs, "expected preflight stage-chain logs")
            preflight_text = stage_chain_logs[-1].read_text(encoding="utf-8")
            set_stage_lines = [
                line
                for line in preflight_text.splitlines()
                if line.startswith("$ ") and "set_active_stage.py" in line
            ]
            self.assertTrue(set_stage_lines, "set_active_stage call must be present in preflight chain")
            command_line = set_stage_lines[0]
            self.assertIn("set_active_stage.py", command_line)
            self.assertIn(" implement", command_line)
            self.assertNotIn("--ticket", command_line)
            self.assertNotIn("--work-item", command_line)
            self.assertNotIn("--stage", command_line)

    def test_loop_step_implement_propagates_scope_env_and_forces_skip_format(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-wrap-scope-env-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-SCOPE-ENV"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "implement",
                        "scope_key": scope_key,
                        "work_item_key": work_item_key,
                        "result": "continue",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            runner_script = root.parent / "runner_scope_env.sh"
            runner_script.write_text(
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        "echo \"${TEST_SCOPE:-}\" > \"${AIDD_LOOP_SCOPE_CAPTURE:?}\"",
                        "echo \"${SKIP_FORMAT:-}\" > \"${AIDD_LOOP_SKIP_FORMAT_CAPTURE:?}\"",
                        "echo \"$*\" >> \"${AIDD_LOOP_RUNNER_LOG:?}\"",
                        "cat <<'EOF'",
                        "Status: READY",
                        "Work item key: iteration_id=I1",
                        f"Artifacts updated: aidd/docs/tasklist/{ticket}.md",
                        "Tests: profile=none",
                        "EOF",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            runner_script.chmod(0o755)

            log_path = root / "runner.log"
            scope_capture = root / "scope.capture.txt"
            skip_format_capture = root / "skip_format.capture.txt"
            env = cli_env(
                {
                    "AIDD_LOOP_RUNNER_LOG": str(log_path),
                    "AIDD_LOOP_SCOPE_CAPTURE": str(scope_capture),
                    "AIDD_LOOP_SKIP_FORMAT_CAPTURE": str(skip_format_capture),
                }
            )
            result = subprocess.run(
                cli_cmd(
                    "loop-step",
                    "--ticket",
                    ticket,
                    "--runner",
                    f"bash {runner_script}",
                    "--format",
                    "json",
                ),
                text=True,
                capture_output=True,
                cwd=root,
                env=env,
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            scope_text = scope_capture.read_text(encoding="utf-8").strip()
            self.assertIn(f"docs/tasklist/{ticket}.md", scope_text)
            self.assertEqual(skip_format_capture.read_text(encoding="utf-8").strip(), "1")

    def test_loop_step_blocks_mass_out_of_scope_diff_with_deterministic_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-wrap-diff-boundary-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-DIFF-BOUNDARY"
            scope_key = "iteration_id_I1"
            work_item_key = "iteration_id=I1"
            write_active_state(root, ticket=ticket, work_item=work_item_key)
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "implement",
                        "scope_key": scope_key,
                        "work_item_key": work_item_key,
                        "result": "continue",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Loop Step Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "loop-step@test"], cwd=root, check=True)
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "baseline"], cwd=root, check=True)
            for idx in range(0, 8):
                write_file(root, f"src/disallowed/file_{idx}.txt", "x\n")

            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                ticket,
                log_path,
                {
                    "AIDD_DIFF_BOUNDARY_MAX_OUT_OF_SCOPE": "3",
                },
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "diff_boundary_violation")
            self.assertIn("out_of_scope", str(payload.get("reason") or ""))

    def test_loop_step_runs_review_when_stage_implement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="implement")
            write_active_state(root, work_item="iteration_id=I1")
            write_tasklist_ready(root, "DEMO-2")
            write_file(root, "docs/prd/DEMO-2.prd.md", "Status: READY\n")
            write_file(root, "reports/context/DEMO-2.pack.md", "# Context pack\n\nStatus: READY\n")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-2",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "blocked",
                "reason_code": "out_of_scope_warn",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-2/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            review_pack = "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:00Z\n---\n"
            write_file(root, "reports/loops/DEMO-2/iteration_id_I1/review.latest.pack.md", review_pack)
            review_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-2",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-2/iteration_id_I1/stage.review.result.json",
                json.dumps(review_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-2", log_path, None)
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("-p /feature-dev-aidd:review DEMO-2", log_path.read_text(encoding="utf-8"))

    def test_loop_step_blocks_legacy_stage_result_schema(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="implement")
            write_active_state(root, work_item="iteration_id=I1")
            write_tasklist_ready(root, "DEMO-LEGACY")
            write_file(root, "docs/prd/DEMO-LEGACY.prd.md", "Status: READY\n")
            write_file(root, "reports/context/DEMO-LEGACY.pack.md", "# Context pack\n\nStatus: READY\n")
            stage_result = {
                "schema": "aidd.stage_result.implement.v1",
                "ticket": "DEMO-LEGACY",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "status": "ok",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-LEGACY/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-LEGACY", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "stage_result_missing_or_invalid")
            self.assertIn("invalid-schema", str(payload.get("reason") or ""))
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_loop_step_accepts_canonical_schema_version_alias(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="implement")
            write_active_state(root, work_item="iteration_id=I1")
            write_tasklist_ready(root, "DEMO-SCHEMA-VERSION")
            write_file(root, "docs/prd/DEMO-SCHEMA-VERSION.prd.md", "Status: READY\n")
            write_file(root, "reports/context/DEMO-SCHEMA-VERSION.pack.md", "# Context pack\n\nStatus: READY\n")
            stage_result = {
                "schema_version": "aidd.stage_result.v1",
                "ticket": "DEMO-SCHEMA-VERSION",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-SCHEMA-VERSION/iteration_id_I1/stage.implement.result.json",
                json.dumps(stage_result),
            )
            review_pack = "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:00Z\n---\n"
            write_file(root, "reports/loops/DEMO-SCHEMA-VERSION/iteration_id_I1/review.latest.pack.md", review_pack)
            review_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-SCHEMA-VERSION",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-SCHEMA-VERSION/iteration_id_I1/stage.review.result.json",
                json.dumps(review_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-SCHEMA-VERSION", log_path, None)
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("-p /feature-dev-aidd:review DEMO-SCHEMA-VERSION", log_path.read_text(encoding="utf-8"))

    def test_loop_step_ship_returns_done(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-3",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "done",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-3/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            review_pack = "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:00Z\n---\n"
            write_file(root, "reports/loops/DEMO-3/iteration_id_I1/review.latest.pack.md", review_pack)
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-3", log_path)
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_validate_review_pack_regens_when_stale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-STALE"
            write_active_state(root, ticket=ticket, stage="review", work_item="iteration_id=I1")
            loop_pack = (
                "---\n"
                "schema: aidd.loop_pack.v1\n"
                "updated_at: 2024-01-01T00:00:00Z\n"
                f"ticket: {ticket}\n"
                "work_item_id: I1\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n"
            )
            write_file(root, f"reports/loops/{ticket}/iteration_id_I1.loop.pack.md", loop_pack)
            review_report = {
                "schema": "aidd.review_report.v1",
                "updated_at": "2024-01-03T00:00:00Z",
                "ticket": ticket,
                "scope_key": "iteration_id_I1",
                "work_item_key": "iteration_id=I1",
                "status": "READY",
                "findings": [],
            }
            write_file(
                root,
                f"reports/reviewer/{ticket}/iteration_id_I1.json",
                json.dumps(review_report),
            )
            stale_pack = (
                "---\n"
                "schema: aidd.review_pack.v2\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: SHIP\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n"
            )
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1/review.latest.pack.md",
                stale_pack,
            )
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                ok, message, code = loop_step_module.validate_review_pack(
                    root,
                    ticket=ticket,
                    slug_hint=ticket,
                    scope_key="iteration_id_I1",
                )
            finally:
                os.chdir(cwd)
            self.assertTrue(ok, msg=f"{code}: {message}")

    def test_loop_step_blocked_without_review_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-4", log_path)
            self.assertEqual(result.returncode, 20, msg=result.stderr)

    def test_loop_step_revise_runs_implement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-6",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-6/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            review_pack = (
                "---\n"
                "schema: aidd.review_pack.v2\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: REVISE\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-6/iteration_id_I1/review.latest.pack.md", review_pack)
            fix_plan = {
                "schema": "aidd.review_fix_plan.v1",
                "updated_at": "2024-01-02T00:00:00Z",
                "ticket": "DEMO-6",
                "work_item_key": "iteration_id=I1",
                "scope_key": "iteration_id_I1",
                "fix_plan": {
                    "steps": ["Fix review:F1"],
                    "commands": [],
                    "tests": ["see AIDD:TEST_EXECUTION"],
                    "expected_paths": ["src/**"],
                    "acceptance_check": "Blocking findings resolved: review:F1",
                    "links": [],
                    "fixes": ["review:F1"],
                },
            }
            write_file(
                root,
                "reports/loops/DEMO-6/iteration_id_I1/review.fix_plan.json",
                json.dumps(fix_plan),
            )
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-6",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-6/iteration_id_I1/stage.implement.result.json",
                json.dumps(implement_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-6", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("-p /feature-dev-aidd:implement DEMO-6", log_path.read_text(encoding="utf-8"))
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("scope_key"), "iteration_id_I1")

    def test_loop_step_review_blocking_findings_continues_to_implement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-6F",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "blocked",
                "reason_code": "blocking_findings",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-6F/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            review_pack = (
                "---\n"
                "schema: aidd.review_pack.v2\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: REVISE\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-6F/iteration_id_I1/review.latest.pack.md", review_pack)
            fix_plan = {
                "schema": "aidd.review_fix_plan.v1",
                "updated_at": "2024-01-02T00:00:00Z",
                "ticket": "DEMO-6F",
                "work_item_key": "iteration_id=I1",
                "scope_key": "iteration_id_I1",
                "fix_plan": {
                    "steps": ["Fix review:F1"],
                    "commands": [],
                    "tests": ["see AIDD:TEST_EXECUTION"],
                    "expected_paths": ["src/**"],
                    "acceptance_check": "Blocking findings resolved: review:F1",
                    "links": [],
                    "fixes": ["review:F1"],
                },
            }
            write_file(
                root,
                "reports/loops/DEMO-6F/iteration_id_I1/review.fix_plan.json",
                json.dumps(fix_plan),
            )
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-6F",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-6F/iteration_id_I1/stage.implement.result.json",
                json.dumps(implement_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-6F", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("-p /feature-dev-aidd:implement DEMO-6F", log_path.read_text(encoding="utf-8"))
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("scope_key"), "iteration_id_I1")

    def test_loop_step_blocks_when_fix_plan_missing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-7",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-7/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            review_pack = (
                "---\n"
                "schema: aidd.review_pack.v2\n"
                "updated_at: 2024-01-02T00:00:00Z\n"
                "verdict: REVISE\n"
                "work_item_key: iteration_id=I1\n"
                "scope_key: iteration_id_I1\n"
                "---\n"
            )
            write_file(root, "reports/loops/DEMO-7/iteration_id_I1/review.latest.pack.md", review_pack)

            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-7", log_path)
            self.assertEqual(result.returncode, 20, msg=result.stderr)

    def test_loop_step_blocks_on_stale_review_pack(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v0",
                "ticket": "DEMO-5",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "done",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-5/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"

            result = self.run_loop_step(root, "DEMO-5", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "stage_result_missing_or_invalid")
            self.assertIn("invalid-schema", str(payload.get("reason") or ""))
            self.assertIn("stage.review.result.json", str(payload.get("reason") or ""))
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_loop_step_blocks_on_invalid_schema_version_alias(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema_version": "aidd.stage_result.v0",
                "ticket": "DEMO-SCHEMA-ALIAS-BLOCK",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "result": "done",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-SCHEMA-ALIAS-BLOCK/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-SCHEMA-ALIAS-BLOCK", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "stage_result_missing_or_invalid")
            self.assertIn("invalid-schema", str(payload.get("reason") or ""))
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_loop_step_blocks_on_legacy_stage_result_unknown_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.review.v1",
                "ticket": "DEMO-LEGACY-BLOCK",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "status": "mystery",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-LEGACY-BLOCK/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-LEGACY-BLOCK", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "stage_result_missing_or_invalid")
            self.assertIn("invalid-schema", str(payload.get("reason") or ""))
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_loop_step_blocks_on_canonical_stage_result_without_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="review")
            write_active_state(root, work_item="iteration_id=I1")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-CAN-BLOCK",
                "stage": "review",
                "scope_key": "iteration_id_I1",
                "status": "ok",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-CAN-BLOCK/iteration_id_I1/stage.review.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-CAN-BLOCK", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "stage_result_missing_or_invalid")
            self.assertIn("invalid-result", str(payload.get("reason") or ""))
            if log_path.exists():
                self.assertEqual(log_path.read_text(encoding="utf-8").strip(), "")

    def test_loop_step_blocks_on_qa_without_repair(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="qa", work_item="iteration_id=I1")
            write_active_state(root, ticket="DEMO-QA")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA",
                "stage": "qa",
                "scope_key": "iteration_id_I1",
                "work_item_key": "iteration_id=I1",
                "result": "blocked",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA/iteration_id_I1/stage.qa.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-QA", log_path)
            self.assertEqual(result.returncode, 20, msg=result.stderr)

    def test_loop_step_qa_repair_with_work_item(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="qa", work_item="iteration_id=I2")
            write_active_state(root, ticket="DEMO-QA2")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA2",
                "stage": "qa",
                "scope_key": "iteration_id_I2",
                "work_item_key": "iteration_id=I2",
                "result": "blocked",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA2/iteration_id_I2/stage.qa.result.json",
                json.dumps(stage_result),
            )
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA2",
                "stage": "implement",
                "scope_key": "iteration_id_I2",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA2/iteration_id_I2/stage.implement.result.json",
                json.dumps(implement_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                "DEMO-QA2",
                log_path,
                None,
                "--from-qa",
                "--work-item-key",
                "iteration_id=I2",
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("-p /feature-dev-aidd:implement DEMO-QA2", log_path.read_text(encoding="utf-8"))
            active_payload = json.loads((root / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(active_payload.get("stage"), "implement")
            self.assertEqual(active_payload.get("work_item"), "iteration_id=I2")

    def test_loop_step_qa_repair_auto_select_blocks_on_multiple(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="qa", work_item="iteration_id=I2")
            write_active_state(root, ticket="DEMO-QA3")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA3",
                "stage": "qa",
                "scope_key": "iteration_id_I2",
                "work_item_key": "iteration_id=I2",
                "result": "blocked",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA3/iteration_id_I2/stage.qa.result.json",
                json.dumps(stage_result),
            )
            tasklist = """<!-- handoff:qa start -->
- [ ] Fix A (id: qa:A1) (Priority: high) (Blocking: true) (scope: iteration_id=I2)
- [ ] Fix B (id: qa:A2) (Priority: high) (Blocking: true) (scope: iteration_id=I3)
<!-- handoff:qa end -->
"""
            write_file(root, "docs/tasklist/DEMO-QA3.md", tasklist)
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                "DEMO-QA3",
                log_path,
                None,
                "--from-qa",
                "auto",
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("reason_code"), "qa_repair_multiple_handoffs")

    def test_loop_step_qa_stage_result_rejects_ticket_scope_in_iteration_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="qa", work_item="iteration_id=I2")
            write_active_state(root, ticket="DEMO-QA-SCOPE-BLOCK")
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA-SCOPE-BLOCK",
                "stage": "qa",
                "scope_key": "DEMO-QA-SCOPE-BLOCK",
                "result": "blocked",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA-SCOPE-BLOCK/DEMO-QA-SCOPE-BLOCK/stage.qa.result.json",
                json.dumps(stage_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                "DEMO-QA-SCOPE-BLOCK",
                log_path,
                None,
                "--from-qa",
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("reason_code"), "stage_result_missing_or_invalid")
            self.assertIn("scope_shape_invalid", str(payload.get("reason") or ""))

    def test_loop_step_qa_repair_auto_config(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="qa", work_item="iteration_id=I1")
            write_active_state(root, ticket="DEMO-QA4")
            write_json(root, "config/gates.json", {"loop": {"auto_repair_from_qa": True}})
            stage_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA4",
                "stage": "qa",
                "scope_key": "iteration_id_I1",
                "work_item_key": "iteration_id=I1",
                "result": "blocked",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA4/iteration_id_I1/stage.qa.result.json",
                json.dumps(stage_result),
            )
            write_tasklist_ready(root, "DEMO-QA4")
            tasklist_path = root / "docs" / "tasklist" / "DEMO-QA4.md"
            tasklist = tasklist_path.read_text(encoding="utf-8")
            tasklist_path.write_text(
                tasklist
                + "\n<!-- handoff:qa start -->\n"
                + "- [ ] Fix A (id: qa:A1) (Priority: high) (Blocking: true) (scope: iteration_id=I1)\n"
                + "<!-- handoff:qa end -->\n",
                encoding="utf-8",
            )
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-QA4",
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-QA4/iteration_id_I1/stage.implement.result.json",
                json.dumps(implement_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-QA4", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            self.assertIn("-p /feature-dev-aidd:implement DEMO-QA4", log_path.read_text(encoding="utf-8"))

    def test_loop_step_wires_stage_runtime_chain(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-WRAP"
            scope_key = "iteration_id_I1"
            write_active_state(root, work_item="iteration_id=I1")
            write_tasklist_ready(root, ticket)
            write_file(root, f"docs/prd/{ticket}.prd.md", "Status: READY\n")
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": "implement",
                "scope_key": scope_key,
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                f"reports/loops/{ticket}/{scope_key}/stage.implement.result.json",
                json.dumps(implement_result),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                ticket,
                log_path,
                None,
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload.get("actions_log_path"))
            self.assertTrue((root / "reports" / "actions" / ticket / scope_key / "implement.actions.template.json").exists())
            self.assertTrue((root / "reports" / "actions" / ticket / scope_key / "implement.actions.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.readmap.json").exists())
            self.assertTrue((root / "reports" / "context" / ticket / f"{scope_key}.writemap.json").exists())
            self.assertTrue((root / "reports" / "loops" / ticket / scope_key / "stage.preflight.result.json").exists())
            self.assertTrue(payload.get("stage_chain_logs"))

    def test_loop_step_blocks_invalid_loop_work_item_key(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, stage="implement")
            write_active_state(root, work_item="id=review:report-1")
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-BAD-WORK", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "blocked")
            self.assertTrue(payload.get("reason"))
            self.assertEqual(payload.get("reason_code"), "invalid_work_item_key")
            self.assertTrue(payload.get("scope_key"))
            self.assertTrue(payload.get("stage_result_path"))
            self.assertTrue(payload.get("cli_log_path"))
            self.assertTrue(payload.get("runner"))
            self.assertTrue(payload.get("runner_effective"))
            self.assertIn("runner.sh", str(payload.get("runner")))
            self.assertIn("runner.sh", str(payload.get("runner_effective")))
            self.assertTrue(payload.get("log_path"))

    def test_loop_step_recovers_non_loop_stage_with_iteration_work_item(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-STAGE-RECOVER"
            write_active_state(root, ticket=ticket, stage="tasklist", work_item="iteration_id=I3")
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I3/stage.implement.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "implement",
                        "scope_key": "iteration_id_I3",
                        "result": "continue",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(root, ticket, log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("stage"), "implement")
            self.assertEqual(payload.get("repair_reason_code"), "non_loop_stage_recovered")
            self.assertEqual(payload.get("repair_scope_key"), "iteration_id_I3")
            active_payload = json.loads((root / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(active_payload.get("stage"), "implement")

    def test_loop_step_blocks_non_loop_stage_recovery_when_work_item_invalid(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-STAGE-BLOCK", stage="tasklist", work_item="id=review:seed")
            log_path = root / "runner.log"
            result = self.run_loop_step(root, "DEMO-STAGE-BLOCK", log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 20, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("reason_code"), "invalid_work_item_key")
            self.assertIn("cannot recover from active stage", str(payload.get("reason") or ""))

    def test_stage_chain_contract_requires_stage_result_and_stage_chain_logs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-contract-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-CONTRACT"
            scope_key = "iteration_id_I1"
            stage = "implement"
            base_actions = root / "reports" / "actions" / ticket / scope_key
            base_context = root / "reports" / "context" / ticket
            base_loops = root / "reports" / "loops" / ticket / scope_key
            base_logs = root / "reports" / "logs" / stage / ticket / scope_key

            write_file(root, f"reports/actions/{ticket}/{scope_key}/{stage}.actions.template.json", "{}")
            write_file(root, f"reports/actions/{ticket}/{scope_key}/{stage}.actions.json", "{}")
            write_file(root, f"reports/context/{ticket}/{scope_key}.readmap.json", "{}")
            write_file(root, f"reports/context/{ticket}/{scope_key}.readmap.md", "# readmap\n")
            write_file(root, f"reports/context/{ticket}/{scope_key}.writemap.json", "{}")
            write_file(root, f"reports/context/{ticket}/{scope_key}.writemap.md", "# writemap\n")
            write_file(root, f"reports/loops/{ticket}/{scope_key}/stage.preflight.result.json", "{}")
            write_file(root, f"reports/logs/{stage}/{ticket}/{scope_key}/stage.preflight.20240101T000000Z.log", "ok\n")

            ok, message, code = loop_step_module._validate_stage_chain_contract(
                target=root,
                ticket=ticket,
                scope_key=scope_key,
                stage=stage,
                actions_log_rel=f"aidd/reports/actions/{ticket}/{scope_key}/{stage}.actions.json",
            )
            self.assertFalse(ok)
            self.assertEqual(code, "stage_chain_output_missing")
            self.assertIn("stage.implement.result.json", message)
            self.assertIn("stage.run", message)
            self.assertIn("stage.postflight", message)
            self.assertTrue(base_actions.exists())
            self.assertTrue(base_context.exists())
            self.assertTrue(base_loops.exists())
            self.assertTrue(base_logs.exists())

    def test_loop_step_missing_stage_result_after_stage_chain_uses_stage_chain_output_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-stage-chain-output-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-WRAPPER-OUTPUT"
            write_active_state(root, ticket=ticket, work_item="iteration_id=I1")
            fake_stage_result_path = root / "reports" / "loops" / ticket / "iteration_id_I1" / "stage.implement.result.json"
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_step.validate_command_available", return_value=(True, "", "")):
                        with patch("aidd_runtime.loop_step.resolve_runner", return_value=(["fake-runner"], "fake-runner", "")):
                            with patch("aidd_runtime.loop_step.should_run_stage_chain", return_value=True):
                                with patch(
                                    "aidd_runtime.loop_step.run_stage_chain",
                                    return_value=(
                                        True,
                                        {
                                            "log_path": (
                                                "aidd/reports/logs/implement/"
                                                f"{ticket}/iteration_id_I1/stage.preflight.log"
                                            )
                                        },
                                        "",
                                    ),
                                ):
                                    with patch("aidd_runtime.loop_step.run_command", return_value=0):
                                        with patch(
                                            "aidd_runtime.loop_step.load_stage_result",
                                            return_value=(
                                                None,
                                                fake_stage_result_path,
                                                "stage_result_missing_or_invalid",
                                                "",
                                                "",
                                                "candidates=none",
                                            ),
                                        ):
                                            with redirect_stdout(captured):
                                                code = loop_step_module.main(["--ticket", ticket, "--format", "json"])
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "stage_chain_output_missing")
            self.assertIn("stage-chain run completed without canonical stage-result emission", str(payload.get("reason") or ""))
            self.assertEqual(payload.get("active_stage_after"), "implement")
            self.assertEqual(payload.get("active_stage_sync_applied"), True)

    def test_loop_step_tst001_fixture_stale_stage_missing_stage_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-stage-chain-output-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "TST001-WRAPPER-OUTPUT"
            write_active_state(root, ticket=ticket, stage="idea", work_item="iteration_id=I1")
            fixture = _fixture_json("tst001_stage_result_missing_diag.json")
            fake_stage_result_path = root / "reports" / "loops" / ticket / "iteration_id_I1" / "stage.implement.result.json"
            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_step.validate_command_available", return_value=(True, "", "")):
                        with patch("aidd_runtime.loop_step.resolve_runner", return_value=(["fake-runner"], "fake-runner", "")):
                            with patch("aidd_runtime.loop_step.should_run_stage_chain", return_value=True):
                                with patch(
                                    "aidd_runtime.loop_step.run_stage_chain",
                                    return_value=(
                                        True,
                                        {
                                            "log_path": (
                                                "aidd/reports/logs/implement/"
                                                f"{ticket}/iteration_id_I1/stage.preflight.log"
                                            )
                                        },
                                        "",
                                    ),
                                ):
                                    with patch("aidd_runtime.loop_step.run_command", return_value=0):
                                        with patch(
                                            "aidd_runtime.loop_step.load_stage_result",
                                            return_value=(
                                                None,
                                                fake_stage_result_path,
                                                str(fixture.get("error") or "stage_result_missing_or_invalid"),
                                                "",
                                                "",
                                                str(fixture.get("diag") or "candidates=none"),
                                            ),
                                        ):
                                            with redirect_stdout(captured):
                                                code = loop_step_module.main(["--ticket", ticket, "--format", "json"])
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "stage_chain_output_missing")
            self.assertEqual(payload.get("repair_reason_code"), "non_loop_stage_recovered")
            self.assertEqual(payload.get("active_stage_before"), "implement")
            self.assertEqual(payload.get("active_stage_after"), "implement")
            self.assertEqual(payload.get("active_stage_sync_applied"), False)
            self.assertTrue(payload.get("report_noise_events"))
            self.assertTrue(payload.get("marker_signal_events"))

    def test_loop_step_recovers_scope_from_stage_result(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, work_item="iteration_id=I2")
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-MISMATCH",
                "stage": "implement",
                "scope_key": "iteration_id_I4",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            review_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-MISMATCH",
                "stage": "review",
                "scope_key": "iteration_id_I4",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:01Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-MISMATCH/iteration_id_I4/stage.implement.result.json",
                json.dumps(implement_result),
            )
            write_file(
                root,
                "reports/loops/DEMO-MISMATCH/iteration_id_I4/stage.review.result.json",
                json.dumps(review_result),
            )
            write_file(
                root,
                "reports/loops/DEMO-MISMATCH/iteration_id_I4/review.latest.pack.md",
                "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:01Z\n---\n",
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                "DEMO-MISMATCH",
                log_path,
                None,
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("scope_key"), "iteration_id_I4")
            self.assertEqual(payload.get("scope_key_mismatch_warn"), "1")

    def test_loop_step_realigns_actions_log_scope_on_mismatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, work_item="iteration_id=I2")
            write_tasklist_ready(root, "DEMO-ACTIONS-MISMATCH")
            write_file(root, "docs/prd/DEMO-ACTIONS-MISMATCH.prd.md", "Status: READY\n")
            implement_result = {
                "schema": "aidd.stage_result.v1",
                "ticket": "DEMO-ACTIONS-MISMATCH",
                "stage": "implement",
                "scope_key": "iteration_id_I4",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            write_file(
                root,
                "reports/loops/DEMO-ACTIONS-MISMATCH/iteration_id_I4/stage.implement.result.json",
                json.dumps(implement_result),
            )
            write_file(
                root,
                "reports/actions/DEMO-ACTIONS-MISMATCH/iteration_id_I4/implement.actions.json",
                '{"schema_version":"aidd.actions.v1","stage":"implement","ticket":"DEMO-ACTIONS-MISMATCH","scope_key":"iteration_id_I4","work_item_key":"iteration_id=I4","allowed_action_types":[],"actions":[]}',
            )
            log_path = root / "runner.log"
            result = self.run_loop_step(
                root,
                "DEMO-ACTIONS-MISMATCH",
                log_path,
                None,
                "--format",
                "json",
            )
            self.assertEqual(result.returncode, 10, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("scope_key"), "iteration_id_I4")
            self.assertEqual(payload.get("scope_key_mismatch_warn"), "1")
            self.assertEqual(
                payload.get("actions_log_path"),
                "aidd/reports/actions/DEMO-ACTIONS-MISMATCH/iteration_id_I4/implement.actions.json",
            )

    def test_load_stage_result_prefers_canonical_scope_candidate_over_alias(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-SCOPE-PREFERENCE"
            stage = "review"
            canonical_payload = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": stage,
                "scope_key": "iteration_id_I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:00Z",
            }
            alias_payload = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": stage,
                "scope_key": "I1",
                "result": "continue",
                "updated_at": "2024-01-02T00:00:01Z",
            }
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1/stage.{stage}.result.json",
                json.dumps(canonical_payload),
            )
            write_file(
                root,
                f"reports/loops/{ticket}/I1/stage.{stage}.result.json",
                json.dumps(alias_payload),
            )

            payload, selected_path, error, mismatch_from, mismatch_to, diag = loop_step_module.load_stage_result(
                root,
                ticket,
                "iteration_id_I2",
                stage,
            )

            self.assertEqual(error, "")
            self.assertTrue(selected_path.as_posix().endswith("/iteration_id_I1/stage.review.result.json"))
            self.assertEqual(str((payload or {}).get("scope_key")), "iteration_id_I1")
            self.assertEqual(mismatch_from, "iteration_id_I2")
            self.assertEqual(mismatch_to, "iteration_id_I1")
            self.assertIn("fallback:selected:", diag)

    def test_load_stage_result_diagnostics_include_preferred_and_fallback_reasons(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-DIAG-DETAILS"
            stage = "review"
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1/stage.{stage}.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": stage,
                        "scope_key": "iteration_id_I1",
                        "status": "ok",
                    }
                ),
            )
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I2/stage.{stage}.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.review.v0",
                        "ticket": ticket,
                        "stage": stage,
                        "scope_key": "iteration_id_I2",
                        "status": "ok",
                    }
                ),
            )

            payload, selected_path, error, _mismatch_from, _mismatch_to, diag = loop_step_module.load_stage_result(
                root,
                ticket,
                "iteration_id_I1",
                stage,
            )

            self.assertIsNone(payload)
            self.assertTrue(selected_path.as_posix().endswith("/iteration_id_I1/stage.review.result.json"))
            self.assertEqual(error, "stage_result_missing_or_invalid")
            self.assertIn("preferred:candidate:", diag)
            self.assertIn("invalid-result", diag)
            self.assertIn("fallback:candidate:", diag)
            self.assertIn("invalid-schema", diag)

    def test_load_stage_result_ignores_cross_scope_blocked_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-SCOPE-BLOCKED-FALLBACK"
            stage = "review"
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1/stage.{stage}.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": stage,
                        "scope_key": "iteration_id_I1",
                        "result": "blocked",
                        "reason_code": "stage_result_blocked",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )

            payload, selected_path, error, mismatch_from, mismatch_to, diag = loop_step_module.load_stage_result(
                root,
                ticket,
                "iteration_id_I9",
                stage,
            )

            self.assertIsNone(payload)
            self.assertTrue(selected_path.as_posix().endswith("/iteration_id_I9/stage.review.result.json"))
            self.assertEqual(error, "stage_result_missing_or_invalid")
            self.assertEqual(mismatch_from, "")
            self.assertEqual(mismatch_to, "")
            self.assertIn("scope_fallback_stale_ignored=iteration_id_I1", diag)

    def test_loop_step_uses_requested_result_for_soft_blocked_review(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-REQUESTED-RESULT"
            write_active_state(root, ticket=ticket, stage="review", work_item="iteration_id=I1")
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1/stage.review.result.json",
                json.dumps(
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "review",
                        "scope_key": "iteration_id_I1",
                        "result": "blocked",
                        "requested_result": "done",
                        "reason_code": "output_contract_warn",
                        "reason": "soft downgrade",
                        "updated_at": "2024-01-02T00:00:00Z",
                    }
                ),
            )
            write_file(
                root,
                f"reports/loops/{ticket}/iteration_id_I1/review.latest.pack.md",
                "---\nschema: aidd.review_pack.v2\nupdated_at: 2024-01-02T00:00:00Z\n---\n",
            )

            log_path = root / "runner.log"
            result = self.run_loop_step(root, ticket, log_path, None, "--format", "json")
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload.get("status"), "done")
            self.assertEqual(payload.get("stage_requested_result"), "done")
            self.assertIn("requested_result=done", str(payload.get("stage_result_diagnostics") or ""))

    def test_extract_stage_chain_reason_code_qa_stage_result_emit_failed(self) -> None:
        code = loop_step_module._extract_stage_chain_reason_code(
            "run stage-chain failed: reason_code=qa_stage_result_emit_failed stage-result write failed",
            "stage_result_missing",
        )
        self.assertEqual(code, "qa_stage_result_emit_failed")

    def test_loop_step_blocks_when_runner_missing_noninteractive_permissions_flag(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            write_active_state(root, ticket="DEMO-PERM-GUARD", work_item="iteration_id=I1")

            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(
                    os.environ,
                    {
                        "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
                    },
                    clear=False,
                ):
                    with patch(
                        "aidd_runtime.loop_step.resolve_runner",
                        return_value=(["claude"], "claude", "runner missing --dangerously-skip-permissions support"),
                    ):
                        with redirect_stdout(captured):
                            code = loop_step_module.main(
                                ["--ticket", "DEMO-PERM-GUARD", "--format", "json"]
                            )
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "loop_runner_permissions")
            self.assertIn("non-interactive permissions", str(payload.get("reason") or ""))

    def test_loop_step_auto_retries_question_block_with_compact_answers(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-question-retry-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-QUESTION-RETRY"
            write_active_state(root, ticket=ticket, work_item="iteration_id=I1")

            fake_stage_result_path = root / "reports" / "loops" / ticket / "iteration_id_I1" / "stage.implement.result.json"
            commands: list[list[str]] = []

            def _fake_run_command(command: list[str], cwd: Path, log_path: Path, env: dict | None = None) -> int:
                _ = cwd, env
                commands.append(list(command))
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text(
                    "Вопрос 1 (Blocker): выбрать профиль\n"
                    "Options: A) strict B) fast C) mixed\n"
                    "Default: B\n",
                    encoding="utf-8",
                )
                return 0

            load_results = [
                (
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "implement",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "result": "blocked",
                        "reason_code": "answers_required",
                        "reason": "Вопрос 1: требуется AIDD:ANSWERS",
                    },
                    fake_stage_result_path,
                    "",
                    "",
                    "",
                    "",
                ),
                (
                    {
                        "schema": "aidd.stage_result.v1",
                        "ticket": ticket,
                        "stage": "implement",
                        "scope_key": "iteration_id_I1",
                        "work_item_key": "iteration_id=I1",
                        "result": "continue",
                        "reason_code": "",
                        "reason": "",
                    },
                    fake_stage_result_path,
                    "",
                    "",
                    "",
                    "",
                ),
            ]

            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_step.validate_command_available", return_value=(True, "", "")):
                        with patch("aidd_runtime.loop_step.resolve_runner", return_value=(["fake-runner"], "fake-runner", "")):
                            with patch("aidd_runtime.loop_step.should_run_stage_chain", return_value=False):
                                with patch("aidd_runtime.loop_step.run_command", side_effect=_fake_run_command):
                                    with patch("aidd_runtime.loop_step.load_stage_result", side_effect=load_results):
                                        with redirect_stdout(captured):
                                            code = loop_step_module.main(["--ticket", ticket, "--format", "json"])
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 10)
            self.assertEqual(len(commands), 2)
            self.assertIn("AIDD:ANSWERS", " ".join(commands[1]))
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "continue")
            self.assertEqual(payload.get("question_retry_attempt"), 1)
            self.assertEqual(payload.get("question_retry_applied"), True)
            self.assertEqual(payload.get("question_answers"), "AIDD:ANSWERS Q1=B")
            self.assertTrue(payload.get("question_questions_path"))
            self.assertTrue(payload.get("question_answers_path"))

    def test_loop_step_question_retry_second_block_is_prompt_flow_blocker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="loop-step-question-retry-block-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            ticket = "DEMO-QUESTION-BLOCK"
            write_active_state(root, ticket=ticket, work_item="iteration_id=I1")

            fake_stage_result_path = root / "reports" / "loops" / ticket / "iteration_id_I1" / "stage.implement.result.json"
            commands: list[list[str]] = []

            def _fake_run_command(command: list[str], cwd: Path, log_path: Path, env: dict | None = None) -> int:
                _ = cwd, env
                commands.append(list(command))
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_path.write_text("Question 1: need AIDD:ANSWERS\n", encoding="utf-8")
                return 0

            blocked_payload = {
                "schema": "aidd.stage_result.v1",
                "ticket": ticket,
                "stage": "implement",
                "scope_key": "iteration_id_I1",
                "work_item_key": "iteration_id=I1",
                "result": "blocked",
                "reason_code": "answers_required",
                "reason": "Question 1 requires AIDD:ANSWERS",
            }
            load_results = [
                (blocked_payload, fake_stage_result_path, "", "", "", ""),
                (blocked_payload, fake_stage_result_path, "", "", "", ""),
            ]

            captured = io.StringIO()
            cwd = os.getcwd()
            try:
                os.chdir(root.parent)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)}, clear=False):
                    with patch("aidd_runtime.loop_step.validate_command_available", return_value=(True, "", "")):
                        with patch("aidd_runtime.loop_step.resolve_runner", return_value=(["fake-runner"], "fake-runner", "")):
                            with patch("aidd_runtime.loop_step.should_run_stage_chain", return_value=False):
                                with patch("aidd_runtime.loop_step.run_command", side_effect=_fake_run_command):
                                    with patch("aidd_runtime.loop_step.load_stage_result", side_effect=load_results):
                                        with redirect_stdout(captured):
                                            code = loop_step_module.main(["--ticket", ticket, "--format", "json"])
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 20)
            self.assertEqual(len(commands), 2)
            payload = json.loads(captured.getvalue())
            self.assertEqual(payload.get("status"), "blocked")
            self.assertEqual(payload.get("reason_code"), "prompt_flow_blocker")
            self.assertEqual(payload.get("question_retry_attempt"), 1)
            self.assertEqual(payload.get("question_retry_applied"), True)
            self.assertIn("manual clarification", str(payload.get("reason") or ""))


if __name__ == "__main__":
    unittest.main()
