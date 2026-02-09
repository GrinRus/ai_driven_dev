---
name: researcher
description: Run research pipeline and produce researcher report artifacts.
argument-hint: $1 [note...] [--paths path1,path2] [--keywords kw1,kw2] [--note text]
lang: ru
prompt_version: 1.2.31
source_version: 1.2.31
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasks_derive.py:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
context: fork
agent: researcher
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active feature and stage `research`.
2. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket <ticket> --auto`.
3. Re-run the same entrypoint with optional overrides (`--paths`, `--keywords`, `--note`) when targeted refresh is needed.
4. Validate RLM outputs (`*-rlm-targets.json`, `*-rlm-manifest.json`, `*-rlm.worklist.pack.json`, optional `*-rlm.pack.json`).
5. Run subagent `feature-dev-aidd:researcher` (fork). First action: read RLM pack/worklist.
6. If RLM is pending or pack is missing, return BLOCKED with explicit handoff to shared RLM owner (`python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py --ticket <ticket>`). Do not execute shared RLM API from this stage command.
7. Optionally append handoff tasks via `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasks_derive.py --source research --append`.
8. Return the output contract.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py`
- When to run: always as canonical researcher pipeline entrypoint.
- Inputs: `--ticket <ticket>` with optional path/keyword/note overrides.
- Outputs: research artifacts, stage status, and RLM readiness/handoff markers (`rlm_status`, `rlm_pack_status`).
- Failure mode: non-zero exit when required inputs/artifacts are missing or RLM artifact generation fails.
- Next action: fix missing inputs/paths, rerun this entrypoint, and if RLM remains pending hand off to `aidd-rlm` owner runtime.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.

## Additional resources
- Research template source: [templates/research.template.md](templates/research.template.md) (when: drafting or reviewing `aidd/docs/research/<ticket>.md`; why: keep artifact shape aligned with canonical workspace template).
- Shared RLM owner skill: [../aidd-rlm/SKILL.md](../aidd-rlm/SKILL.md) (when: `rlm_status` is not `ready` or RLM pack is missing; why: run canonical shared RLM API outside stage-local orchestration).
