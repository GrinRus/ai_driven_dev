import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aidd_runtime import artifact_quality
from aidd_runtime import artifact_truth
from hooks.context_gc import working_set_builder


class ArtifactQualityTests(unittest.TestCase):
    def test_detect_template_leakage_positive(self) -> None:
        text = (
            "# PRD — Шаблон\n"
            "Status: draft\n"
            "Owner: <name/team>\n"
            "# Status: PENDING|READY|WARN|BLOCKED\n"
            "<stage-specific goal>\n"
        )
        markers = artifact_quality.detect_template_leakage(text)
        self.assertIn("template_prd_header", markers)
        self.assertIn("template_status_draft", markers)
        self.assertIn("template_owner_placeholder", markers)
        self.assertIn("template_status_hint", markers)
        self.assertIn("template_stage_goal", markers)

    def test_detect_template_leakage_negative(self) -> None:
        text = (
            "# AIDD Context Pack — review\n"
            "stage: review\n"
            "generated_at: 2026-01-01T00:00:00Z\n"
            "## What to do now\n"
            "- Run review and publish report.\n"
        )
        self.assertEqual(artifact_quality.detect_template_leakage(text), [])
        self.assertFalse(artifact_quality.has_template_leakage(text))

    def test_detect_status_drift(self) -> None:
        text = (
            "---\n"
            "Status: READY\n"
            "---\n\n"
            "## Plan Review\n"
            "Status: WARN\n"
        )
        drift = artifact_quality.detect_status_drift(text)
        self.assertEqual(drift, ["Plan Review:WARN!=READY"])

    def test_normalize_expected_report_paths_filters_non_canonical(self) -> None:
        normalized, dropped = artifact_quality.normalize_expected_report_paths(
            [
                "aidd/reports/qa/TST-001.json",
                "domain/adapter/MCP",
                "aidd/reports/reviewer/TST-001/iteration_id_I1.json",
                "<placeholder>",
            ]
        )
        self.assertEqual(
            normalized,
            [
                "aidd/reports/qa/TST-001.json",
                "aidd/reports/reviewer/TST-001/iteration_id_I1.json",
            ],
        )
        self.assertIn("domain/adapter/MCP", dropped)
        self.assertIn("<placeholder>", dropped)

    def test_repair_context_pack_if_contaminated_hard_replace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-quality-") as tmpdir:
            root = Path(tmpdir) / "aidd"
            (root / "reports" / "context").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "tasklist").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "plan").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            ticket = "TST-001"
            (root / "docs" / "tasklist" / f"{ticket}.md").write_text("# tasklist\n", encoding="utf-8")
            (root / "docs" / "plan" / f"{ticket}.md").write_text("# plan\n", encoding="utf-8")
            (root / "docs" / "prd" / f"{ticket}.prd.md").write_text("# prd\n", encoding="utf-8")
            context_path = root / "reports" / "context" / f"{ticket}.pack.md"
            context_path.write_text(
                (
                    "# AIDD Context Pack — <stage>\n\n"
                    "Status: draft\n"
                    "Owner: <name/team>\n"
                    "<stage-specific goal>\n"
                ),
                encoding="utf-8",
            )

            repaired, markers = artifact_quality.repair_context_pack_if_contaminated(root, ticket, context_path)
            self.assertTrue(repaired)
            self.assertTrue(markers)
            rebuilt = context_path.read_text(encoding="utf-8")
            self.assertIn("## Repair telemetry", rebuilt)
            self.assertIn("quality_repair: hard_replace", rebuilt)
            self.assertNotIn("<stage-specific goal>", rebuilt)
            self.assertNotIn("Owner: <name/team>", rebuilt)

    def test_repair_context_pack_preserves_original_when_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-quality-") as tmpdir:
            root = Path(tmpdir) / "aidd"
            (root / "reports" / "context").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "tasklist").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "plan").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            ticket = "TST-ATOMIC-1"
            (root / "docs" / "tasklist" / f"{ticket}.md").write_text("# tasklist\n", encoding="utf-8")
            (root / "docs" / "plan" / f"{ticket}.md").write_text("# plan\n", encoding="utf-8")
            (root / "docs" / "prd" / f"{ticket}.prd.md").write_text("# prd\n", encoding="utf-8")
            context_path = root / "reports" / "context" / f"{ticket}.pack.md"
            original = (
                "# AIDD Context Pack — <stage>\n\n"
                "Status: draft\n"
                "Owner: <name/team>\n"
                "<stage-specific goal>\n"
            )
            context_path.write_text(original, encoding="utf-8")

            with mock.patch("aidd_runtime.artifact_quality.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaises(OSError):
                    artifact_quality.repair_context_pack_if_contaminated(root, ticket, context_path)

            self.assertEqual(context_path.read_text(encoding="utf-8"), original)

    def test_working_set_builder_reports_quality_repair_for_contaminated_context(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-quality-ws-") as tmpdir:
            project_root = Path(tmpdir)
            aidd_root = project_root / "aidd"
            (aidd_root / "docs").mkdir(parents=True, exist_ok=True)
            (aidd_root / "docs" / "tasklist").mkdir(parents=True, exist_ok=True)
            (aidd_root / "reports" / "context").mkdir(parents=True, exist_ok=True)
            (aidd_root / "config").mkdir(parents=True, exist_ok=True)
            ticket = "TST-WS-1"
            (aidd_root / "docs" / ".active.json").write_text(
                '{"ticket":"TST-WS-1","slug_hint":"tst-ws-1","stage":"review"}\n',
                encoding="utf-8",
            )
            (aidd_root / "docs" / "tasklist" / f"{ticket}.md").write_text("## AIDD:NEXT_3\n- [ ] one\n", encoding="utf-8")
            (aidd_root / "reports" / "context" / f"{ticket}.pack.md").write_text(
                "# AIDD Context Pack — <stage>\n\nStatus: draft\n<stage-specific goal>\n",
                encoding="utf-8",
            )

            ws = working_set_builder.build_working_set(project_root)
            self.assertIn("quality_repair: hard_replace", ws.text)
            self.assertIn("#### Context Pack (rolling)", ws.text)
            self.assertNotIn("<stage-specific goal>", ws.text)

    def test_build_clean_context_pack_uses_index_and_pack_sources(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-quality-pack-sources-") as tmpdir:
            root = Path(tmpdir) / "aidd"
            ticket = "TST-PACK-1"
            (root / "docs" / "tasklist").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "plan").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "index").mkdir(parents=True, exist_ok=True)
            (root / "reports" / "qa").mkdir(parents=True, exist_ok=True)
            (root / "reports" / "research").mkdir(parents=True, exist_ok=True)
            (root / "reports" / "context").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "tasklist" / f"{ticket}.md").write_text("# tasklist\n", encoding="utf-8")
            (root / "docs" / "plan" / f"{ticket}.md").write_text("# plan\n", encoding="utf-8")
            (root / "docs" / "prd" / f"{ticket}.prd.md").write_text("# prd\n", encoding="utf-8")
            (root / "docs" / "index" / f"{ticket}.json").write_text("{}", encoding="utf-8")
            (root / "reports" / "qa" / f"{ticket}.pack.json").write_text("{}", encoding="utf-8")
            (root / "reports" / "research" / f"{ticket}-rlm.pack.json").write_text("{}", encoding="utf-8")

            clean = artifact_quality.build_clean_context_pack(root, ticket, existing_text="")
            self.assertIn(f"- aidd/docs/index/{ticket}.json", clean)
            self.assertIn(f"- aidd/reports/qa/{ticket}.pack.json", clean)
            self.assertIn(f"- aidd/reports/research/{ticket}-rlm.pack.json", clean)

    def test_build_clean_context_pack_hard_replace_ignores_contaminated_existing_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-quality-clean-pack-") as tmpdir:
            root = Path(tmpdir) / "aidd"
            ticket = "TST-CLEAN-1"
            (root / "docs" / "tasklist").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "plan").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "index").mkdir(parents=True, exist_ok=True)
            (root / "reports" / "context").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "tasklist" / f"{ticket}.md").write_text("# tasklist\n", encoding="utf-8")
            (root / "docs" / "plan" / f"{ticket}.md").write_text("# plan\n", encoding="utf-8")
            (root / "docs" / "prd" / f"{ticket}.prd.md").write_text("# prd\n", encoding="utf-8")
            (root / "docs" / "index" / f"{ticket}.json").write_text("{}", encoding="utf-8")

            existing = (
                f"# AIDD Context Pack — review\n\n"
                "read_next:\n"
                "- <stage-specific goal>\n"
                "- domain/adapter/MCP\n"
                f"- aidd/docs/prd/{ticket}.prd.md\n"
                "artefact_links:\n"
                "- <placeholder>\n"
                f"- aidd/docs/index/{ticket}.json\n\n"
                "## What to do now\n"
                "- <stage-specific goal>\n"
            )
            clean = artifact_quality.build_clean_context_pack(
                root,
                ticket,
                existing_text=existing,
                contamination=["template_stage_goal"],
            )
            self.assertNotIn("<stage-specific goal>", clean)
            self.assertNotIn("domain/adapter/MCP", clean)
            self.assertNotIn("<placeholder>", clean)
            self.assertIn(f"- aidd/docs/tasklist/{ticket}.md", clean)
            self.assertIn(f"- aidd/docs/index/{ticket}.json", clean)
            self.assertFalse(artifact_quality.has_template_leakage(clean))

    def test_artifact_truth_flags_tasklist_and_context_template_leakage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="artifact-quality-truth-") as tmpdir:
            root = Path(tmpdir) / "aidd"
            ticket = "TST-QC-1"
            (root / "docs" / "tasklist").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "plan").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "prd").mkdir(parents=True, exist_ok=True)
            (root / "reports" / "context").mkdir(parents=True, exist_ok=True)
            (root / "docs" / "tasklist" / f"{ticket}.md").write_text(
                (
                    "---\n"
                    f"Ticket: {ticket}\n"
                    "Status: READY\n"
                    f"Plan: aidd/docs/plan/{ticket}.md\n"
                    "Owner: <name/team>\n"
                    "---\n"
                ),
                encoding="utf-8",
            )
            (root / "docs" / "plan" / f"{ticket}.md").write_text("Status: READY\n", encoding="utf-8")
            (root / "docs" / "prd" / f"{ticket}.prd.md").write_text("Status: READY\n", encoding="utf-8")
            (root / "reports" / "context" / f"{ticket}.pack.md").write_text(
                "# AIDD Context Pack — <stage>\nStatus: draft\n",
                encoding="utf-8",
            )

            payload = artifact_truth.evaluate_artifact_truth(root, ticket)
            codes = {item.get("code") for item in payload.get("truth_checks") or []}
            self.assertIn("template_leakage", codes)
            self.assertIn("context_template_leakage", codes)


if __name__ == "__main__":
    unittest.main()
