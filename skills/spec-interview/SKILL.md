---
name: spec-interview
description: Run spec interview and update spec.yaml from answers.
argument-hint: $1 [note...]
lang: ru
prompt_version: 1.0.11
source_version: 1.0.11
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - AskUserQuestionTool
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(cat:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active stage `spec` and active feature.
2. Use `AskUserQuestionTool` to gather missing spec details; update `aidd/docs/spec/<ticket>.spec.yaml`.
3. If answers arrive, sync them into the spec and `AIDD:OPEN_QUESTIONS`/`AIDD:DECISIONS` as needed.
4. Return the output contract and next step `/feature-dev-aidd:tasks-new <ticket>`.

## Notes
- Use the aidd-core question format.
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.
