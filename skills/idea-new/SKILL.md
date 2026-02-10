---
name: idea-new
description: "Kick off a feature: set ticket/slug, build PRD draft, ask questions."
argument-hint: $1 [slug=<slug-hint>] [note...]
lang: ru
prompt_version: 1.3.17
source_version: 1.3.17
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg *)"
  - "Bash(sed *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py *)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Inputs: resolve `<ticket>/<slug>` and verify PRD/context artifacts are readable for idea stage.
2. Preflight: set active stage `idea` and active feature/slug with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py` and `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py`.
3. Orchestration: build/update the rolling context pack `aidd/reports/context/<ticket>.pack.md` and run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py --ticket <ticket>`.
4. Run subagent `feature-dev-aidd:analyst`. First action: read the rolling context pack.
5. Postflight: if answers already exist, rerun `python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py --ticket <ticket>` and sync PRD readiness status.
6. Output: return open questions (if any) and explicit next step `/feature-dev-aidd:researcher <ticket>`.

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
