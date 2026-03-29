from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY_PROMPT_FULL = REPO_ROOT / "docs" / "e2e" / "aidd_quality_audit_prompt_ralph_script_full.txt"
QUALITY_PROMPT_SMOKE = REPO_ROOT / "docs" / "e2e" / "aidd_quality_audit_prompt_ralph_script.txt"
PROMPT_BUILDER = REPO_ROOT / "tests" / "repo_tools" / "build_e2e_prompts.py"
PROMPT_FRAGMENTS_DIR = REPO_ROOT / "tests" / "repo_tools" / "e2e_prompt"


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"missing contract file: {path}")
    return path.read_text(encoding="utf-8")


class E2EQualityPromptContractTests(unittest.TestCase):
    def test_quality_prompt_fragments_exist(self) -> None:
        for rel in ("quality_base_contract.md", "quality_profile_full.md", "quality_profile_smoke.md"):
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

    def test_quality_prompt_outputs_exist(self) -> None:
        self.assertTrue(QUALITY_PROMPT_FULL.exists(), msg=f"missing quality full prompt output: {QUALITY_PROMPT_FULL}")
        self.assertTrue(
            QUALITY_PROMPT_SMOKE.exists(),
            msg=f"missing quality smoke prompt output: {QUALITY_PROMPT_SMOKE}",
        )

    def test_quality_prompts_render_must_read_manifest(self) -> None:
        for prompt in (QUALITY_PROMPT_FULL, QUALITY_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertNotIn("{{MUST_READ_MANIFEST}}", text, msg=f"{prompt}: unresolved MUST_READ placeholder")
            self.assertIn(
                "$PLUGIN_DIR/skills/aidd-core/templates/workspace-agents.md",
                text,
                msg=f"{prompt}: must-read manifest not embedded",
            )

    def test_quality_full_contains_step9_and_backlog_contract(self) -> None:
        text = _read(QUALITY_PROMPT_FULL)
        self.assertIn("## 9) Quality Gate + User Improvement Plan + Backlog Wave Planning", text)
        self.assertIn("WAVE_WRITE_MODE=disabled|on-findings|always", text)
        self.assertIn("единственный разрешённый plugin-side write: `BACKLOG_PATH`", text)
        self.assertIn("запись в `BACKLOG_PATH` разрешена только после готового `AUDIT_DIR/09_quality_gate.txt`", text)

    def test_quality_full_includes_required_step9_artifacts(self) -> None:
        text = _read(QUALITY_PROMPT_FULL)
        required = (
            "09_quality_sources.txt",
            "09_final_state_check.txt",
            "09_code_scorecard.json",
            "09_artifact_scorecard.json",
            "09_acceptance_trace.md",
            "09_quality_findings.md",
            "09_quality_findings.json",
            "09_user_improvement_plan.md",
            "09_quality_gate.txt",
        )
        for artifact in required:
            self.assertIn(artifact, text, msg=f"missing quality artifact in full prompt: {artifact}")

    def test_quality_prompts_use_profile_variable_only(self) -> None:
        for prompt in (QUALITY_PROMPT_FULL, QUALITY_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertIn("PROFILE=", text, msg=f"{prompt}: missing PROFILE variable")
            self.assertNotIn("QUALITY_PROFILE", text, msg=f"{prompt}: QUALITY_PROFILE must not be used")

    def test_quality_smoke_disables_wave_write(self) -> None:
        text = _read(QUALITY_PROMPT_SMOKE)
        self.assertIn("WAVE_WRITE_MODE=disabled", text)
        self.assertIn("`wave_created` всегда `0`", text)
        self.assertIn("В `BACKLOG_PATH` не писать.", text)
        self.assertIn("wave_created=0", text)
        self.assertIn("wave_id=-", text)

    def test_quality_prompts_define_findings_classes(self) -> None:
        for prompt in (QUALITY_PROMPT_FULL, QUALITY_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertIn("systemic_aidd_gap", text, msg=f"{prompt}: missing systemic class")
            self.assertIn("product_output_gap", text, msg=f"{prompt}: missing product class")
            self.assertIn("env_or_runner_gap", text, msg=f"{prompt}: missing env class")

    def test_quality_prompts_emit_dual_markers(self) -> None:
        pattern = re.compile(
            r"QUALITY_AUDIT_COMPLETE\s+<TICKET>\s+status=<PASS\|WARN\|FAIL>\s+wave=<[^>]+>\s+feature_final_state=<REACHED\|NOT_REACHED>"
        )
        for prompt in (QUALITY_PROMPT_FULL, QUALITY_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertRegex(text, pattern, msg=f"{prompt}: missing quality completion marker")
            self.assertIn("AUDIT_COMPLETE <TICKET>", text, msg=f"{prompt}: missing legacy completion marker")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
