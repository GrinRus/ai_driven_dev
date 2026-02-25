---
name: review-spec
description: Reviews plan and PRD, then gates readiness for implementation. Use when plan and PRD artifacts are ready for spec approval.
argument-hint: $1 [note...]
lang: ru
prompt_version: 1.0.23
source_version: 1.0.23
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg *)"
  - "Bash(sed *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress_cli.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-spec/runtime/prd_review_cli.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py *)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active stage `review-plan`, then `review-prd`; keep active feature in sync via canonical active-state runtime commands only.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-spec/runtime/prd_review_cli.py --ticket <ticket>`.
3. Gate PRD readiness with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py`; block on failure.
4. Use the existing rolling context pack as review input; keep read order RLM pack -> optional AST pack -> memory/context.
5. `ast-index` evidence is preferred when present; optional mode keeps rg fallback non-blocking.
6. Run subagent `feature-dev-aidd:plan-reviewer`, then run subagent `feature-dev-aidd:prd-reviewer`.
7. Persist PRD review report with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-spec/runtime/prd_review_cli.py --ticket <ticket> --report aidd/reports/prd/<ticket>.json`.
8. Return the output contract with canonical next action: `/feature-dev-aidd:tasks-new <ticket>` when READY, or `/feature-dev-aidd:spec-interview <ticket>` when BLOCKED by missing/unresolved spec inputs.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-spec/runtime/prd_review_cli.py`
- When to run: as canonical review-spec stage entrypoint before PRD approval decisions.
- Inputs: `--ticket <ticket>` plus active PRD/plan artifacts.
- Outputs: normalized PRD review report payload and readiness status.
- Failure mode: non-zero exit when review inputs are incomplete or report validation fails.
- Next action: fix missing artifacts/review findings, then rerun the CLI.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.

## Additional resources
- PRD review runtime: [runtime/prd_review_cli.py](runtime/prd_review_cli.py) (when: review-spec gate behavior is unclear; why: confirm report contract and status mapping).
