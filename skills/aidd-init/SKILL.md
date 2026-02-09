---
name: aidd-init
description: Initialize AIDD workspace scaffolding in the current project.
argument-hint: "[--force] [--detect-build-tools]"
lang: ru
prompt_version: 0.1.6
source_version: 0.1.6
allowed-tools:
  - Read
  - Write
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py`.
2. Verify `aidd/` exists and core templates were copied (`aidd/AGENTS.md`, `aidd/docs/shared/stage-lexicon.md`).
3. If `--detect-build-tools` was used, confirm `.claude/settings.json` was updated.
4. Return the output contract and next actions.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py`
- When to run: always for canonical workspace bootstrap.
- Inputs: optional `--force` and `--detect-build-tools`.
- Outputs: initialized `aidd/` structure and synced workspace templates/settings.
- Failure mode: non-zero exit on invalid workspace, write failures, or template contract mismatch.
- Next action: fix workspace path/permissions, then rerun the same entrypoint.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.

## Additional resources
- Runtime implementation: [runtime/init.py](runtime/init.py) (when: init behavior or flags are unclear; why: verify exact bootstrap logic and exit conditions).
