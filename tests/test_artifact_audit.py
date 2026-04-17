from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT, cli_env, ensure_gates_config, ensure_project_root, write_active_stage


SCRIPT_PATH = REPO_ROOT / "skills" / "aidd-observability" / "runtime" / "artifact_audit.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("artifact_audit", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_artifact_audit(root: Path, ticket: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(SCRIPT_PATH), "--root", str(root), "--ticket", ticket],
        cwd=root,
        text=True,
        capture_output=True,
        env=cli_env(),
    )


class ArtifactAuditCliTests(unittest.TestCase):
    def test_unknown_truth_check_uses_generic_follow_up(self) -> None:
        module = _load_module()

        actions = module.build_recommended_next_actions(
            [{"code": "future_truth_check", "severity": "warn", "summary": "new issue"}]
        )

        self.assertEqual(
            actions,
            [
                "Inspect truth_checks in the artifact audit output and reconcile the reported inconsistencies "
                "before trusting downstream readiness."
            ],
        )

    def test_template_leakage_is_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-audit-cli-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "TST-AUDIT-1"
            ensure_gates_config(workspace)
            write_active_stage(workspace, "review")
            (project_root / "docs" / "tasklist").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "plan").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            (project_root / "reports" / "context").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "tasklist" / f"{ticket}.md").write_text(
                "---\n"
                f"Ticket: {ticket}\n"
                "Status: READY\n"
                f"Plan: aidd/docs/plan/{ticket}.md\n"
                "Owner: <name/team>\n"
                "---\n",
                encoding="utf-8",
            )
            (project_root / "docs" / "plan" / f"{ticket}.md").write_text("Status: READY\n", encoding="utf-8")
            (project_root / "docs" / "prd" / f"{ticket}.prd.md").write_text("Status: READY\n", encoding="utf-8")
            (project_root / "reports" / "context" / f"{ticket}.pack.md").write_text(
                "# AIDD Context Pack — <stage>\nStatus: draft\n",
                encoding="utf-8",
            )

            result = _run_artifact_audit(workspace, ticket)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["artifact_quality_gate"], "WARN")
            codes = {item["code"] for item in payload["template_leakage"]}
            self.assertEqual(codes, {"context_template_leakage", "template_leakage"})

    def test_missing_expected_reports_are_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-audit-cli-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "TST-AUDIT-2"
            ensure_gates_config(workspace)
            write_active_stage(workspace, "qa")
            (project_root / "docs" / "tasklist").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "plan").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "tasklist" / f"{ticket}.md").write_text(
                "---\n"
                f"Ticket: {ticket}\n"
                "Status: READY\n"
                f"Plan: aidd/docs/plan/{ticket}.md\n"
                f"ExpectedReports:\n  qa: aidd/reports/qa/{ticket}.json\n"
                "---\n",
                encoding="utf-8",
            )
            (project_root / "docs" / "plan" / f"{ticket}.md").write_text("Status: READY\n", encoding="utf-8")
            (project_root / "docs" / "prd" / f"{ticket}.prd.md").write_text("Status: READY\n", encoding="utf-8")

            result = _run_artifact_audit(workspace, ticket)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["missing_expected_reports"], [f"aidd/reports/qa/{ticket}.json"])
            self.assertTrue(any("missing downstream reports" in item for item in payload["recommended_next_actions"]))

    def test_status_drift_is_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-audit-cli-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "TST-AUDIT-3"
            ensure_gates_config(workspace)
            write_active_stage(workspace, "review")
            (project_root / "docs" / "tasklist").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "plan").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "tasklist" / f"{ticket}.md").write_text(
                "---\n"
                f"Ticket: {ticket}\n"
                "Status: READY\n"
                f"Plan: aidd/docs/plan/{ticket}.md\n"
                "---\n\n"
                "## Plan Review\n"
                "Status: WARN\n",
                encoding="utf-8",
            )
            (project_root / "docs" / "plan" / f"{ticket}.md").write_text("Status: READY\n", encoding="utf-8")
            (project_root / "docs" / "prd" / f"{ticket}.prd.md").write_text("Status: READY\n", encoding="utf-8")

            result = _run_artifact_audit(workspace, ticket)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(len(payload["status_drift"]), 1)
            self.assertEqual(payload["status_drift"][0]["code"], "status_drift")

    def test_stale_references_are_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-audit-cli-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "TST-AUDIT-4"
            ensure_gates_config(workspace)
            write_active_stage(workspace, "plan")
            (project_root / "docs" / "tasklist").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "tasklist" / f"{ticket}.md").write_text(
                "---\n"
                f"Ticket: {ticket}\n"
                "Status: READY\n"
                "PRD: aidd/docs/prd/missing.prd.md\n"
                "Plan: aidd/docs/plan/missing.md\n"
                "---\n",
                encoding="utf-8",
            )

            result = _run_artifact_audit(workspace, ticket)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(len(payload["stale_references"]), 1)
            self.assertEqual(payload["stale_references"][0]["code"], "stale_reference")


if __name__ == "__main__":
    unittest.main()
