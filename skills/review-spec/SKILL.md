---
name: review-spec
description: Review plan + PRD and gate readiness for implementation.
argument-hint: $1 [note...]
lang: ru
prompt_version: 1.0.20
source_version: 1.0.20
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
1. Set active stage `review-plan`, then `review-prd`; keep active feature in sync.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-spec/runtime/prd_review_cli.py --ticket <ticket>`.
3. Gate PRD readiness with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py`; block on failure.
4. Build the rolling context pack; run subagents in order: `plan-reviewer` then `prd-reviewer` (refresh between them).
5. Persist PRD review report with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review-spec/runtime/prd_review_cli.py --ticket <ticket> --report aidd/reports/prd/<ticket>.json`.
6. Return the output contract.

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
