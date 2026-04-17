---
name: plan-new
description: Drafts implementation plan from ready PRD and research artifacts. Use when PRD and research gates pass and plan stage should start. Do not use when the request is feature kickoff in `idea-new` or readiness approval in `review-spec`.
argument-hint: $1 [note...]
lang: en
prompt_version: 1.1.17
source_version: 1.1.17
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
4. Use the existing rolling context pack as input evidence; do not invoke standalone context-pack builder scripts from this stage.
5. Runtime-path safety: execute only canonical runtime commands from this contract (`python3 ${CLAUDE_PLUGIN_ROOT}/skills/.../runtime/...`).
6. Root-relative `/skills/...` runtime paths are forbidden; use only `${CLAUDE_PLUGIN_ROOT}/skills/.../runtime/...`.
7. Run subagent `feature-dev-aidd:planner`. The planner is the only writer for `aidd/docs/plan/<ticket>.md`.
8. Run subagent `feature-dev-aidd:validator`. The validator is read-only and returns the narrative verdict and gap list only.
9. Final stage readiness is sourced from `prd_check + research_check + validator verdict`; return `/feature-dev-aidd:review-spec <ticket>` only on the ready path.
10. Otherwise return PENDING or BLOCKED with the validator gaps and the canonical next action for the current stage.
11. Question trigger contract: use only the latest top-level stage return from this run as retry source-of-truth; nested excerpts and persisted template snippets are telemetry only.
12. Context hygiene: use rolling context-pack summary only; never copy raw template markdown bodies into context artifacts.
13. Forbidden bypass recovery: do not set, request, or rely on `AIDD_ALLOW_PLUGIN_WORKSPACE=1`; plugin-workspace bypass is non-canonical for this stage.
14. Forbidden self-diagnosis recovery: do not read runtime source files as primary recovery path; use top-level stage return + canonical report payload only.
15. No-question parity rule: if `AIDD:OPEN_QUESTIONS=none` and top-level stage return does not request Q/A, set `question_cycle_required=0` and do not start question retry.

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
