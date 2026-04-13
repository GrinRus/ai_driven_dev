from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STREAM_PATHS_MODULE_PATH = REPO_ROOT / "tests" / "repo_tools" / "aidd_stream_paths.py"
LAUNCHER_MODULE_PATH = REPO_ROOT / "tests" / "repo_tools" / "aidd_stage_launcher.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class AiddStageLauncherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stream_paths = _load_module(STREAM_PATHS_MODULE_PATH, "aidd_stream_paths")
        cls.launcher = _load_module(LAUNCHER_MODULE_PATH, "aidd_stage_launcher")

    def test_primary_extraction_ignores_tool_result_noise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "run.log"
            log.write_text(
                "\n".join(
                    [
                        '{"type":"system","subtype":"init","plugins":[{"name":"feature-dev-aidd"}]}',
                        '{"type":"user","message":{"content":"tool_result: cli.loop-run.20260305-140900.stream.jsonl"}}',
                    ]
                ),
                encoding="utf-8",
            )
            candidates = self.stream_paths.extract_primary_paths(log_path=log, project_dir=root)
            self.assertEqual(candidates, [])

    def test_header_extraction_parses_stream_and_log_without_prefix_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stream_jsonl = root / "aidd" / "reports" / "loops" / "TST-001" / "cli.loop-step.20260305-140900.stream.jsonl"
            stream_log = root / "aidd" / "reports" / "loops" / "TST-001" / "cli.loop-step.20260305-140900.stream.log"
            stream_jsonl.parent.mkdir(parents=True, exist_ok=True)
            stream_jsonl.write_text("{}", encoding="utf-8")
            stream_log.write_text("{}", encoding="utf-8")
            log = root / "run.log"
            log.write_text(
                "==> streaming enabled: writing stream=aidd/reports/loops/TST-001/cli.loop-step.20260305-140900.stream.jsonl "
                "log=aidd/reports/loops/TST-001/cli.loop-step.20260305-140900.stream.log\n",
                encoding="utf-8",
            )
            result = self.stream_paths.resolve_stream_paths(
                log_path=log,
                out_path=root / "stream_paths.txt",
                project_dir=root,
                ticket="TST-001",
                run_start_epoch=int(time.time()),
            )
            self.assertEqual(result["valid_count"], 2)
            self.assertEqual(result["invalid_count"], 0)
            self.assertEqual(result["missing_count"], 0)
            lines = (root / "stream_paths.txt").read_text(encoding="utf-8").splitlines()
            self.assertIn(f"source=loop_stream_header path={stream_jsonl.resolve()}", lines)
            self.assertIn(f"source=loop_stream_header path={stream_log.resolve()}", lines)
            self.assertNotRegex("\n".join(lines), r"log=aidd/")

    def test_invalid_and_missing_paths_are_classified_and_not_promoted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            candidates = [
                self.stream_paths.CandidatePath(source="init_json", raw_path="/tmp/outside.stream.log"),
                self.stream_paths.CandidatePath(source="init_json", raw_path="aidd/reports/loops/TST-001/missing.stream.jsonl"),
            ]
            valid, invalid, missing = self.stream_paths.normalize_and_validate(candidates, project_dir=root)
            self.assertEqual(len(valid), 0)
            self.assertEqual(len(invalid), 1)
            self.assertEqual(len(missing), 1)

    def test_fallback_discovery_ignores_stale_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            loop_root = root / "aidd" / "reports" / "loops" / "TST-001"
            loop_root.mkdir(parents=True, exist_ok=True)
            old_file = loop_root / "old.stream.jsonl"
            new_file = loop_root / "new.stream.log"
            old_file.write_text("old", encoding="utf-8")
            new_file.write_text("new", encoding="utf-8")

            now = int(time.time())
            run_start = now
            old_mtime = run_start - 60
            new_mtime = run_start - 1
            os.utime(old_file, (old_mtime, old_mtime))
            os.utime(new_file, (new_mtime, new_mtime))

            fallback = self.stream_paths.fallback_discovery(project_dir=root, ticket="TST-001", run_start_epoch=run_start)
            self.assertEqual(len(fallback), 1)
            self.assertEqual(fallback[0].raw_path, str(new_file.resolve()))

    def test_fallback_discovery_requires_ticket_to_avoid_cross_ticket_scan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            foreign_root = root / "aidd" / "reports" / "loops" / "OTHER-TICKET"
            foreign_root.mkdir(parents=True, exist_ok=True)
            (foreign_root / "foreign.stream.jsonl").write_text("{}", encoding="utf-8")
            fallback = self.stream_paths.fallback_discovery(project_dir=root, ticket="", run_start_epoch=int(time.time()))
            self.assertEqual(fallback, [])

    def test_liveness_active_stream_when_stream_grows_and_main_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            main = root / "main.log"
            stream = root / "stream.jsonl"
            main.write_text("main", encoding="utf-8")
            stream.write_text("stream", encoding="utf-8")
            now = int(time.time())
            os.utime(main, (now - 2000, now - 2000))
            os.utime(stream, (now - 5, now - 5))
            payload = self.launcher.build_liveness_payload(
                main_log=main,
                valid_stream_paths=[str(stream)],
                run_start_epoch=now - 100,
            )
            self.assertEqual(payload["classification"], "active_stream")
            self.assertEqual(payload["active_source"], "stream")

    def test_liveness_silent_stall_when_all_sources_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            main = root / "main.log"
            stream = root / "stream.log"
            main.write_text("main", encoding="utf-8")
            stream.write_text("stream", encoding="utf-8")
            now = int(time.time())
            os.utime(main, (now - 2500, now - 2500))
            os.utime(stream, (now - 2500, now - 2500))
            payload = self.launcher.build_liveness_payload(
                main_log=main,
                valid_stream_paths=[str(stream)],
                run_start_epoch=now - 3000,
            )
            self.assertEqual(payload["classification"], "silent_stall")
            self.assertEqual(payload["active_source"], "none")

    def test_detect_top_level_result_accepts_status_equals_blocked(self) -> None:
        self.assertEqual(self.launcher._detect_top_level_result("status=blocked reason_code=seed_scope_cascade_detected\n"), 1)

    def test_run_stage_budget_watchdog_sets_kill_markers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / "run.log"
            heartbeat_path = root / "run.heartbeat.log"
            payload = self.launcher.run_stage(
                cmd=[sys.executable, "-c", "import time; time.sleep(5)"],
                cwd=root,
                log_path=log_path,
                heartbeat_path=heartbeat_path,
                poll_seconds=1,
                budget_seconds=1,
            )
            self.assertEqual(payload.get("killed_flag"), 1)
            self.assertEqual(payload.get("watchdog_marker"), 1)
            self.assertIn(int(payload.get("exit_code") or 0), {137, 143})
            self.assertIn(str(payload.get("signal") or ""), {"SIGTERM", "SIGKILL"})
            self.assertGreaterEqual(int(payload.get("stage_elapsed_seconds") or 0), 1)

    def test_run_stage_fail_fast_for_playwright_dependency_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / "run.log"
            heartbeat_path = root / "run.heartbeat.log"
            payload = self.launcher.run_stage(
                cmd=[
                    sys.executable,
                    "-u",
                    "-c",
                    (
                        "import time;"
                        "print(\"Error: browserType.launch: Executable doesn't exist at /tmp/chrome\", flush=True);"
                        "print(\"Looks like Playwright Test or Playwright was just installed or updated.\", flush=True);"
                        "print(\"Please run: npx playwright install\", flush=True);"
                        "time.sleep(8)"
                    ),
                ],
                cwd=root,
                log_path=log_path,
                heartbeat_path=heartbeat_path,
                poll_seconds=1,
                budget_seconds=0,
                enable_tests_env_failfast=True,
            )
            self.assertEqual(payload.get("reason_code"), "tests_env_dependency_missing")
            self.assertIn(str(payload.get("reason") or ""), {"playwright_executable_missing", "playwright_install_loop_hint"})
            self.assertEqual(int(payload.get("watchdog_marker") or 0), 0)
            self.assertEqual(int(payload.get("killed_flag") or 0), 1)
            self.assertIn(int(payload.get("exit_code") or 0), {137, 143})

    def test_main_writes_termination_attribution_on_budget_watchdog(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "project"
            plugin_dir = root / "plugin"
            audit_dir = root / "audit"
            project_dir.mkdir(parents=True, exist_ok=True)
            plugin_dir.mkdir(parents=True, exist_ok=True)
            audit_dir.mkdir(parents=True, exist_ok=True)

            original_build_command = self.launcher.build_command
            original_argv = list(sys.argv)
            self.launcher.build_command = lambda **_: [sys.executable, "-c", "import time; time.sleep(5)"]
            try:
                sys.argv = [
                    "aidd_stage_launcher.py",
                    "--project-dir",
                    str(project_dir),
                    "--plugin-dir",
                    str(plugin_dir),
                    "--audit-dir",
                    str(audit_dir),
                    "--step",
                    "06_implement",
                    "--run",
                    "1",
                    "--ticket",
                    "TST-001",
                    "--stage-command",
                    "/feature-dev-aidd:implement TST-001",
                    "--budget-seconds",
                    "1",
                ]
                rc = self.launcher.main()
            finally:
                self.launcher.build_command = original_build_command
                sys.argv = original_argv

            self.assertIn(rc, {137, 143})
            term_path = audit_dir / "06_implement_termination_attribution.txt"
            self.assertTrue(term_path.exists())
            term_text = term_path.read_text(encoding="utf-8")
            self.assertIn("killed_flag=1", term_text)
            self.assertIn("watchdog_marker=1", term_text)
            self.assertIn("watchdog_terminated", term_text)
            summary_text = (audit_dir / "06_implement_run1.summary.txt").read_text(encoding="utf-8")
            self.assertIn("killed_flag=1", summary_text)
            self.assertIn("watchdog_marker=1", summary_text)

    def test_main_fail_fast_classifies_tests_env_dependency_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "project"
            plugin_dir = root / "plugin"
            audit_dir = root / "audit"
            project_dir.mkdir(parents=True, exist_ok=True)
            plugin_dir.mkdir(parents=True, exist_ok=True)
            audit_dir.mkdir(parents=True, exist_ok=True)

            original_build_command = self.launcher.build_command
            original_argv = list(sys.argv)
            self.launcher.build_command = lambda **_: [
                sys.executable,
                "-u",
                "-c",
                (
                    "import time;"
                    "print(\"Error: browserType.launch: Executable doesn't exist at /tmp/chrome\", flush=True);"
                    "print(\"Looks like Playwright Test or Playwright was just installed or updated.\", flush=True);"
                    "print(\"Please run: npx playwright install\", flush=True);"
                    "time.sleep(8)"
                ),
            ]
            try:
                sys.argv = [
                    "aidd_stage_launcher.py",
                    "--project-dir",
                    str(project_dir),
                    "--plugin-dir",
                    str(plugin_dir),
                    "--audit-dir",
                    str(audit_dir),
                    "--step",
                    "06_implement",
                    "--run",
                    "1",
                    "--ticket",
                    "TST-001",
                    "--stage-command",
                    "/feature-dev-aidd:implement TST-001",
                    "--budget-seconds",
                    "120",
                ]
                rc = self.launcher.main()
            finally:
                self.launcher.build_command = original_build_command
                sys.argv = original_argv

            self.assertIn(rc, {137, 143})
            term_path = audit_dir / "06_implement_termination_attribution.txt"
            term_text = term_path.read_text(encoding="utf-8")
            self.assertIn("reason_code=tests_env_dependency_missing", term_text)
            self.assertIn("tests_env_dependency_missing", term_text)
            self.assertIn("watchdog_marker=0", term_text)
            summary_text = (audit_dir / "06_implement_run1.summary.txt").read_text(encoding="utf-8")
            self.assertIn("reason_code=tests_env_dependency_missing", summary_text)
            self.assertIn("watchdog_marker=0", summary_text)

    def test_main_fail_fast_when_project_equals_plugin_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_dir = root / "audit"
            audit_dir.mkdir(parents=True, exist_ok=True)

            original_run_stage = self.launcher.run_stage
            original_argv = list(sys.argv)
            self.launcher.run_stage = lambda **_: (_ for _ in ()).throw(AssertionError("run_stage must not be called"))
            try:
                sys.argv = [
                    "aidd_stage_launcher.py",
                    "--project-dir",
                    str(root),
                    "--plugin-dir",
                    str(root),
                    "--audit-dir",
                    str(audit_dir),
                    "--step",
                    "05_tasks_new",
                    "--run",
                    "1",
                    "--ticket",
                    "TST-001",
                    "--stage-command",
                    "/feature-dev-aidd:tasks-new TST-001",
                ]
                rc = self.launcher.main()
            finally:
                sys.argv = original_argv
                self.launcher.run_stage = original_run_stage

            self.assertEqual(rc, self.launcher.CWD_BLOCKER_EXIT_CODE)
            summary = (audit_dir / "05_tasks_new_run1.summary.txt").read_text(encoding="utf-8")
            self.assertIn("reason_code=cwd_wrong", summary)
            self.assertIn("classification=ENV_MISCONFIG(cwd_wrong)", summary)
            self.assertIn("result_count=1", summary)
            self.assertIn("top_level_result=1", summary)
            self.assertIn(f"project_dir={root.resolve()}", summary)
            self.assertIn(f"plugin_dir={root.resolve()}", summary)
            log_text = (audit_dir / "05_tasks_new_run1.log").read_text(encoding="utf-8")
            self.assertIn("refusing to use plugin repository as workspace root", log_text)

    def test_main_fail_fast_when_project_looks_like_plugin_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_dir = root / "project_like_plugin"
            plugin_dir = root / "plugin_runtime"
            audit_dir = root / "audit"
            (project_dir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
            (project_dir / "skills").mkdir(parents=True, exist_ok=True)
            plugin_dir.mkdir(parents=True, exist_ok=True)
            audit_dir.mkdir(parents=True, exist_ok=True)

            original_run_stage = self.launcher.run_stage
            original_argv = list(sys.argv)
            self.launcher.run_stage = lambda **_: (_ for _ in ()).throw(AssertionError("run_stage must not be called"))
            try:
                sys.argv = [
                    "aidd_stage_launcher.py",
                    "--project-dir",
                    str(project_dir),
                    "--plugin-dir",
                    str(plugin_dir),
                    "--audit-dir",
                    str(audit_dir),
                    "--step",
                    "04_aidd_init",
                    "--run",
                    "1",
                    "--ticket",
                    "TST-001",
                    "--stage-command",
                    "/feature-dev-aidd:aidd-init",
                ]
                rc = self.launcher.main()
            finally:
                sys.argv = original_argv
                self.launcher.run_stage = original_run_stage

            self.assertEqual(rc, self.launcher.CWD_BLOCKER_EXIT_CODE)
            summary = (audit_dir / "04_aidd_init_run1.summary.txt").read_text(encoding="utf-8")
            self.assertIn("reason_code=cwd_wrong", summary)
            env_misconfig = (audit_dir / "04_aidd_init_run1.env_misconfig.txt").read_text(encoding="utf-8")
            self.assertIn("reason_detail=project_dir_looks_like_plugin_root", env_misconfig)


if __name__ == "__main__":
    unittest.main()
