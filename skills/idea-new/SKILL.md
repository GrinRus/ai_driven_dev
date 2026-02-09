---
name: idea-new
description: Kick off a feature: set ticket/slug, build PRD draft, ask questions.
argument-hint: $1 [slug=<slug-hint>] [note...]
lang: ru
prompt_version: 1.3.17
source_version: 1.3.17
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
context: fork
agent: analyst
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active stage `idea` and active feature/slug with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py` and `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py`.
2. Build the rolling context pack `aidd/reports/context/<ticket>.pack.md`.
3. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py --ticket <ticket>`.
4. Run subagent `feature-dev-aidd:analyst` in forked context. First action: read the rolling context pack.
5. If answers already exist, rerun `python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py --ticket <ticket>` and update PRD status.
6. Return questions (if any) and the next step `/feature-dev-aidd:researcher <ticket>`.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py`
- When to run: before/after analyst execution to validate PRD readiness and Q/A synchronization.
- Inputs: `--ticket <ticket>` and active workspace artifacts.
- Outputs: deterministic readiness status for idea-stage gate decisions.
- Failure mode: non-zero exit when required PRD fields or answer alignment are missing.
- Next action: update PRD/QA artifacts, then rerun the same validator.

## Notes
- Use the aidd-core question format.
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.

## Additional resources
- PRD template source: [templates/prd.template.md](templates/prd.template.md) (when: defining or validating required PRD structure; why: keep analyst output aligned with canonical sections).
