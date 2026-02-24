from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_PROMPT_FULL = REPO_ROOT / "aidd_test_flow_prompt_ralph_script_full.txt"
AUDIT_PROMPT_SMOKE = REPO_ROOT / "aidd_test_flow_prompt_ralph_script.txt"
RESEARCHER_AGENT = REPO_ROOT / "agents" / "researcher.md"
RESEARCHER_SKILL = REPO_ROOT / "skills" / "researcher" / "SKILL.md"

LOOP_STAGE_SKILLS = [
    REPO_ROOT / "skills" / "implement" / "SKILL.md",
    REPO_ROOT / "skills" / "review" / "SKILL.md",
    REPO_ROOT / "skills" / "qa" / "SKILL.md",
]

STAGE_SKILLS_FOR_ALIAS_GUARD = [
    REPO_ROOT / "skills" / "review-spec" / "SKILL.md",
    REPO_ROOT / "skills" / "tasks-new" / "SKILL.md",
    REPO_ROOT / "skills" / "qa" / "SKILL.md",
]

LEGACY_STAGE_ALIASES = [
    "/feature-dev-aidd:planner",
    "/feature-dev-aidd:tasklist-refiner",
    "/feature-dev-aidd:implementer",
    "/feature-dev-aidd:reviewer",
]

FORBIDDEN_DIRECT_MANUAL_RECOVERY_PATTERNS = [
    r"`python3\s+\$\{claude_plugin_root\}/skills/aidd-loop/runtime/preflight_prepare\.py`",
    r"(?:cat|tee|echo).{0,120}stage\.[a-z0-9_.-]*result\.json",
]
FORBIDDEN_LOOP_ALLOWED_TOOL_SURFACES = [
    "skills/aidd-loop/runtime/preflight_prepare.py",
    "skills/aidd-flow-state/runtime/stage_result.py",
]


def _read(path: Path) -> str:
    if not path.exists():
        raise AssertionError(f"missing contract file: {path}")
    return path.read_text(encoding="utf-8")


def _front_matter(path: Path) -> str:
    text = _read(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:idx])
    return ""


def _body(path: Path) -> str:
    text = _read(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[idx + 1 :])
    return text


class E2EPromptContractTests(unittest.TestCase):
    def test_prompts_do_not_contain_wave_readiness_markers(self) -> None:
        for prompt in (AUDIT_PROMPT_FULL, AUDIT_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertIsNone(
                re.search(r"\bWave\s+\d+\b", text, flags=re.IGNORECASE),
                msg=f"{prompt}: contains wave marker",
            )
            self.assertIsNone(
                re.search(r"\bW\d{2,}\b", text),
                msg=f"{prompt}: contains readiness marker W<number>",
            )

    def test_full_prompt_contains_mandatory_fixed_fs_catalog(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn("Каталог задач для шага 3 (выбрать ровно одну)", text)
        for task_id in ("FS-GA-01", "FS-MP-02", "FS-RBAC-03", "FS-ID-04", "FS-GRAPH-05"):
            self.assertIn(task_id, text, msg=f"missing fixed task id {task_id}")

    def test_full_prompt_contains_retry_seed_and_drift_guards(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn("retry-триггер разрешён только по текущему stage-return", text)
        self.assertIn("question retry для шага 6 запрещён", text)
        self.assertIn("prompt-flow drift (non-canonical stage orchestration)", text)
        self.assertIn("manual preflight/debug path", text)

    def test_prompt_policy_uses_stage_return_only_signal_extraction(self) -> None:
        for prompt in (AUDIT_PROMPT_FULL, AUDIT_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertIn(
                "не считать trigger-ом `Q*`/`AIDD:ANSWERS`/`Question` внутри вложенных артефактов",
                text,
                msg=f"{prompt}: missing nested-artifact trigger guard",
            )
            self.assertRegex(
                text.lower(),
                r"stage-level классификац|stage-return",
                msg=f"{prompt}: missing stage-return-only extraction policy",
            )

    def test_prompt_policy_has_stream_liveness_contract(self) -> None:
        full_text = _read(AUDIT_PROMPT_FULL).lower()
        smoke_text = _read(AUDIT_PROMPT_SMOKE).lower()
        for text, label in ((full_text, "full"), (smoke_text, "smoke")):
            self.assertIn("active_stream", text, msg=f"{label}: missing active_stream policy")
            self.assertIn("main log", text, msg=f"{label}: missing main log probe policy")
            self.assertRegex(
                text,
                r"stream.*jsonl|stream-jsonl",
                msg=f"{label}: missing stream jsonl probe policy",
            )

    def test_full_prompt_captures_watchdog_and_stream_path_attribution_rules(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn("stream_path_invalid", text)
        self.assertIn("stream_path_missing", text)
        self.assertIn("stream_path_resolution_incomplete", text)
        self.assertIn("fallback_scan=1", text)
        self.assertIn("stream_path_not_emitted_by_cli=1", text)
        self.assertIn("exit_code=143", text)
        self.assertIn("watchdog_marker=1", text)
        self.assertIn("watchdog_terminated", text)
        self.assertIn("result_count` в summary отсутствует", text)

    def test_prompts_define_conservative_severity_profile(self) -> None:
        for prompt in (AUDIT_PROMPT_FULL, AUDIT_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertIn("SEVERITY_PROFILE=conservative", text)
            self.assertIn("Severity profile `conservative`", text)

    def test_full_prompt_contains_step5_readiness_gate_contract(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn("#### 5.2.1 Step 5 Readiness Gate (hard-stop)", text)
        self.assertIn("05_precondition_block.txt", text)
        self.assertIn("answers_format=compact_q_codes|legacy_answer_alias", text)
        self.assertIn("`compact_q_codes` обязателен для retry payload", text)
        self.assertIn("prd_not_ready|open_questions_present|answers_format_invalid|research_not_ready", text)
        self.assertIn("NOT VERIFIED (readiness_gate_failed)", text)
        self.assertIn("NOT VERIFIED (upstream_readiness_gate_failed)", text)

    def test_full_prompt_requires_answer_normalization_and_compact_retry_payload(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn("legacy `Answer N:`/`Answer to QN:`", text)
        self.assertIn("AUDIT_DIR/<step>_questions_normalized.txt", text)
        self.assertIn("AIDD:ANSWERS Q1=C; Q2=B; Q3=C; Q4=A; Q5=C", text)
        self.assertIn("legacy префиксы `Answer N:` в retry запрещены", text)

    def test_full_prompt_marker_semantics_excludes_template_backup_noise(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn("marker semantics", text)
        self.assertIn("aidd/docs/tasklist/templates/**", text)
        self.assertIn("*.bak", text)
        self.assertIn("*.tmp", text)
        self.assertIn("report_noise", text)

    def test_prompt_launcher_policy_enforces_cwd_plugin_dir_and_verbose(self) -> None:
        for prompt in (AUDIT_PROMPT_FULL, AUDIT_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertIn('cd "$PROJECT_DIR"', text, msg=f"{prompt}: missing cwd launcher invariant")
            self.assertIn('--plugin-dir "$PLUGIN_DIR"', text, msg=f"{prompt}: missing plugin-dir launcher invariant")
            self.assertIn("--verbose --output-format stream-json", text, msg=f"{prompt}: missing stream-json verbose flags")
            self.assertIn('df -Pk "$PROJECT_DIR"', text, msg=f"{prompt}: missing disk preflight invariant")

    def test_full_prompt_step7_python_runtime_has_plugin_env_wiring(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn(
            'CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 $PLUGIN_DIR/skills/aidd-loop/runtime/loop_run.py',
            text,
        )
        self.assertIn(
            'CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 $PLUGIN_DIR/skills/aidd-loop/runtime/loop_step.py',
            text,
        )

    def test_full_prompt_step7_loop_step_command_uses_supported_flags_only(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        match = re.search(r"python3 \$PLUGIN_DIR/skills/aidd-loop/runtime/loop_step\.py[^\n`]*", text)
        self.assertIsNotNone(match, msg="missing loop_step.py command in full prompt step 7")
        command = str(match.group(0))
        self.assertNotIn("--max-iterations", command)
        self.assertNotIn("--blocked-policy", command)
        self.assertNotIn("--recoverable-block-retries", command)

    def test_prompts_do_not_define_model_override_policy(self) -> None:
        forbidden_patterns = (
            r"\b--model\b",
            r"\bglm[-_ ]?4\.?7",
            r"\bflashx?\b",
            r"\blight model\b",
            r"\bfast model\b",
        )
        for prompt in (AUDIT_PROMPT_FULL, AUDIT_PROMPT_SMOKE):
            text = _read(prompt)
            for pattern in forbidden_patterns:
                self.assertIsNone(
                    re.search(pattern, text, flags=re.IGNORECASE),
                    msg=f"{prompt}: must not contain model override policy ({pattern})",
                )

    def test_prompt_ralph_blocked_policy_parity(self) -> None:
        full_text = _read(AUDIT_PROMPT_FULL)
        smoke_text = _read(AUDIT_PROMPT_SMOKE)
        for text, label in ((full_text, "full"), (smoke_text, "smoke")):
            self.assertIn("BLOCKED_POLICY=strict|ralph", text, msg=f"{label}: missing blocked policy variable")
            self.assertIn("RECOVERABLE_BLOCK_RETRIES", text, msg=f"{label}: missing recoverable retry variable")
        self.assertIn("--blocked-policy $BLOCKED_POLICY", full_text)
        self.assertIn("--recoverable-block-retries $RECOVERABLE_BLOCK_RETRIES", full_text)
        self.assertIn("recoverable_blocked", full_text)
        self.assertIn("recovery_path", full_text)
        self.assertIn("retry_attempt", full_text)

    def test_prompt_research_pending_finalize_contract(self) -> None:
        for prompt in (AUDIT_PROMPT_FULL, AUDIT_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertIn("rlm_status_pending", text, msg=f"{prompt}: missing downstream pending reason contract")
            self.assertIn("baseline_missing", text, msg=f"{prompt}: missing baseline_missing drift guard")
            self.assertIn("AIDD:RLM_EVIDENCE", text, msg=f"{prompt}: missing RLM evidence section contract")
            self.assertRegex(
                text.lower(),
                r"bounded[\s\S]*finalize|finalize[\s\S]*bounded",
                msg=f"{prompt}: missing bounded finalize recovery expectation",
            )

    def test_prompt_retry_contract_removes_legacy_answers_alias(self) -> None:
        for prompt in (AUDIT_PROMPT_FULL, AUDIT_PROMPT_SMOKE):
            text = _read(prompt)
            self.assertIn("--plan-path", text, msg=f"{prompt}: missing plan-review-gate retry arg guard")
            self.assertNotIn("--answers", text, msg=f"{prompt}: removed spec-interview alias should not be documented")

    def test_full_prompt_cwd_recovery_stays_on_project_dir(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn("refusing to use plugin repository as workspace root", text)
        self.assertIn("исправь `cwd` на `PROJECT_DIR`", text)

    def test_full_prompt_has_preloop_fail_fast_gate(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn("Fail-fast gate (до шага 7)", text)
        self.assertIn("preloop_artifacts_missing", text)
        self.assertIn("шаги 7 и 8 пометить `NOT VERIFIED`", text)
        self.assertIn("NOT VERIFIED (upstream_seed_stage_failed)", text)
        self.assertIn("NOT VERIFIED (upstream_loop_stage_failed)", text)

    def test_prompts_enforce_runtime_drift_fail_fast_and_manual_stage_chain_preflight_forbidden(self) -> None:
        full_text = _read(AUDIT_PROMPT_FULL)
        smoke_text = _read(AUDIT_PROMPT_SMOKE)
        self.assertIn("runtime_path_missing_or_drift", full_text)
        self.assertIn("immediate `blocked`", full_text)
        self.assertIn("manual_stage_chain_preflight_forbidden", full_text)
        self.assertIn("runtime_path_missing_or_drift", smoke_text)
        self.assertIn("manual_stage_chain_preflight_forbidden", smoke_text)

    def test_full_prompt_requires_ralph_recoverable_probe_for_research_gate(self) -> None:
        text = _read(AUDIT_PROMPT_FULL)
        self.assertIn("rlm_links_empty_warn|rlm_status_pending", text)
        self.assertIn("research_gate_links_build_probe", text)
        self.assertIn("policy_mismatch(research_gate_recovery_path)", text)

    def test_researcher_contract_prefers_reviewed_and_plan_new(self) -> None:
        agent_text = _read(RESEARCHER_AGENT)
        skill_text = _read(RESEARCHER_SKILL)

        self.assertIn("Status: reviewed|pending|warn", agent_text)
        self.assertIn("/feature-dev-aidd:plan-new <ticket>", agent_text)
        self.assertIn("/feature-dev-aidd:plan-new <ticket>", skill_text)
        self.assertNotIn("/feature-dev-aidd:planner", agent_text)
        self.assertNotIn("/feature-dev-aidd:planner", skill_text)

    def test_loop_stage_skills_enforce_stage_chain_only_policy(self) -> None:
        for skill_path in LOOP_STAGE_SKILLS:
            text = _read(skill_path)
            lower = text.lower()
            body_lower = _body(skill_path).lower()
            frontmatter_lower = _front_matter(skill_path).lower()
            stage = skill_path.parent.name
            self.assertIn("forbidden", lower)
            self.assertRegex(lower, r"(manual|direct|вручн|прям).{0,220}preflight")
            self.assertRegex(lower, r"stage\." + re.escape(stage) + r"\.result\.json")
            self.assertIn("stage-chain", lower)
            self.assertIn("actions_apply.py", lower)
            self.assertIn(
                "python3 ${claude_plugin_root}/skills/aidd-flow-state/runtime/stage_result.py",
                lower,
            )
            self.assertNotIn(
                "python3 ${claude_plugin_root}/skills/aidd-loop/runtime/stage_result.py",
                lower,
            )
            self.assertNotIn(f"### `/feature-dev-aidd:{stage}", body_lower)
            self.assertRegex(
                body_lower,
                rf"python3\s+\$\{{claude_plugin_root\}}/skills/{re.escape(stage)}/runtime/",
            )
            self.assertNotRegex(
                body_lower,
                rf"python3\s+(?:\./)?skills/{re.escape(stage)}/runtime/",
            )
            for forbidden_surface in FORBIDDEN_LOOP_ALLOWED_TOOL_SURFACES:
                self.assertNotIn(
                    forbidden_surface,
                    frontmatter_lower,
                    msg=f"{skill_path}: frontmatter allowed-tools must not include {forbidden_surface}",
                )
            for pattern in FORBIDDEN_DIRECT_MANUAL_RECOVERY_PATTERNS:
                self.assertIsNone(
                    re.search(pattern, lower),
                    msg=f"{skill_path}: direct manual recovery pattern matched: {pattern}",
                )

    def test_stage_skill_guidance_avoids_legacy_stage_aliases(self) -> None:
        for skill_path in STAGE_SKILLS_FOR_ALIAS_GUARD:
            text = _read(skill_path)
            for alias in LEGACY_STAGE_ALIASES:
                self.assertNotIn(alias, text, msg=f"{skill_path}: contains legacy alias {alias}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
