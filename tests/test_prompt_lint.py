import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from textwrap import dedent
import unittest
from typing import Dict, Optional

from .helpers import REPO_ROOT

STAGE_SKILLS = [
    "aidd-init",
    "idea-new",
    "researcher",
    "plan-new",
    "review-spec",
    "spec-interview",
    "tasks-new",
    "implement",
    "review",
    "qa",
    "status",
]

STAGE_RUNTIME_ENTRYPOINT = {
    "aidd-init": "skills/aidd-init/runtime/init.py",
    "idea-new": "skills/idea-new/runtime/analyst_check.py",
    "researcher": "skills/researcher/runtime/research.py",
    "plan-new": "skills/plan-new/runtime/research_check.py",
    "review-spec": "skills/review-spec/runtime/prd_review_cli.py",
    "spec-interview": "skills/spec-interview/runtime/spec_interview.py",
    "tasks-new": "skills/tasks-new/runtime/tasks_new.py",
    "implement": "skills/implement/runtime/implement_run.py",
    "review": "skills/review/runtime/review_run.py",
    "qa": "skills/qa/runtime/qa_run.py",
    "status": "skills/status/runtime/status.py",
}

AGENT_NAMES = [
    "analyst",
    "researcher",
    "planner",
    "validator",
    "plan-reviewer",
    "prd-reviewer",
    "spec-interview-writer",
    "tasklist-refiner",
    "implementer",
    "reviewer",
    "qa",
]
STAGE_SUBAGENT = {
    "idea-new": "analyst",
    "researcher": "researcher",
    "spec-interview": "spec-interview-writer",
    "tasks-new": "tasklist-refiner",
    "implement": "implementer",
    "review": "reviewer",
    "qa": "qa",
}
RLM_PRELOAD_ROLES = {
    "analyst",
    "planner",
    "plan-reviewer",
    "prd-reviewer",
    "researcher",
    "reviewer",
    "spec-interview-writer",
    "tasklist-refiner",
    "validator",
}

CRITICAL_TEMPLATE_FILES = [
    "skills/aidd-core/templates/workspace-agents.md",
    "skills/aidd-core/templates/stage-lexicon.md",
    "skills/aidd-core/templates/index.schema.json",
    "skills/aidd-core/templates/context-pack.template.md",
    "skills/aidd-loop/templates/loop-pack.template.md",
    "skills/idea-new/templates/prd.template.md",
    "skills/plan-new/templates/plan.template.md",
    "skills/researcher/templates/research.template.md",
    "skills/spec-interview/templates/spec.template.yaml",
    "skills/tasks-new/templates/tasklist.template.md",
]


def build_agent(name: str) -> str:
    loop_skill = "" if name not in {"implementer", "reviewer", "qa"} else "\n  - feature-dev-aidd:aidd-loop"
    rlm_skill = "" if name not in RLM_PRELOAD_ROLES else "\n  - feature-dev-aidd:aidd-rlm"
    stage_research_skill = "" if name != "researcher" else "\n  - feature-dev-aidd:aidd-stage-research"
    tools = "Read, Edit, Write"
    return (
        dedent(
            f"""
            ---
            name: {name}
            description: test agent
            lang: ru
            prompt_version: 1.0.0
            source_version: 1.0.0
            tools: {tools}
            skills:
              - feature-dev-aidd:aidd-core
              - feature-dev-aidd:aidd-policy{rlm_skill}{stage_research_skill}{loop_skill}
            model: inherit
            permissionMode: inherit
            ---

            ## Контекст
            Output follows aidd-core skill.

            ## Входные артефакты
            - item

            ## Автоматизация
            Text.

            ## Пошаговый план
            1. step

            ## Fail-fast и вопросы
            Text.

            ## Формат ответа
            Output follows aidd-core skill.
            """
        ).strip()
        + "\n"
    )


def build_stage_skill(stage: str, *, lang: str = "ru") -> str:
    description = f"Test skill for {stage}."
    argument_hint = "<TICKET>"
    prompt_version = "1.0.0"
    source_version = "1.0.0"
    runtime_tool = f"Bash(python3 ${{CLAUDE_PLUGIN_ROOT}}/{STAGE_RUNTIME_ENTRYPOINT[stage]} *)"
    disable_invocation = "false" if stage == "status" else "true"
    loop_ref = " and `feature-dev-aidd:aidd-loop`" if stage in {"implement", "review", "qa"} else ""

    lines = [
        "---",
        f"name: {stage}",
        f"description: {description}",
        f"argument-hint: {argument_hint}",
        f"lang: {lang}",
        f"prompt_version: {prompt_version}",
        f"source_version: {source_version}",
        "allowed-tools:",
        "  - Read",
        f'  - "{runtime_tool}"',
        "model: inherit",
        f"disable-model-invocation: {disable_invocation}",
        "user-invocable: true",
    ]
    lines.append("---")
    lines.append("")
    lines.append(f"Follow `feature-dev-aidd:aidd-core`{loop_ref}.")
    lines.append("")
    lines.append("## Steps")
    if stage in {"implement", "review", "qa"}:
        lines.append("1. Stage-chain-only policy: execute only via canonical stage-chain.")
        lines.append(
            "2. Internal preflight/postflight are orchestration details; operators run only canonical stage runtime entrypoint."
        )
        lines.append(
            f"3. Manual write/create of `stage.{stage}.result.json` is forbidden; stage-chain/postflight writes it. [AIDD_LOOP_POLICY:MANUAL_STAGE_RESULT_FORBIDDEN]"
        )
        lines.append(
            "4. Runtime-path safety: if output contains `can't open file .../skills/.../runtime/...`, return BLOCKED `runtime_path_missing_or_drift`."
        )
        lines.append(
            "5. Retry safety: do not rerun the same failing command without new evidence."
        )
        lines.append(
            "6. Read order after preflight artifacts: readmap -> loop pack -> review pack -> rolling context pack."
        )
        lines.append(f"7. Run subagent `feature-dev-aidd:{STAGE_SUBAGENT[stage]}`.")
        lines.append(f"8. Fill actions.json: create `aidd/reports/actions/<ticket>/<scope_key>/{stage}.actions.json`.")
        lines.append(
            "9. Canonical stage-chain: internal preflight -> stage runtime -> actions_apply.py/postflight -> python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py. [AIDD_LOOP_POLICY:CANONICAL_STAGE_RESULT_PATH]"
        )
        lines.append(
            "10. Non-canonical stage-result path under `skills/aidd-loop/runtime/` is forbidden. [AIDD_LOOP_POLICY:NON_CANONICAL_STAGE_RESULT_FORBIDDEN]"
        )
    elif stage == "plan-new":
        lines.append("1. Run subagent `feature-dev-aidd:planner`.")
        lines.append("2. Run subagent `feature-dev-aidd:validator`.")
    elif stage == "review-spec":
        lines.append("1. Run subagent `feature-dev-aidd:plan-reviewer`.")
        lines.append("2. Run subagent `feature-dev-aidd:prd-reviewer`.")
    elif stage in STAGE_SUBAGENT:
        lines.append(f"1. Run subagent `feature-dev-aidd:{STAGE_SUBAGENT[stage]}` after stage orchestration.")
    else:
        lines.append("1. Do the work.")
    lines.append("")
    lines.append("## Command contracts")
    lines.append(f"### `python3 ${{CLAUDE_PLUGIN_ROOT}}/{STAGE_RUNTIME_ENTRYPOINT[stage]}`")
    lines.append("- When to run: always for canonical stage orchestration.")
    lines.append("- Inputs: `--ticket <ticket>` plus stage-specific optional flags.")
    lines.append("- Outputs: stage artifacts and structured status output.")
    lines.append("- Failure mode: non-zero exit with actionable error message.")
    lines.append("- Next action: resolve input/gate issues and rerun the same entrypoint.")
    if stage in {"implement", "review", "qa"}:
        lines.append("")
        lines.append("### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`")
        lines.append("- When to run: postflight step in stage-chain; not a manual recovery shortcut.")
        lines.append("- Inputs: ticket + scope/work-item context + validated actions file.")
        lines.append("- Outputs: applied actions, progress updates, and stage summary artifacts.")
        lines.append("- Failure mode: DocOps/apply validation failure.")
        lines.append("- Next action: inspect apply log, fix actions, rerun stage-chain.")
    lines.append("")
    lines.append("## Additional resources")
    lines.append(
        f"- Runtime owner: [runtime/{Path(STAGE_RUNTIME_ENTRYPOINT[stage]).name}](runtime/{Path(STAGE_RUNTIME_ENTRYPOINT[stage]).name}) (when: orchestration behavior needs clarification; why: confirm canonical flags and output contract)."
    )
    lines.append("")
    return "\n".join(lines)


def build_core_skill() -> str:
    return (
        dedent(
            """
            ---
            name: aidd-core
            description: Core runtime policy for skills.
            lang: en
            model: inherit
            user-invocable: false
            ---

            ## Command contracts
            ### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/skill_contract_validate.py`
            - When to run: before release checks for prompt/skill contract drift.
            - Inputs: repository root and optional validation scope filters.
            - Outputs: deterministic contract diagnostics.
            - Failure mode: non-zero exit on missing contract fields/sections.
            - Next action: fix reported contract gaps and rerun.

            ## Additional resources
            - Policy owner: [../aidd-policy/SKILL.md](../aidd-policy/SKILL.md) (when: output/question/read policy details are needed; why: avoid duplicating policy prose in topology skill).
            """
        ).strip()
        + "\n"
    )


def build_docio_skill() -> str:
    return (
        dedent(
            """
            ---
            name: aidd-docio
            description: Shared DocIO ownership for markdown/actions/context runtime tools.
            lang: en
            model: inherit
            user-invocable: false
            ---

            ## Command contracts
            ### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/md_slice.py`
            - When to run: when bounded markdown excerpt is needed.
            - Inputs: source markdown path plus selectors.
            - Outputs: deterministic section slice.
            - Failure mode: invalid file path or selector.
            - Next action: fix selectors and rerun.

            ## Additional resources
            - DocIO flow: [references/actions-flow.md](references/actions-flow.md) (when: actions apply/validate sequence is unclear; why: keep postflight behavior deterministic).
            """
        ).strip()
        + "\n"
    )


def build_flow_state_skill() -> str:
    return (
        dedent(
            """
            ---
            name: aidd-flow-state
            description: Shared flow/state ownership for stage state and progress lifecycle runtime tools.
            lang: en
            model: inherit
            user-invocable: false
            ---

            ## Command contracts
            ### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py`
            - When to run: stage-chain postflight stage-result emission only.
            - Inputs: canonical postflight payload.
            - Outputs: deterministic stage result artifact.
            - Failure mode: invalid payload schema.
            - Next action: fix payload and rerun stage-chain.

            ## Additional resources
            - Stage lifecycle: [references/stage-lifecycle.md](references/stage-lifecycle.md) (when: stage result/status sequencing is unclear; why: confirm canonical flow-state ownership semantics).
            """
        ).strip()
        + "\n"
    )


def build_observability_skill() -> str:
    return (
        dedent(
            """
            ---
            name: aidd-observability
            description: Shared observability ownership for diagnostics and reporting runtime tools.
            lang: en
            model: inherit
            user-invocable: false
            ---

            ## Command contracts
            ### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py`
            - When to run: when env/runtime path drift is suspected.
            - Inputs: optional diagnostics flags.
            - Outputs: deterministic environment health diagnostics.
            - Failure mode: required dependency/path checks fail.
            - Next action: fix environment and rerun doctor.

            ## Additional resources
            - Diagnostics notes: [references/diagnostics.md](references/diagnostics.md) (when: doctor/tests-log output meaning is unclear; why: keep troubleshooting deterministic).
            """
        ).strip()
        + "\n"
    )


def build_loop_skill() -> str:
    return (
        dedent(
            """
            ---
            name: aidd-loop
            description: Loop discipline for implement/review/qa.
            lang: en
            model: inherit
            user-invocable: false
            ---

            ## Command contracts
            ### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_pack.py`
            - When to run: before loop stage execution to assemble bounded evidence.
            - Inputs: ticket/scope context and upstream artifacts.
            - Outputs: deterministic loop pack payload.
            - Failure mode: missing/malformed upstream artifacts.
            - Next action: fix prerequisites and rerun pack generation.

            ## Additional resources
            - Loop reference: [reference.md](reference.md) (when: stage-chain/fallback behavior needs clarification; why: keep loop orchestration inside canonical boundaries).
            """
        ).strip()
        + "\n"
    )


def build_policy_skill() -> str:
    return (
        dedent(
            """
            ---
            name: aidd-policy
            description: Shared policy contract for output format, read discipline, and question protocol.
            lang: en
            model: inherit
            user-invocable: false
            ---

            ## Output contract (required)
            - Status: ...
            - Work item key: ...
            - Artifacts updated: ...
            - Tests: ...
            - Blockers/Handoff: ...
            - Next actions: ...
            - AIDD:READ_LOG: ...
            - AIDD:ACTIONS_LOG: ...

            ## Question format
            ```
            Question N (Blocker|Clarification): ...
            Why: ...
            Options: A) ... B) ...
            Default: ...
            ```

            ## Command contracts
            ### `Policy output contract application`
            - When to run: before final response for every stage/subagent output.
            - Inputs: stage result plus artifacts/tests/blockers evidence.
            - Outputs: deterministic output skeleton with required fields.
            - Failure mode: missing or inconsistent contract fields.
            - Next action: normalize response shape and rerun final composition.

            ### `Policy question protocol`
            - When to run: only when blocker/clarification is unavoidable after artifact-first checks.
            - Inputs: verified blocker context with options and default path.
            - Outputs: deterministic Question/Why/Options/Default prompt.
            - Failure mode: free-form question without options/default.
            - Next action: rewrite question to policy format before asking.

            ## Additional resources
            - Output contract guide: [references/output-contract.md](references/output-contract.md) (when: response fields are uncertain; why: keep status/artifact/test/blocker reporting deterministic).
            """
        ).strip()
        + "\n"
    )


def build_rlm_skill() -> str:
    return (
        dedent(
            """
            ---
            name: aidd-rlm
            description: Shared RLM preload skill for subagents.
            lang: en
            model: inherit
            user-invocable: false
            ---

            ## Command contracts
            ### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py`
            - When to run: for targeted evidence extraction from RLM artifacts.
            - Inputs: ticket/query selectors.
            - Outputs: bounded RLM evidence slice payload.
            - Failure mode: missing pack/worklist artifacts.
            - Next action: repair missing artifacts and rerun slice.

            ## Additional resources
            - RLM finalize runtime: [runtime/rlm_finalize.py](runtime/rlm_finalize.py) (when: pending->ready transitions are unclear; why: align finalize ownership and handoff path).
            """
        ).strip()
        + "\n"
    )


def build_stage_research_skill() -> str:
    return (
        dedent(
            """
            ---
            name: aidd-stage-research
            description: Stage-level research reference preload.
            lang: en
            model: inherit
            user-invocable: false
            ---

            ## Command contracts
            ### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py`
            - When to run: handoff path when stage reports pending RLM readiness.
            - Inputs: ticket from deterministic pending status output.
            - Outputs: finalized readiness status or bounded pending reason.
            - Failure mode: unresolved upstream RLM integrity issues.
            - Next action: fix upstream targets/manifest/worklist and rerun finalize.

            ## Additional resources
            - Stage owner skill: [../researcher/SKILL.md](../researcher/SKILL.md) (when: stage-vs-shared ownership boundary is unclear; why: keep researcher orchestration separate from shared RLM runtime ownership).
            """
        ).strip()
        + "\n"
    )


class PromptLintTests(unittest.TestCase):
    def run_lint(
        self,
        root: Path,
        *,
        env_override: Optional[Dict[str, str]] = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        if env_override:
            env.update(env_override)
        return subprocess.run(
            [sys.executable, str(REPO_ROOT / "tests" / "repo_tools" / "lint-prompts.py"), "--root", str(root)],
            text=True,
            capture_output=True,
            env=env,
            cwd=REPO_ROOT,
        )

    def write_prompts(
        self,
        root: Path,
        agent_override: Optional[Dict[str, str]] = None,
        skill_override: Optional[Dict[str, str]] = None,
    ) -> None:
        agent_override = agent_override or {}
        skill_override = skill_override or {}

        for agent_name in AGENT_NAMES:
            agent_path = root / "agents" / f"{agent_name}.md"
            agent_path.parent.mkdir(parents=True, exist_ok=True)
            content = agent_override.get(agent_name, build_agent(agent_name))
            agent_path.write_text(content, encoding="utf-8")

        skills_root = root / "skills"
        skills_root.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-core" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-docio" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-flow-state" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-observability" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-policy" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-loop" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-rlm" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-stage-research" / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
        (skills_root / "aidd-core" / "SKILL.md").write_text(
            skill_override.get("aidd-core", build_core_skill()), encoding="utf-8"
        )
        (skills_root / "aidd-docio" / "SKILL.md").write_text(
            skill_override.get("aidd-docio", build_docio_skill()), encoding="utf-8"
        )
        (skills_root / "aidd-flow-state" / "SKILL.md").write_text(
            skill_override.get("aidd-flow-state", build_flow_state_skill()), encoding="utf-8"
        )
        (skills_root / "aidd-observability" / "SKILL.md").write_text(
            skill_override.get("aidd-observability", build_observability_skill()), encoding="utf-8"
        )
        (skills_root / "aidd-policy" / "SKILL.md").write_text(
            skill_override.get("aidd-policy", build_policy_skill()), encoding="utf-8"
        )
        (skills_root / "aidd-loop" / "SKILL.md").write_text(
            skill_override.get("aidd-loop", build_loop_skill()), encoding="utf-8"
        )
        (skills_root / "aidd-rlm" / "SKILL.md").write_text(
            skill_override.get("aidd-rlm", build_rlm_skill()), encoding="utf-8"
        )
        (skills_root / "aidd-stage-research" / "SKILL.md").write_text(
            skill_override.get("aidd-stage-research", build_stage_research_skill()), encoding="utf-8"
        )

        for stage in STAGE_SKILLS:
            skill_path = skills_root / stage / "SKILL.md"
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            content = skill_override.get(stage, build_stage_skill(stage))
            skill_path.write_text(content, encoding="utf-8")
            runtime_entry = skills_root / stage / "runtime" / Path(STAGE_RUNTIME_ENTRYPOINT[stage]).name
            runtime_entry.parent.mkdir(parents=True, exist_ok=True)
            runtime_entry.write_text("from __future__ import annotations\n", encoding="utf-8")

        self.write_baseline(root)
        self.write_policy(root)
        self.write_docs(root)
        self.write_plugin_manifest(root)

    def write_baseline(self, root: Path) -> None:
        rows = []
        for stage in STAGE_SKILLS:
            rows.append(
                {
                    "stage": stage,
                    "command_path": f"commands/{stage}.md",
                    "skill_path": f"skills/{stage}/SKILL.md",
                    "frontmatter": {
                        "name": stage,
                        "allowed-tools": [
                            "Read",
                            f"Bash(python3 ${{CLAUDE_PLUGIN_ROOT}}/{STAGE_RUNTIME_ENTRYPOINT[stage]} *)",
                        ],
                        "model": "inherit",
                        "prompt_version": "1.0.0",
                        "source_version": "1.0.0",
                        "lang": "ru",
                        "argument-hint": "<TICKET>",
                    },
                }
            )
        payload = {
            "schema": "aidd.commands_to_skills_frontmatter.v1",
            "rows": rows,
        }
        out_dir = root / "dev" / "reports" / "migrations"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "commands_to_skills_frontmatter.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    def write_policy(self, root: Path) -> None:
        policy_path = root / "docs" / "skill-language.md"
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_text("Skills are EN-only.\n", encoding="utf-8")

    def write_plugin_manifest(self, root: Path) -> None:
        skills = sorted(f"./skills/{path.parent.name}" for path in (root / "skills").glob("*/SKILL.md"))
        agents = sorted(f"./agents/{path.name}" for path in (root / "agents").glob("*.md"))
        manifest = {
            "name": "test-plugin",
            "skills": skills,
            "agents": agents,
        }
        plugin_manifest = root / ".claude-plugin" / "plugin.json"
        plugin_manifest.parent.mkdir(parents=True, exist_ok=True)
        plugin_manifest.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    def write_docs(self, root: Path) -> None:
        for rel_path in CRITICAL_TEMPLATE_FILES:
            target = root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel_path.endswith("conventions.md"):
                content = "# Conventions\n\n## Evidence read policy (pack-first, rolling)\n"
            elif rel_path.endswith("context-pack.template.md"):
                content = "# Context Pack Template\n"
            elif rel_path.endswith("loop-pack.template.md"):
                content = "# Loop Pack Template\n"
            elif rel_path.endswith("AGENTS.md"):
                content = "# AGENTS\n"
            else:
                content = "# Template\n"
            target.write_text(content, encoding="utf-8")

        index_schema_path = root / "skills" / "aidd-core" / "templates" / "index.schema.json"
        index_schema_path.parent.mkdir(parents=True, exist_ok=True)
        index_schema_path.write_text(
            json.dumps(
                {
                    "schema": "aidd.ticket.v1",
                    "required": [
                        "schema",
                        "ticket",
                        "slug",
                        "stage",
                        "updated",
                        "summary",
                        "artifacts",
                        "reports",
                        "next3",
                        "open_questions",
                        "risks_top5",
                        "checks",
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        index_schema = root / "docs" / "index" / "schema.json"
        index_schema.parent.mkdir(parents=True, exist_ok=True)
        index_schema.write_text(
            json.dumps(
                {
                    "schema": "aidd.ticket.v1",
                    "required": [
                        "schema",
                        "ticket",
                        "slug",
                        "stage",
                        "updated",
                        "summary",
                        "artifacts",
                        "reports",
                        "next3",
                        "open_questions",
                        "risks_top5",
                        "checks",
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_valid_prompts_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root)
            result = self.run_lint(root)
            self.assertEqual(
                result.returncode,
                0,
                msg=f"stdout: {result.stdout}\nstderr: {result.stderr}",
            )

    def test_missing_section_fails(self) -> None:
        broken_agent = dedent(
            """
            ---
            name: implementer
            description: bad agent
            lang: ru
            prompt_version: 1.0.0
            source_version: 1.0.0
            tools: Read, Edit, Write
            skills:
              - feature-dev-aidd:aidd-core
              - feature-dev-aidd:aidd-policy
              - feature-dev-aidd:aidd-loop
            model: inherit
            permissionMode: inherit
            ---

            ## Контекст
            Text.

            ## Входные артефакты
            - item

            ## Пошаговый план
            1. step

            ## Fail-fast и вопросы
            Text.

            ## Формат ответа
            Output follows aidd-core skill.
            """
        ).strip() + "\n"

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"implementer": broken_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing section", result.stderr)

    def test_missing_user_invocable_fails(self) -> None:
        bad_skill = build_stage_skill("idea-new").replace("user-invocable: true", "", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"idea-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("user-invocable", result.stderr)

    def test_duplicate_front_matter_key_fails(self) -> None:
        duplicate_agent = build_agent("implementer").replace(
            "prompt_version: 1.0.0",
            "prompt_version: 1.0.0\nprompt_version: 1.0.1",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"implementer": duplicate_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate front matter key", result.stderr)

    def test_invalid_status_fails(self) -> None:
        bad_skill = build_stage_skill("plan-new").replace(
            "## Steps\n1. Run subagent `feature-dev-aidd:planner`.\n2. Run subagent `feature-dev-aidd:validator`.",
            "## Steps\nStatus: approved",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"plan-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown status", result.stderr)

    def test_html_ticket_escape_fails(self) -> None:
        bad_skill = build_stage_skill("plan-new").replace("--ticket <ticket>", "--ticket &lt;ticket&gt;", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"plan-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("replace HTML escape", result.stderr)

    def test_parity_fails(self) -> None:
        bad_skill = build_stage_skill("review").replace("- Read", "- Edit", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"review": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("allowed-tools does not match baseline", result.stderr)

    def test_skill_length_limit_fails(self) -> None:
        long_tail = "\n".join([f"Extra line {idx}" for idx in range(340)])
        long_skill = build_stage_skill("qa") + "\n" + long_tail + "\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"qa": long_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exceeds max skill length", result.stderr)

    def test_missing_command_contracts_fails(self) -> None:
        bad_skill = build_stage_skill("plan-new").replace("## Command contracts", "## Contracts", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"plan-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing `## Command contracts` section", result.stderr)

    def test_shared_skill_missing_name_fails(self) -> None:
        bad_skill = build_docio_skill().replace("name: aidd-docio\n", "", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"aidd-docio": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing `name`", result.stderr)

    def test_shared_skill_missing_command_contracts_fails(self) -> None:
        bad_skill = build_rlm_skill().replace("## Command contracts", "## Contracts", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"aidd-rlm": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing `## Command contracts` section", result.stderr)

    def test_shared_skill_command_contracts_require_canonical_runtime_heading(self) -> None:
        bad_skill = build_docio_skill().replace(
            "### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/md_slice.py`",
            "### `not-a-runtime-command`",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"aidd-docio": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must use canonical runtime headings", result.stderr)

    def test_additional_resources_requires_when_why(self) -> None:
        bad_skill = build_stage_skill("status").replace(
            "(when: orchestration behavior needs clarification; why: confirm canonical flags and output contract).",
            "(details).",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"status": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Additional resources bullet must include `when:` and `why:`", result.stderr)

    def test_shared_skill_additional_resources_requires_when_why(self) -> None:
        bad_skill = build_policy_skill().replace(
            "(when: response fields are uncertain; why: keep status/artifact/test/blocker reporting deterministic).",
            "(details).",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"aidd-policy": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Additional resources bullet must include `when:` and `why:`", result.stderr)

    def test_missing_agent_preload_skill_fails(self) -> None:
        broken = build_agent("analyst").replace("feature-dev-aidd:aidd-core", "feature-dev-aidd:missing-skill", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"analyst": broken})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing preload skill", result.stderr)

    def test_missing_role_based_rlm_preload_fails(self) -> None:
        broken = build_agent("analyst")
        broken = broken.replace("\n- feature-dev-aidd:aidd-rlm", "", 1)
        broken = broken.replace("\n  - feature-dev-aidd:aidd-rlm", "", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"analyst": broken})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing role-based preload feature-dev-aidd:aidd-rlm", result.stderr)

    def test_forbidden_role_based_rlm_preload_fails(self) -> None:
        broken = build_agent("implementer").replace(
            "  - feature-dev-aidd:aidd-policy",
            "  - feature-dev-aidd:aidd-policy\n  - feature-dev-aidd:aidd-rlm",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"implementer": broken})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("preload feature-dev-aidd:aidd-rlm is forbidden for role `implementer`", result.stderr)

    def test_agent_stage_local_tool_redirect_ref_fails(self) -> None:
        bad_agent = (
            dedent(
                """
                ---
                name: researcher
                description: bad
                lang: ru
                prompt_version: 1.0.0
                source_version: 1.0.0
                tools: Read, Edit, Write, Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-nodes-build.sh *)
                skills:
                  - feature-dev-aidd:aidd-core
                  - feature-dev-aidd:aidd-policy
                  - feature-dev-aidd:aidd-rlm
                model: inherit
                permissionMode: inherit
                ---

                ## Контекст
                Output follows aidd-core skill.

                ## Входные артефакты
                - item

                ## Автоматизация
                Text.

                ## Пошаговый план
                1. step

                ## Fail-fast и вопросы
                Text.

                ## Формат ответа
                Output follows aidd-core skill.
                """
            ).strip()
            + "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"researcher": bad_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("agent tools must use", result.stderr)

    def test_agent_wrapper_tool_ref_fails(self) -> None:
        bad_agent = (
            dedent(
                """
                ---
                name: researcher
                description: bad
                lang: ru
                prompt_version: 1.0.0
                source_version: 1.0.0
                tools: Read, Edit, Write, Bash(${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/reports-pack.sh *)
                skills:
                  - feature-dev-aidd:aidd-core
                  - feature-dev-aidd:aidd-policy
                  - feature-dev-aidd:aidd-rlm
                model: inherit
                permissionMode: inherit
                ---

                ## Контекст
                Output follows aidd-core skill.

                ## Входные артефакты
                - item

                ## Автоматизация
                Text.

                ## Пошаговый план
                1. step

                ## Fail-fast и вопросы
                Text.

                ## Формат ответа
                Output follows aidd-core skill.
                """
            ).strip()
            + "\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"researcher": bad_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not call stage/shared script internals directly", result.stderr)

    def test_loop_agent_manual_preflight_path_in_body_is_telemetry_only(self) -> None:
        bad_agent = build_agent("implementer") + "\nНе используй skills/aidd-loop/runtime/preflight_prepare.py напрямую.\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"implementer": bad_agent})
            result = self.run_lint(root)
            self.assertEqual(result.returncode, 0, msg=f"stdout: {result.stdout}\nstderr: {result.stderr}")

    def test_loop_agent_manual_stage_result_path_in_body_fails(self) -> None:
        bad_agent = build_agent("qa") + "\nНе создавай stage.qa.result.json вручную.\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"qa": bad_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("loop agent must not duplicate stage path-level orchestration policy", result.stderr)
            self.assertIn("stage.qa.result.json", result.stderr)

    def test_agent_self_stage_slash_link_in_body_fails_for_implementer(self) -> None:
        bad_agent = build_agent("implementer") + "\nДля запуска используй /feature-dev-aidd:implement.\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"implementer": bad_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("agent must not reference own stage slash command", result.stderr)
            self.assertIn("/feature-dev-aidd:implement", result.stderr)

    def test_agent_self_stage_slash_link_in_body_fails_for_qa(self) -> None:
        bad_agent = build_agent("qa") + "\nВыполни /feature-dev-aidd:qa перед отчётом.\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"qa": bad_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("agent must not reference own stage slash command", result.stderr)
            self.assertIn("/feature-dev-aidd:qa", result.stderr)

    def test_agent_self_stage_slash_link_in_body_fails_for_spec_interview_writer(self) -> None:
        bad_agent = build_agent("spec-interview-writer") + "\nЕсли данных нет, запусти /feature-dev-aidd:spec-interview.\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"spec-interview-writer": bad_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("agent must not reference own stage slash command", result.stderr)
            self.assertIn("/feature-dev-aidd:spec-interview", result.stderr)

    def test_agent_non_self_stage_handoff_link_is_allowed(self) -> None:
        good_agent = build_agent("researcher") + "\nПри готовности укажи /feature-dev-aidd:plan-new <ticket>.\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"researcher": good_agent})
            result = self.run_lint(root)
            self.assertEqual(result.returncode, 0, msg=f"stdout: {result.stdout}\nstderr: {result.stderr}")

    def test_agent_self_stage_slash_link_in_description_fails(self) -> None:
        bad_agent = build_agent("implementer").replace(
            "description: test agent",
            "description: use /feature-dev-aidd:implement for orchestration",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"implementer": bad_agent})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("agent must not reference own stage slash command", result.stderr)
            self.assertIn("/feature-dev-aidd:implement", result.stderr)

    def test_stage_skill_tools_allowed_tools_ref_fails(self) -> None:
        bad_skill = build_stage_skill("qa").replace(
            "  - Read",
            "  - Read\n  - \"Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh *)\"",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"qa": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("stage skills must not use tools/* in allowed-tools", result.stderr)

    def test_loop_stage_skill_forbidden_manual_recovery_tool_fails(self) -> None:
        bad_skill = build_stage_skill("review").replace(
            "  - Read",
            (
                "  - Read\n"
                "  - \"Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/preflight_prepare.py *)\""
            ),
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"review": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manual recovery surface", result.stderr)

    def test_loop_stage_skill_non_canonical_stage_result_path_fails(self) -> None:
        bad_skill = build_stage_skill("qa").replace(
            "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_result.py",
            "python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/stage_result.py",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"qa": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("non-canonical stage-result path", result.stderr)

    def test_loop_stage_skill_non_canonical_loop_pack_runtime_path_fails(self) -> None:
        bad_skill = build_stage_skill("review").replace(
            "## Additional resources",
            (
                "## Runtime hints\n"
                "- Не использовать python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/loop_pack.py.\n\n"
                "## Additional resources"
            ),
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"review": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("loop pack runtime path must be canonical", result.stderr)

    def test_loop_stage_skill_missing_runtime_path_blocker_code_fails(self) -> None:
        bad_skill = build_stage_skill("qa").replace("runtime_path_missing_or_drift", "runtime_path_unknown", 1)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"qa": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("runtime_path_missing_or_drift", result.stderr)

    def test_loop_stage_skill_internal_preflight_script_mention_warns_only(self) -> None:
        bad_skill = build_stage_skill("review").replace(
            "internal preflight",
            "preflight_prepare.py",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"review": bad_skill})
            result = self.run_lint(root)
            self.assertEqual(result.returncode, 0, msg=f"stdout: {result.stdout}\nstderr: {result.stderr}")
            self.assertIn("telemetry-only", result.stderr)

    def test_loop_stage_skill_missing_semantic_marker_fails(self) -> None:
        bad_skill = build_stage_skill("review").replace(
            "[AIDD_LOOP_POLICY:MANUAL_STAGE_RESULT_FORBIDDEN]",
            "",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"review": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing semantic marker", result.stderr)

    def test_loop_stage_skill_self_slash_contract_fails(self) -> None:
        bad_skill = build_stage_skill("implement").replace(
            "## Additional resources",
            (
                "### `/feature-dev-aidd:implement <ticket>`\n"
                "- When to run: operator entrypoint.\n"
                "- Inputs: ticket and active scope/work-item context.\n"
                "- Outputs: stage-chain artifacts and stage result.\n"
                "- Failure mode: blocked/warn.\n"
                "- Next action: fix and rerun.\n\n"
                "## Additional resources"
            ),
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"implement": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not duplicate self slash-stage entrypoint", result.stderr)

    def test_stage_skill_body_relative_runtime_ref_fails(self) -> None:
        bad_skill = build_stage_skill("idea-new").replace(
            "### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py`",
            "### `python3 skills/idea-new/runtime/analyst_check.py`",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"idea-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical runtime paths", result.stderr)

    def test_aidd_init_stage_skill_body_relative_runtime_ref_fails(self) -> None:
        bad_skill = build_stage_skill("aidd-init").replace(
            "### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py`",
            "### `python3 skills/aidd-init/runtime/init.py`",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"aidd-init": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical runtime paths", result.stderr)

    def test_stage_skill_missing_python_entrypoint_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root)
            (root / STAGE_RUNTIME_ENTRYPOINT["plan-new"]).unlink()
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing canonical python entrypoint", result.stderr)

    def test_stage_skill_missing_python_allowed_tool_fails(self) -> None:
        bad_skill = build_stage_skill("idea-new").replace(
            '\n  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py *)"',
            "",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"idea-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must include canonical python entrypoint", result.stderr)

    def test_stage_skill_legacy_stage_alias_fails(self) -> None:
        bad_skill = build_stage_skill("review-spec").replace(
            "## Steps\n1. Run subagent `feature-dev-aidd:plan-reviewer`.\n2. Run subagent `feature-dev-aidd:prd-reviewer`.",
            "## Steps\n1. Run `/feature-dev-aidd:planner DEMO-1` before review.",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"review-spec": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("legacy stage alias `/feature-dev-aidd:planner`", result.stderr)

    def test_stage_skill_deprecated_runtime_alias_without_ban_fails(self) -> None:
        bad_skill = build_stage_skill("review-spec").replace(
            "## Steps\n1. Run subagent `feature-dev-aidd:plan-reviewer`.\n2. Run subagent `feature-dev-aidd:prd-reviewer`.",
            (
                "## Steps\n"
                "1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/stage_set.py --stage review-prd`."
            ),
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"review-spec": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("deprecated runtime alias `stage_set.py`", result.stderr)

    def test_stage_skill_context_pack_refresh_without_agent_fails(self) -> None:
        bad_skill = build_stage_skill("plan-new").replace(
            "## Steps\n1. Run subagent `feature-dev-aidd:planner`.\n2. Run subagent `feature-dev-aidd:validator`.",
            (
                "## Steps\n"
                "1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/context_pack.py --refresh --stage plan`."
            ),
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"plan-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("context pack guidance must not use `context_pack.py --refresh`", result.stderr)

    def test_loop_stage_skill_stage_local_preflight_allowed_tool_fails(self) -> None:
        bad_skill = build_stage_skill("qa").replace(
            "  - Read",
            (
                "  - Read\n"
                "  - \"Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/preflight_prepare.py *)\""
            ),
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"qa": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("manual recovery surface", result.stderr)

    def test_stage_skill_foreign_wrapper_ref_fails(self) -> None:
        bad_skill = build_stage_skill("tasks-new").replace(
            "  - Read",
            '  - Read\n  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/research.sh *)"',
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"tasks-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must not reference legacy shell wrappers", result.stderr)

    def test_researcher_stage_must_not_call_shared_rlm_api_directly(self) -> None:
        bad_skill = build_stage_skill("researcher").replace(
            "  - Read",
            (
                "  - Read\n"
                "  - \"Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_nodes_build.py *)\""
            ),
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"researcher": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("researcher stage must not call shared RLM API directly", result.stderr)

    def test_stage_skill_must_not_use_context_or_agent_frontmatter(self) -> None:
        bad_skill = build_stage_skill("researcher").replace(
            "user-invocable: true",
            "user-invocable: true\ncontext: fork\nagent: researcher",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"researcher": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("stage skills must not set `context`", result.stderr)
            self.assertIn("stage skills must not set `agent`", result.stderr)

    def test_researcher_stage_requires_single_run_subagent_step(self) -> None:
        bad_skill = build_stage_skill("researcher").replace(
            "## Steps\n1. Run subagent `feature-dev-aidd:researcher` after stage orchestration.",
            "## Steps\n1. Run subagent alpha.\n2. Run subagent beta.",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"researcher": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must contain exactly one `Run subagent` step", result.stderr)

    def test_plan_new_requires_two_run_subagent_steps(self) -> None:
        bad_skill = build_stage_skill("plan-new").replace(
            "2. Run subagent `feature-dev-aidd:validator`.",
            "2. Validate plan artifacts.",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"plan-new": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("stage must contain exactly 2 `Run subagent` step(s)", result.stderr)

    def test_review_spec_requires_two_run_subagent_steps(self) -> None:
        bad_skill = build_stage_skill("review-spec").replace(
            "2. Run subagent `feature-dev-aidd:prd-reviewer`.",
            "2. Summarize review findings.",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, skill_override={"review-spec": bad_skill})
            result = self.run_lint(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("stage must contain exactly 2 `Run subagent` step(s)", result.stderr)

    def test_legacy_bash_grammar_warns_in_warn_mode(self) -> None:
        legacy_tail = ":" + "*"
        bad_agent = build_agent("analyst").replace(
            "tools: Read, Edit, Write",
            f"tools: Read, Edit, Write, Bash(rg{legacy_tail})",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"analyst": bad_agent})
            result = self.run_lint(root, env_override={"AIDD_BASH_LEGACY_POLICY": "warn"})
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("legacy Bash wildcard syntax is deprecated", result.stderr)

    def test_legacy_bash_grammar_errors_in_error_mode(self) -> None:
        legacy_tail = ":" + "*"
        bad_agent = build_agent("analyst").replace(
            "tools: Read, Edit, Write",
            f"tools: Read, Edit, Write, Bash(rg{legacy_tail})",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_prompts(root, agent_override={"analyst": bad_agent})
            result = self.run_lint(root, env_override={"AIDD_BASH_LEGACY_POLICY": "error"})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("legacy Bash wildcard syntax is forbidden by policy", result.stderr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
