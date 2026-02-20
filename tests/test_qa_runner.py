import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import ensure_project_root, write_active_state
from aidd_runtime import qa as qa_module


class QaRunnerTests(unittest.TestCase):
    def test_gradle_commands_run_in_module_cwd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="qa-runner-") as tmpdir:
            workspace = Path(tmpdir)
            target = ensure_project_root(workspace)
            report_path = target / "reports" / "qa" / "DEMO-QA.json"
            for module in ("backend", "backend-mcp"):
                module_dir = workspace / module
                module_dir.mkdir(parents=True, exist_ok=True)
                gradlew = module_dir / "gradlew"
                gradlew.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
                gradlew.chmod(0o755)

            executed, summary = qa_module._run_qa_tests(
                target,
                workspace,
                ticket="DEMO-QA",
                slug_hint="DEMO-QA",
                branch=None,
                report_path=report_path,
                allow_missing=True,
                commands_override=[["./gradlew", "test"]],
                allow_skip_override=True,
            )

            self.assertEqual(summary, "pass")
            self.assertEqual(len(executed), 2)
            cwds = {entry.get("cwd") for entry in executed}
            self.assertIn("backend", cwds)
            self.assertIn("backend-mcp", cwds)
            for entry in executed:
                self.assertEqual(entry.get("status"), "pass")

    def test_missing_gradle_wrapper_reports_actionable_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="qa-runner-") as tmpdir:
            workspace = Path(tmpdir)
            target = ensure_project_root(workspace)
            report_path = target / "reports" / "qa" / "DEMO-QA2.json"

            executed, summary = qa_module._run_qa_tests(
                target,
                workspace,
                ticket="DEMO-QA2",
                slug_hint="DEMO-QA2",
                branch=None,
                report_path=report_path,
                allow_missing=False,
                commands_override=[["./gradlew", "test"]],
                allow_skip_override=False,
            )

            self.assertEqual(summary, "fail")
            self.assertEqual(len(executed), 1)
            self.assertEqual(executed[0].get("status"), "fail")
            rel_log = str(executed[0]["log"])
            if rel_log.startswith("aidd/"):
                rel_log = rel_log.split("/", 1)[1]
            log_path = target / rel_log
            self.assertTrue(log_path.exists())
            self.assertIn("could not locate gradlew", log_path.read_text(encoding="utf-8"))

    def test_non_gradle_commands_run_from_target_root(self) -> None:
        with tempfile.TemporaryDirectory(prefix="qa-runner-") as tmpdir:
            workspace = Path(tmpdir)
            target = ensure_project_root(workspace)
            report_path = target / "reports" / "qa" / "DEMO-QA3.json"
            marker = target / "test_target_only.py"
            marker.write_text("import unittest\n", encoding="utf-8")

            executed, summary = qa_module._run_qa_tests(
                target,
                workspace,
                ticket="DEMO-QA3",
                slug_hint="DEMO-QA3",
                branch=None,
                report_path=report_path,
                allow_missing=True,
                commands_override=[["bash", "-lc", "test -f test_target_only.py"]],
                allow_skip_override=True,
            )

            self.assertEqual(summary, "pass")
            self.assertEqual(len(executed), 1)
            self.assertEqual(executed[0].get("status"), "pass")
            self.assertEqual(executed[0].get("cwd"), "aidd")

    def test_absolute_gradlew_outside_workspace_uses_fallback_display(self) -> None:
        with tempfile.TemporaryDirectory(prefix="qa-runner-") as tmpdir, tempfile.TemporaryDirectory(prefix="qa-ext-") as extdir:
            workspace = Path(tmpdir)
            target = ensure_project_root(workspace)
            report_path = target / "reports" / "qa" / "DEMO-QA4.json"
            external_gradlew = Path(extdir) / "gradlew"
            external_gradlew.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            external_gradlew.chmod(0o755)

            executed, summary = qa_module._run_qa_tests(
                target,
                workspace,
                ticket="DEMO-QA4",
                slug_hint="DEMO-QA4",
                branch=None,
                report_path=report_path,
                allow_missing=True,
                commands_override=[[str(external_gradlew), "test"]],
                allow_skip_override=True,
            )

            self.assertEqual(summary, "pass")
            self.assertEqual(len(executed), 1)
            self.assertEqual(executed[0].get("status"), "pass")
            self.assertTrue(str(executed[0].get("command") or "").startswith(str(external_gradlew)))

    def test_qa_main_syncs_active_stage_to_qa_before_execution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="qa-stage-sync-") as tmpdir:
            workspace = Path(tmpdir)
            target = ensure_project_root(workspace)
            ticket = "DEMO-QA-SYNC"
            write_active_state(target, ticket=ticket, stage="review", work_item="iteration_id=I1")
            (target / "reports" / "qa").mkdir(parents=True, exist_ok=True)
            report_path = target / "reports" / "qa" / f"{ticket}.json"
            report_path.write_text(json.dumps({"status": "READY"}, ensure_ascii=False) + "\n", encoding="utf-8")

            cwd = os.getcwd()
            try:
                os.chdir(workspace)
                with patch.dict(os.environ, {"CLAUDE_PLUGIN_ROOT": str(Path(__file__).resolve().parents[1])}, clear=False):
                    with patch("aidd_runtime.qa._qa_agent.main", return_value=0), patch(
                        "aidd_runtime.stage_result.main", return_value=0
                    ):
                        code = qa_module.main(["--ticket", ticket, "--skip-tests", "--allow-no-tests"])
            finally:
                os.chdir(cwd)

            self.assertEqual(code, 0)
            active_payload = json.loads((target / "docs" / ".active.json").read_text(encoding="utf-8"))
            self.assertEqual(active_payload.get("stage"), "qa")


if __name__ == "__main__":
    unittest.main()
