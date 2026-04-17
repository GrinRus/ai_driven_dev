from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import ensure_project_root


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "tests" / "repo_tools" / "aidd_e2e_live_audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("aidd_e2e_live_audit", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    def __init__(
        self,
        module,
        workspace_root: Path,
        *,
        launcher_exit_code: int = 0,
        plugin_loaded: bool = True,
        artifact_audit_exit_code: int = 0,
    ):
        self.module = module
        self.workspace_root = workspace_root
        self.launcher_exit_code = launcher_exit_code
        self.plugin_loaded = plugin_loaded
        self.artifact_audit_exit_code = artifact_audit_exit_code
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(cmd))
        script_name = Path(cmd[1]).name if len(cmd) > 1 else ""
        if script_name == "build_e2e_prompts.py":
            return subprocess.CompletedProcess(cmd, 0, "[e2e-prompt-build] outputs are up to date\n", "")
        if script_name == "aidd_stage_launcher.py":
            audit_dir = Path(cmd[cmd.index("--audit-dir") + 1])
            step = cmd[cmd.index("--step") + 1]
            run = cmd[cmd.index("--run") + 1]
            paths = self.module._stage_paths(audit_dir, step, int(run))
            paths["summary"].write_text(
                "\n".join(
                    [
                        f"step={step}",
                        "result_count=1",
                        "top_level_status=done",
                        "exit_code=0",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            paths["init_check"].write_text(
                "\n".join(
                    [
                        f"plugins_ok={1 if self.plugin_loaded else 0}",
                        f"slash_ok={1 if self.plugin_loaded else 0}",
                        "skills_ok=1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            if self.launcher_exit_code == 12:
                paths["disk_preflight"].write_text("free_bytes=0\nmin_free_bytes=1073741824\n", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, self.launcher_exit_code, "", "")
        if script_name == "aidd_audit_runner.py":
            payload = {
                "rollup_outcome": "completed",
                "steps": {
                    "00_status": {
                        "classification": "TELEMETRY_ONLY",
                        "classification_subtype": "completed",
                        "effective_classification": "INFO(completed)",
                        "top_level_status": "done",
                        "summary_path": str(self.workspace_root / "aidd" / "reports" / "events" / "codex-e2e-audit" / "fake"),
                        "primary_root_cause": "TELEMETRY_ONLY:completed",
                    }
                },
            }
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        if script_name == "artifact_audit.py":
            payload = {
                "artifact_quality_gate": "PASS",
                "truth_checks": [],
                "missing_expected_reports": [],
                "template_leakage": [],
                "status_drift": [],
                "recommended_next_actions": ["No artifact issues detected; the current artifact set is internally consistent."],
            }
            return subprocess.CompletedProcess(
                cmd,
                self.artifact_audit_exit_code,
                json.dumps(payload) if self.artifact_audit_exit_code == 0 else "",
                "" if self.artifact_audit_exit_code == 0 else "artifact audit failed\n",
            )
        raise AssertionError(f"unexpected command: {cmd}")


class AiddE2ELiveAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()

    def _run_main(self, workspace: Path, fake_runner: FakeRunner, *extra_args: str) -> int:
        original = self.module._run_subprocess
        self.module._run_subprocess = fake_runner
        argv = [
            "--project-dir",
            str(workspace),
            "--plugin-dir",
            str(REPO_ROOT),
            "--ticket",
            "TST-CODEX-1",
            "--profile",
            "smoke",
            "--quality-profile",
            "full",
            *extra_args,
        ]
        try:
            original_argv = list(self.module.sys.argv)
            self.module.sys.argv = [str(SCRIPT_PATH), *argv]
            return self.module.main()
        finally:
            self.module.sys.argv = original_argv
            self.module._run_subprocess = original

    def test_run_creates_summary_pack_and_invokes_primitives(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aidd-codex-live-audit-") as tmpdir:
            workspace = Path(tmpdir)
            ensure_project_root(workspace)
            fake_runner = FakeRunner(self.module, workspace)

            exit_code = self._run_main(workspace, fake_runner)

            self.assertEqual(exit_code, 0)
            audit_root = workspace / "aidd" / "reports" / "events" / "codex-e2e-audit"
            runs = sorted(audit_root.iterdir())
            self.assertEqual(len(runs), 1)
            run_dir = runs[0]
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "PASS")
            self.assertEqual(summary["artifact_quality_gate"], "PASS")
            self.assertEqual(summary["top_findings"], [])
            self.assertTrue((run_dir / "summary.md").exists())
            self.assertTrue(any("build_e2e_prompts.py" in " ".join(call) for call in fake_runner.calls))
            self.assertTrue(any("aidd_stage_launcher.py" in " ".join(call) for call in fake_runner.calls))
            self.assertTrue(any("aidd_audit_runner.py" in " ".join(call) for call in fake_runner.calls))
            self.assertTrue(any("artifact_audit.py" in " ".join(call) for call in fake_runner.calls))

    def test_fail_fast_on_plugin_not_loaded(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aidd-codex-live-audit-") as tmpdir:
            workspace = Path(tmpdir)
            ensure_project_root(workspace)
            fake_runner = FakeRunner(self.module, workspace, plugin_loaded=False)

            exit_code = self._run_main(workspace, fake_runner)

            self.assertEqual(exit_code, 2)
            run_dir = next((workspace / "aidd" / "reports" / "events" / "codex-e2e-audit").iterdir())
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["fail_fast_reason"], "plugin_not_loaded")
            launcher_calls = [call for call in fake_runner.calls if "aidd_stage_launcher.py" in " ".join(call)]
            self.assertEqual(len(launcher_calls), 1)

    def test_fail_fast_on_no_space_return_code(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aidd-codex-live-audit-") as tmpdir:
            workspace = Path(tmpdir)
            ensure_project_root(workspace)
            fake_runner = FakeRunner(self.module, workspace, launcher_exit_code=12)

            exit_code = self._run_main(workspace, fake_runner)

            self.assertEqual(exit_code, 2)
            run_dir = next((workspace / "aidd" / "reports" / "events" / "codex-e2e-audit").iterdir())
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["fail_fast_reason"], "no_space_left_on_device")

    def test_fail_fast_on_cwd_wrong_return_code(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aidd-codex-live-audit-") as tmpdir:
            workspace = Path(tmpdir)
            ensure_project_root(workspace)
            fake_runner = FakeRunner(self.module, workspace, launcher_exit_code=14)

            exit_code = self._run_main(workspace, fake_runner)

            self.assertEqual(exit_code, 2)
            run_dir = next((workspace / "aidd" / "reports" / "events" / "codex-e2e-audit").iterdir())
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["fail_fast_reason"], "cwd_wrong")

    def test_unexpected_stage_failure_marks_run_failed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aidd-codex-live-audit-") as tmpdir:
            workspace = Path(tmpdir)
            ensure_project_root(workspace)
            fake_runner = FakeRunner(self.module, workspace, launcher_exit_code=23)

            exit_code = self._run_main(workspace, fake_runner)

            self.assertEqual(exit_code, 2)
            run_dir = next((workspace / "aidd" / "reports" / "events" / "codex-e2e-audit").iterdir())
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "FAIL")
            self.assertEqual(summary["fail_fast_reason"], "stage_execution_failed")
            self.assertEqual(summary["stop_reason"], "00_status_returned_23")

    def test_artifact_audit_failure_marks_run_failed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="aidd-codex-live-audit-") as tmpdir:
            workspace = Path(tmpdir)
            ensure_project_root(workspace)
            fake_runner = FakeRunner(self.module, workspace, artifact_audit_exit_code=7)

            exit_code = self._run_main(workspace, fake_runner)

            self.assertEqual(exit_code, 2)
            run_dir = next((workspace / "aidd" / "reports" / "events" / "codex-e2e-audit").iterdir())
            summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "FAIL")
            self.assertEqual(summary["fail_fast_reason"], "artifact_audit_failed")
            self.assertEqual(summary["artifact_quality_gate"], "FAIL")


if __name__ == "__main__":
    unittest.main()
