---
name: spec-interview
description: Collects missing spec inputs and synchronizes answers into `spec.yaml`. Use when review-spec leaves unresolved specification fields. Do not use when the request is readiness gating in `review-spec` or task derivation in `tasks-new`.
argument-hint: $1 [note...]
lang: en
prompt_version: 1.0.17
source_version: 1.0.17
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - AskUserQuestionTool
  - "Bash(rg *)"
  - "Bash(sed *)"
  - "Bash(cat *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-interview/runtime/spec_interview.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py *)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active stage `spec-interview` and active feature.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-interview/runtime/spec_interview.py --ticket <ticket>` to create or sync the spec scaffold before question capture.
3. Use `AskUserQuestionTool` to gather missing spec details and append or refresh `aidd/reports/spec/<ticket>.interview.jsonl`.
4. Run subagent `feature-dev-aidd:spec-interview-writer` after the interview log has been refreshed.
5. Ready path: return `/feature-dev-aidd:tasks-new <ticket>` only when the synthesized spec is ready and required spec questions do not remain open.
6. Pending or blocked path: if required fields remain unresolved, return PENDING or BLOCKED with the remaining questions and keep the next action on `spec-interview`.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/spec-interview/runtime/spec_interview.py`
- When to run: as canonical spec interview entrypoint after review-spec and before tasklist derivation.
- Inputs: `--ticket <ticket>` with current PRD/plan context and optional notes.
- Outputs: created or synchronized `spec.yaml` scaffold and refreshed workspace index metadata for the current ticket.
- Scope boundary: this runtime does not resolve open questions or decisions; question collection and interview-log refresh remain stage-owned steps.
- Failure mode: non-zero exit when required source artifacts or the spec template are missing.
- Next action: fix scaffold/template issues, gather answers in the stage flow, then rerun the same command.

## Notes
- Use the aidd-core question format.
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.
- Canonical stage name: `spec-interview` (legacy alias `spec` normalizes to `spec-interview`).
- Interview capture is owned by the stage command; the writer agent consumes the refreshed interview log only after question collection.

## Additional resources
- Spec template source: [templates/spec.template.yaml](templates/spec.template.yaml) (when: creating or reconciling spec structure; why: keep generated `spec.yaml` aligned with canonical schema).
