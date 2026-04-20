from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_status_skill_is_runtime_only_and_read_only_by_default() -> None:
    text = (REPO_ROOT / "skills" / "status" / "SKILL.md").read_text(encoding="utf-8")

    assert "disable-model-invocation: true" in text
    assert "read-only by default" in text
    assert "must never bootstrap the workspace" in text
    assert "single-shot read-only report command" in text
    assert "must never bootstrap the workspace, invoke `/feature-dev-aidd:aidd-init`, call `init.py`, call `index_sync.py`" in text
    assert "The `Next action` field is advisory" in text
    assert 'Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/index_sync.py *)' not in text
    assert "may refresh index data internally when needed" not in text


def test_planner_prompt_uses_prd_then_rlm_then_context_pack() -> None:
    skill_text = (REPO_ROOT / "skills" / "plan-new" / "SKILL.md").read_text(encoding="utf-8")
    planner_text = (REPO_ROOT / "agents" / "planner.md").read_text(encoding="utf-8")
    template_text = (REPO_ROOT / "skills" / "plan-new" / "templates" / "plan.template.md").read_text(
        encoding="utf-8"
    )

    assert "read PRD first, then the primary RLM pack" in skill_text
    assert "Planner first-pass handoff must stay narrow" in skill_text
    assert "must not list both the full research markdown and the full context pack together" in skill_text
    assert "Read the PRD first." in planner_text
    assert "Read the primary RLM pack next." in planner_text
    assert "Read the rolling context pack only when" in planner_text
    assert "Do not include `aidd/docs/research/<ticket>.md` in the first-pass evidence list" in planner_text
    assert "the research markdown and then the rolling context pack" in planner_text
    assert "Read the rolling context pack first." not in planner_text
    assert "Primary research evidence: `aidd/reports/research/<ticket>-rlm.pack.json`" in template_text
    assert "Research narrative: `aidd/docs/research/<ticket>.md` (reference only; consult on demand)" in template_text
    assert "Run subagent `feature-dev-aidd:planner`" not in skill_text
    assert "Run subagent `feature-dev-aidd:validator`" not in skill_text
    assert "do not require `feature-dev-aidd:planner` or `feature-dev-aidd:validator` as runtime orchestration steps" in skill_text
