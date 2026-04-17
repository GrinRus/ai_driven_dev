from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY_PROMPT = REPO_ROOT / "docs" / "e2e" / "aidd_test_quality_audit_prompt_tst002_full.txt"
FLOW_PROMPT_FULL = REPO_ROOT / "docs" / "e2e" / "aidd_test_flow_prompt_ralph_script_full.txt"
PROMPT_BUILDER = REPO_ROOT / "tests" / "repo_tools" / "build_e2e_prompts.py"
PROMPT_FRAGMENTS_DIR = REPO_ROOT / "tests" / "repo_tools" / "e2e_prompt"
CI_LINT_SCRIPT = REPO_ROOT / "tests" / "repo_tools" / "ci-lint.sh"


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"missing contract file: {path}")
    return path.read_text(encoding="utf-8")


class E2EQualityPromptContractTests(unittest.TestCase):
    def test_quality_prompt_builder_fragments_exist(self) -> None:
        self.assertTrue(PROMPT_BUILDER.exists(), msg=f"missing prompt builder: {PROMPT_BUILDER}")
        for rel in ("quality_base_contract.md", "quality_profile_full.md", "quality_must_read_manifest.md"):
            path = PROMPT_FRAGMENTS_DIR / rel
            self.assertTrue(path.exists(), msg=f"missing quality prompt fragment: {path}")

    def test_quality_prompt_builder_outputs_are_up_to_date(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PROMPT_BUILDER), "--check"],
            cwd=str(REPO_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(
            result.returncode,
            0,
            msg=f"builder check failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )

    def test_quality_prompt_has_expected_identity_and_reference_prompt(self) -> None:
        text = _read(QUALITY_PROMPT)
        self.assertIn("# AIDD E2E Quality Audit Prompt (TST-002, FULL)", text)
        self.assertIn("AIDD E2E Quality Audit (TST-002)", text)
        self.assertIn("$PLUGIN_DIR/docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt", text)
        self.assertIn("standalone-expanded", text)
        self.assertNotIn("AUDIT_COMPLETE TST-001", text)

    def test_legacy_qna_guard_scans_quality_prompt_output_path(self) -> None:
        ci_lint = _read(CI_LINT_SCRIPT)
        self.assertIn('"docs/e2e/aidd_test_quality_audit_prompt_tst002*.txt"', ci_lint)
        matched = sorted(REPO_ROOT.glob("docs/e2e/aidd_test_quality_audit_prompt_tst002*.txt"))
        self.assertTrue(matched, msg="quality prompt glob should resolve at least one file from repo root")
        self.assertIn(
            QUALITY_PROMPT,
            matched,
            msg=f"quality prompt path {QUALITY_PROMPT} must be covered by legacy Qn scan glob",
        )

    def test_quality_prompt_declares_quality_variables(self) -> None:
        text = _read(QUALITY_PROMPT)
        for needle in (
            "BASE_PROMPT=$PLUGIN_DIR/docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt",
            "BACKLOG_PATH=$PLUGIN_DIR/docs/backlog.md",
            "QUALITY_PROFILE=full|smoke",
            "CLASSIFICATION_PROFILE=soft_default|strict",
            "QUALITY_GATE_POLICY=strict",
            "WAVE_WRITE_MODE=on-findings|always",
            "BACKLOG_SCOPE=aidd-only|mixed",
            "QUALITY_SCORE_SCALE=0..3",
            "QUALITY_TOP_FINDINGS_LIMIT=<int>",
            "QUALITY_BACKLOG_ITEM_LIMIT=<int>",
            "ALLOW_PLUGIN_BACKLOG_WRITE=1",
            "BACKLOG_NEW_WAVE=<auto>",
            "QUALITY_FINAL_MARKER=QUALITY_AUDIT_COMPLETE",
        ):
            self.assertIn(needle, text)

    def test_quality_prompt_preserves_launcher_liveness_and_readiness_invariants(self) -> None:
        text = _read(QUALITY_PROMPT)
        for needle in (
            'cd "$PROJECT_DIR"',
            '--plugin-dir "$PLUGIN_DIR"',
            "--verbose --output-format stream-json",
            'df -Pk "$PROJECT_DIR"',
            "active_stream",
            "main log",
            "stream jsonl",
            "system/init",
            "streaming enabled",
            "05_precondition_block.txt",
            "answers_format=compact_q_values",
            "INFO(readiness_gate_research_softened)",
            "review_spec_report_mismatch",
            "review_spec_report_mismatch_non_blocking",
            "AIDD:SYNC_FROM_REVIEW",
            "NOT VERIFIED (findings_sync_not_converged)",
            "runtime_path_missing_or_drift",
            "prompt-flow drift (non-canonical stage orchestration)",
            "aidd_stage_launcher.py",
            'realpath("$PROJECT_DIR") != realpath("$PLUGIN_DIR")',
            "PROJECT_DIR must differ from PLUGIN_DIR",
            "not_available=1",
        ):
            self.assertIn(needle, text)

    def test_quality_prompt_keeps_loop_stage_shared_invariants(self) -> None:
        flow_text = _read(FLOW_PROMPT_FULL)
        quality_text = _read(QUALITY_PROMPT)
        for needle in (
            'CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 $PLUGIN_DIR/skills/aidd-loop/runtime/loop_run.py',
            'CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 $PLUGIN_DIR/skills/aidd-loop/runtime/loop_step.py',
            "recoverable_blocked",
            "recovery_path",
            "retry_attempt",
            "policy_matrix_v2",
            "07_stage_result_contract_check.txt",
            "07_blocking_findings_policy_check.txt",
            "07_python_only_surface_check.txt",
            "seed_scope_cascade_detected",
            "tests_env_dependency_missing",
            "strict-shadow telemetry",
            "strict_shadow_classification",
            "softened=1",
            "--budget-seconds <N>",
        ):
            self.assertIn(needle, flow_text, msg=f"flow prompt lost shared invariant: {needle}")
            self.assertIn(needle, quality_text, msg=f"quality prompt missing shared invariant: {needle}")

    def test_quality_prompt_does_not_reference_plan_alias_path(self) -> None:
        text = _read(QUALITY_PROMPT)
        self.assertNotIn(".plan.md", text)

    def test_quality_prompt_defines_step9_artifacts_and_scorecards(self) -> None:
        text = _read(QUALITY_PROMPT)
        for needle in (
            "### Шаг 9. Quality Gate + Improvement Plan + Backlog Wave Planning",
            "09_quality_sources.txt",
            "09_final_state_check.txt",
            "09_code_scorecard.json",
            "09_artifact_scorecard.json",
            "09_code_findings.md",
            "09_artifact_findings.md",
            "09_acceptance_trace.md",
            "09_quality_findings.md",
            "09_quality_findings.json",
            "09_user_improvement_plan.md",
            "09_quality_gate.txt",
            "feature_final_state=<REACHED|NOT_REACHED>",
            "code_quality_gate=<PASS|WARN|FAIL>",
            "artifact_quality_gate=<PASS|WARN|FAIL>",
            "overall_quality_gate=<PASS|WARN|FAIL>",
            '"dimension": "acceptance_coverage"',
            '"dimension": "prd_quality"',
        ):
            self.assertIn(needle, text)

    def test_quality_prompt_defines_backlog_wave_contract(self) -> None:
        text = _read(QUALITY_PROMPT)
        for needle in (
            "09_backlog_before_head.txt",
            "09_backlog_parse.txt",
            "09_backlog_wave_draft.md",
            "09_backlog_after_head.txt",
            "09_backlog_wave_write.txt",
            "max(Wave NNN)+1",
            "insert_mode=after_revision_note",
            "allowed_plugin_write=BACKLOG_PATH",
            "## Wave <NNN> — E2E quality follow-ups for <TICKET> (<YYYY-MM-DD>)",
            "**W<NNN>-1 (P1) <short title>**",
            "**AC:** <acceptance criteria>",
            "**Deps:** <wave/task ids or ->>",
            "**Regression/tests:** `<commands>`",
            "**Evidence:** `<AUDIT_DIR/...>`",
            "**Effort:** S|M|L",
            "**Risk:** Low|Medium|High",
        ):
            self.assertIn(needle, text)

    def test_quality_prompt_overrides_step99_for_backlog_allowed_delta(self) -> None:
        text = _read(QUALITY_PROMPT)
        for needle in (
            "### Шаг 99. Post-run write-safety (quality override)",
            "99_plugin_allowed_delta.txt",
            "99_backlog_wave_integrity_check.txt",
            "allowed_plugin_paths=$BACKLOG_PATH",
            "PASS(no_plugin_delta)",
            "PASS(backlog_wave_written)",
            "WARN(backlog_wave_malformed)",
            "WARN(backlog_expected_but_missing)",
            "FAIL(plugin_write_safety_violation)",
            "FAIL(backlog_write_unexpected_delta)",
        ):
            self.assertIn(needle, text)

    def test_quality_prompt_has_machine_friendly_final_marker(self) -> None:
        text = _read(QUALITY_PROMPT)
        self.assertRegex(
            text.strip().splitlines()[-1],
            r"^`QUALITY_AUDIT_COMPLETE TST-002 status=<PASS\|WARN\|FAIL> wave=<WNNN\|none> feature_final_state=<REACHED\|NOT_REACHED>`$",
        )

    def test_quality_prompt_intentionally_contains_wave_markers(self) -> None:
        text = _read(QUALITY_PROMPT)
        self.assertIn("Wave <NNN>", text)
        self.assertIn("W<NNN>-1", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
