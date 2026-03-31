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
FIXTURE_PACK_20260310 = REPO_ROOT / "tests" / "fixtures" / "audit_tst001_20260310"
FIXTURE_PACK_20260311 = REPO_ROOT / "tests" / "fixtures" / "audit_tst001_20260311"
FIXTURE_PACK_20260330 = REPO_ROOT / "tests" / "fixtures" / "audit_tst001_20260330"


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

    def test_fallback_discovery_excludes_loop_stream_for_non_loop_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            loop_root = root / "aidd" / "reports" / "loops" / "TST-001"
            loop_root.mkdir(parents=True, exist_ok=True)
            loop_file = loop_root / "cli.loop-run.20260317-052348.stream.log"
            qa_file = loop_root / "cli.qa.20260317-052349.stream.log"
            loop_file.write_text("loop", encoding="utf-8")
            qa_file.write_text("qa", encoding="utf-8")
            run_start = int(time.time())
            now = run_start - 1
            os.utime(loop_file, (now, now))
            os.utime(qa_file, (now, now))

            fallback = self.stream_paths.fallback_discovery(
                project_dir=root,
                ticket="TST-001",
                run_start_epoch=run_start,
                step="08_qa",
            )
            self.assertEqual(len(fallback), 1)
            self.assertEqual(fallback[0].raw_path, str(qa_file.resolve()))

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

    def test_extract_prompt_exec_telemetry_counts_alias_sibling_and_canonical_calls(self) -> None:
        log_text = "\n".join(
            [
                "Unknown skill: :status",
                "command not found: :status",
                "Sibling tool call errored",
                "InputValidationError: required parameter `command` is missing",
                "python3 /tmp/plugin/skills/implement/runtime/implement_run.py --ticket TST-001",
                "python3 /tmp/plugin/skills/aidd-docio/runtime/actions_apply.py --actions /tmp/a.json",
            ]
        )
        telemetry = self.launcher._extract_prompt_exec_telemetry(log_text)
        self.assertEqual(telemetry["status_alias_error_count"], 2)
        self.assertEqual(telemetry["sibling_tool_error_count"], 1)
        self.assertEqual(telemetry["canonical_runtime_call_count"], 2)
        self.assertEqual(telemetry["malformed_stage_alias_count"], 0)
        self.assertEqual(telemetry["tool_command_missing_count"], 1)

    def test_extract_prompt_exec_telemetry_counts_malformed_stage_alias(self) -> None:
        telemetry = self.launcher._extract_prompt_exec_telemetry(
            "\n".join(
                [
                    "Unknown skill: :qa",
                    "command not found: :review",
                ]
            )
        )
        self.assertEqual(telemetry["malformed_stage_alias_count"], 2)
        self.assertEqual(telemetry["tool_command_missing_count"], 0)

    def test_detect_seed_stage_non_converging_command_requires_alias_and_sibling_without_canonical_chain(self) -> None:
        positive = self.launcher._detect_seed_stage_non_converging_command(
            result_count="0",
            top_level_result=0,
            telemetry={
                "status_alias_error_count": 2,
                "sibling_tool_error_count": 3,
                "canonical_runtime_call_count": 0,
            },
        )
        self.assertEqual(positive, 1)
        negative = self.launcher._detect_seed_stage_non_converging_command(
            result_count="0",
            top_level_result=0,
            telemetry={
                "status_alias_error_count": 2,
                "sibling_tool_error_count": 3,
                "canonical_runtime_call_count": 1,
            },
        )
        self.assertEqual(negative, 0)

    def test_seed_stage_step_detection_scopes_marker_to_implement(self) -> None:
        self.assertTrue(self.launcher._is_seed_stage_step("06_implement"))
        self.assertTrue(self.launcher._is_seed_stage_step("implement"))
        self.assertTrue(self.launcher._is_seed_stage_step("seed_stage"))
        self.assertFalse(self.launcher._is_seed_stage_step("08_qa"))
        self.assertFalse(self.launcher._is_seed_stage_step("05_review_spec"))

    def test_append_synthetic_terminal_result_for_nonzero_without_top_level(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / "run.log"
            log_path.write_text("runner exited\n", encoding="utf-8")
            event = self.launcher._maybe_append_synthetic_terminal_result(
                log_path=log_path,
                exit_code=143,
                ticket="TST-001",
                stage="implement",
            )
            self.assertTrue(event)
            self.assertEqual(event.get("reason_code"), "parent_terminated_or_external_terminate")
            self.assertEqual(event.get("schema"), "aidd.stage_result.v1")
            self.assertEqual(event.get("ticket"), "TST-001")
            self.assertEqual(event.get("stage"), "implement")
            self.assertEqual(event.get("result"), "blocked")
            text = log_path.read_text(encoding="utf-8")
            self.assertIn('"schema": "aidd.stage_result.v1"', text)
            self.assertIn('"terminal_marker": 1', text)

    def test_append_synthetic_terminal_result_skips_when_top_level_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / "run.log"
            log_path.write_text('{"type":"result","status":"blocked"}\n', encoding="utf-8")
            event = self.launcher._maybe_append_synthetic_terminal_result(
                log_path=log_path,
                exit_code=1,
                ticket="TST-001",
                stage="qa",
            )
            self.assertEqual(event, {})

    def test_append_synthetic_terminal_result_marks_malformed_stage_alias_contract_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log_path = root / "run.log"
            log_path.write_text("Unknown skill: :qa\n", encoding="utf-8")
            event = self.launcher._maybe_append_synthetic_terminal_result(
                log_path=log_path,
                exit_code=1,
                ticket="TST-001",
                stage="qa",
            )
            self.assertEqual(event.get("reason_code"), "launcher_prompt_contract_mismatch")
            self.assertEqual(
                event.get("classification"),
                "PROMPT_EXEC_ISSUE(launcher_prompt_contract_mismatch)",
            )

    def test_infer_stage_name_from_stage_commands_for_stage5x(self) -> None:
        cases = [
            ("/feature-dev-aidd:idea-new TST-001 note", "idea-new"),
            ("/feature-dev-aidd:researcher TST-001", "researcher"),
            ("/feature-dev-aidd:plan-new TST-001", "plan-new"),
            ("/feature-dev-aidd:review-spec TST-001", "review-spec"),
        ]
        for stage_command, expected in cases:
            with self.subTest(stage_command=stage_command):
                stage = self.launcher._infer_stage_name(stage_command=stage_command, step_hint="")
                self.assertEqual(stage, expected)

    def test_tst001_fixture_packs_are_available_for_replay(self) -> None:
        expected = [
            FIXTURE_PACK_20260310 / "06_implement_run1.summary.txt",
            FIXTURE_PACK_20260310 / "06_review_run1.summary.txt",
            FIXTURE_PACK_20260311 / "08_qa_run1.summary.txt",
            FIXTURE_PACK_20260311 / "07_loop_run_run2.summary.txt",
            FIXTURE_PACK_20260330 / "06_implement_run1.summary.txt",
        ]
        for path in expected:
            with self.subTest(path=path):
                self.assertTrue(path.exists(), f"missing fixture: {path}")


if __name__ == "__main__":
    unittest.main()
