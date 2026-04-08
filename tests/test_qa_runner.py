import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import ensure_project_root, write_active_state
from aidd_runtime import qa as qa_module


class QaRunnerTests(unittest.TestCase):
    def test_relative_script_commands_run_in_module_cwd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="qa-runner-") as tmpdir:
            workspace = Path(tmpdir)
            target = ensure_project_root(workspace)
            report_path = target / "reports" / "qa" / "DEMO-QA.json"
            module_dir = workspace / "backend"
            module_dir.mkdir(parents=True, exist_ok=True)
            runner = module_dir / "run-tests.sh"
            runner.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            runner.chmod(0o755)

            executed, summary = qa_module._run_qa_tests(
                target,
                workspace,
                ticket="DEMO-QA",
                slug_hint="DEMO-QA",
                branch=None,
                report_path=report_path,
                allow_missing=True,
                commands_override=[["./backend/run-tests.sh"]],
                allow_skip_override=True,
            )

            self.assertEqual(summary, "pass")
            self.assertEqual(len(executed), 1)
            self.assertEqual(executed[0].get("status"), "pass")
            self.assertEqual(executed[0].get("cwd"), "backend")
            self.assertIn("backend/run-tests.sh", str(executed[0].get("command") or ""))

    def test_missing_relative_script_reports_actionable_failure(self) -> None:
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
                commands_override=[["./backend/missing-tests.sh"]],
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
            self.assertIn("command path not found in selected cwd", log_path.read_text(encoding="utf-8"))

    def test_non_path_commands_run_from_target_root(self) -> None:
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

    def test_absolute_script_outside_workspace_uses_absolute_display(self) -> None:
        with tempfile.TemporaryDirectory(prefix="qa-runner-") as tmpdir, tempfile.TemporaryDirectory(prefix="qa-ext-") as extdir:
            workspace = Path(tmpdir)
            target = ensure_project_root(workspace)
            report_path = target / "reports" / "qa" / "DEMO-QA4.json"
            external_runner = Path(extdir) / "run-tests.sh"
            external_runner.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            external_runner.chmod(0o755)

            executed, summary = qa_module._run_qa_tests(
                target,
                workspace,
                ticket="DEMO-QA4",
                slug_hint="DEMO-QA4",
                branch=None,
                report_path=report_path,
                allow_missing=True,
                commands_override=[[str(external_runner)]],
                allow_skip_override=True,
            )

            self.assertEqual(summary, "pass")
            self.assertEqual(len(executed), 1)
            self.assertEqual(executed[0].get("status"), "pass")
            self.assertTrue(str(executed[0].get("command") or "").startswith(str(external_runner)))

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
