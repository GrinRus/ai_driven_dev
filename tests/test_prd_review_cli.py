import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import REPO_ROOT, ensure_project_root


def _load_prd_review_cli_module():
    module_path = REPO_ROOT / "skills" / "review-spec" / "runtime" / "prd_review_cli.py"
    spec = importlib.util.spec_from_file_location("test_prd_review_cli_module", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PrdReviewCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load_prd_review_cli_module()

    def test_links_warn_auto_heal_is_non_blocking_for_review_spec(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-review-cli-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "DEMO-LINKS-WARN"
            report_path = project_root / "reports" / "prd" / f"{ticket}.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps({"status": "ready"}) + "\n", encoding="utf-8")
            context = types.SimpleNamespace(resolved_ticket=ticket, slug_hint=ticket)

            with (
                patch.object(
                    self.mod,
                    "validate_research",
                    side_effect=[
                        self.mod.ResearchValidationError(
                            "BLOCK: links missing (reason_code=rlm_links_empty_warn). Next action: `x`."
                        ),
                        object(),
                    ],
                ) as validate_mock,
                patch.object(
                    self.mod,
                    "_bounded_links_auto_heal",
                    return_value={
                        "auto_recovery_attempted": True,
                        "recovery_path": "review_spec_links_build_then_finalize",
                        "links_build_exit_code": 0,
                        "finalize_exit_code": 0,
                        "finalize_reason_code": "rlm_links_empty_warn",
                    },
                ) as heal_mock,
                patch.object(self.mod.prd_review, "run", return_value=0),
                patch.object(self.mod.runtime, "require_workflow_root", return_value=(workspace, project_root)),
                patch.object(self.mod.runtime, "resolve_feature_context", return_value=context),
                patch.object(self.mod.runtime, "maybe_sync_index"),
            ):
                rc = self.mod.main(["--ticket", ticket])

            self.assertEqual(rc, 0)
            self.assertEqual(validate_mock.call_count, 2)
            second_kwargs = validate_mock.call_args_list[1].kwargs
            self.assertEqual(second_kwargs.get("expected_stage"), "review")
            self.assertEqual(second_kwargs.get("allow_review_links_empty_warn"), True)
            self.assertEqual(second_kwargs.get("auto_recovery_attempted"), True)
            heal_mock.assert_called_once_with(ticket)
            updated = json.loads(report_path.read_text(encoding="utf-8"))
            research_validation = updated.get("research_validation") or {}
            self.assertEqual(research_validation.get("status"), "warn")
            self.assertEqual(research_validation.get("reason_code"), "rlm_links_empty_warn")
            self.assertEqual(research_validation.get("non_blocking"), True)

    def test_persist_research_warning_skips_repack_for_pack_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-review-cli-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "DEMO-PACK-REPORT"
            report_path = project_root / "reports" / "prd" / f"{ticket}.pack.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps({"ticket": ticket, "status": "ready"}) + "\n", encoding="utf-8")

            with patch.object(self.mod.reports_pack, "write_prd_pack") as repack_mock:
                self.mod._persist_review_research_warning(
                    target=project_root,
                    report_path=report_path,
                    evidence={"non_blocking": True},
                )

            repack_mock.assert_not_called()
            updated = json.loads(report_path.read_text(encoding="utf-8"))
            research_validation = updated.get("research_validation") or {}
            self.assertEqual(research_validation.get("reason_code"), "rlm_links_empty_warn")

    def test_persist_research_warning_repacks_raw_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-review-cli-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "DEMO-RAW-REPORT"
            report_path = project_root / "reports" / "prd" / f"{ticket}.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps({"ticket": ticket, "status": "ready"}) + "\n", encoding="utf-8")

            with patch.object(self.mod.reports_pack, "write_prd_pack") as repack_mock:
                self.mod._persist_review_research_warning(
                    target=project_root,
                    report_path=report_path,
                    evidence={"non_blocking": True},
                )

            repack_mock.assert_called_once_with(report_path, root=project_root)
            updated = json.loads(report_path.read_text(encoding="utf-8"))
            research_validation = updated.get("research_validation") or {}
            self.assertEqual(research_validation.get("reason_code"), "rlm_links_empty_warn")

    def test_non_links_research_error_stays_blocking(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-review-cli-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "DEMO-RLM-PENDING"
            context = types.SimpleNamespace(resolved_ticket=ticket, slug_hint=ticket)

            with (
                patch.object(
                    self.mod,
                    "validate_research",
                    side_effect=self.mod.ResearchValidationError(
                        "BLOCK: pending (reason_code=rlm_status_pending). Next action: `x`."
                    ),
                ),
                patch.object(self.mod, "_bounded_links_auto_heal") as heal_mock,
                patch.object(self.mod.runtime, "require_workflow_root", return_value=(workspace, project_root)),
                patch.object(self.mod.runtime, "resolve_feature_context", return_value=context),
            ):
                rc = self.mod.main(["--ticket", ticket])

            self.assertEqual(rc, 2)
            heal_mock.assert_not_called()

    def test_require_ready_fails_when_report_not_ready(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-review-cli-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "DEMO-REQUIRE-READY-FAIL"
            report_path = project_root / "reports" / "prd" / f"{ticket}.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps({"status": "ready", "recommended_status": "pending"}) + "\n",
                encoding="utf-8",
            )
            context = types.SimpleNamespace(resolved_ticket=ticket, slug_hint=ticket)

            with (
                patch.object(self.mod, "validate_research", return_value=object()),
                patch.object(self.mod.prd_review, "run", return_value=0),
                patch.object(self.mod.runtime, "require_workflow_root", return_value=(workspace, project_root)),
                patch.object(self.mod.runtime, "resolve_feature_context", return_value=context),
                patch.object(self.mod.runtime, "maybe_sync_index") as sync_mock,
            ):
                rc = self.mod.main(["--ticket", ticket, "--require-ready"])

            self.assertEqual(rc, 2)
            sync_mock.assert_not_called()

    def test_require_ready_passes_when_report_ready(self) -> None:
        with tempfile.TemporaryDirectory(prefix="prd-review-cli-") as tmpdir:
            workspace = Path(tmpdir)
            project_root = ensure_project_root(workspace)
            ticket = "DEMO-REQUIRE-READY-PASS"
            report_path = project_root / "reports" / "prd" / f"{ticket}.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps({"status": "ready", "recommended_status": "ready"}) + "\n",
                encoding="utf-8",
            )
            context = types.SimpleNamespace(resolved_ticket=ticket, slug_hint=ticket)

            with (
                patch.object(self.mod, "validate_research", return_value=object()),
                patch.object(self.mod.prd_review, "run", return_value=0),
                patch.object(self.mod.runtime, "require_workflow_root", return_value=(workspace, project_root)),
                patch.object(self.mod.runtime, "resolve_feature_context", return_value=context),
                patch.object(self.mod.runtime, "maybe_sync_index") as sync_mock,
            ):
                rc = self.mod.main(["--ticket", ticket, "--require-ready"])

            self.assertEqual(rc, 0)
            sync_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
