---
name: plan-new
description: Drafts implementation plan from ready PRD and research artifacts. Use when PRD and research gates pass and plan stage should start. Do not use when the request is feature kickoff in `idea-new` or readiness approval in `review-spec`.
argument-hint: $1 [note...]
lang: en
prompt_version: 1.1.18
source_version: 1.1.18
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg *)"
  - "Bash(sed *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan-new/runtime/research_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active stage `plan` and active feature.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan-new/runtime/research_check.py --ticket <ticket>`.
3. Gate readiness with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py` and `python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan-new/runtime/research_check.py`; block early if either fails.
4. Evidence order is deterministic: read PRD first, then the primary RLM pack (`aidd/reports/research/<ticket>-rlm.pack.json`), and only then the existing rolling context pack when the first two sources are insufficient. Do not invoke standalone context-pack builder scripts from this stage.
5. Planner first-pass handoff must stay narrow: pass PRD + RLM pack by default, add the rolling context pack only when a concrete gap remains, and keep `aidd/docs/research/<ticket>.md` strictly on-demand. The default planner handoff must not list both the full research markdown and the full context pack together.
6. Prompt-budget rule: when the first-pass context approaches the model budget, drop lower-priority artifacts instead of widening the evidence set. Drop research markdown first, then context pack, and keep pack/slice-first evidence.
7. Runtime-path safety: execute only canonical runtime commands from this contract (`python3 ${CLAUDE_PLUGIN_ROOT}/skills/.../runtime/...`).
8. Root-relative `/skills/...` runtime paths are forbidden; use only `${CLAUDE_PLUGIN_ROOT}/skills/.../runtime/...`.
9. Produce or refresh `aidd/docs/plan/<ticket>.md` directly in this stage command from the canonical evidence above; do not require `feature-dev-aidd:planner` or `feature-dev-aidd:validator` as runtime orchestration steps under this stage policy.
10. Keep validation in the same stage pass: use canonical gate results plus bounded self-review of the generated plan, and treat planner/validator roles as conceptual authoring guidance only, not as required runtime handoffs.
11. Final stage readiness is sourced from `prd_check + research_check + stage-authored plan validation`; return `/feature-dev-aidd:review-spec <ticket>` only on the ready path.
12. Otherwise return PENDING or BLOCKED with the concrete plan gaps and the canonical next action for the current stage.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan-new/runtime/research_check.py`
- When to run: before planning to enforce research-readiness gate.
- Inputs: `--ticket <ticket>` and current PRD/research artifacts.
- Outputs: deterministic readiness verdict for plan stage.
- Failure mode: non-zero exit if research status/artifacts do not satisfy gate policy.
- Next action: resolve research blockers and rerun the gate check.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py`
- When to run: before planner execution and before final stage verdict normalization.
- Inputs: active PRD artifacts for the current ticket.
- Outputs: deterministic PRD readiness verdict used by the stage command as source-of-truth input.
- Failure mode: non-zero exit when required PRD fields or readiness markers are missing.
- Next action: fix the PRD blockers, then rerun the gate before planning continues.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.

## Additional resources
- Plan template source: [templates/plan.template.md](templates/plan.template.md) (when: generating or normalizing plan structure; why: ensure planner/validator outputs follow canonical sections).
