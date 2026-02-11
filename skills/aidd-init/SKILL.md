---
description: Initialize AIDD workspace scaffolding in the current project.
argument-hint: "[--force] [--detect-build-tools]"
lang: ru
prompt_version: 0.1.5
source_version: 0.1.5
allowed-tools:
  - Read
  - Write
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/init.sh:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Run `${CLAUDE_PLUGIN_ROOT}/tools/init.sh` (add `--force` or `--detect-build-tools` if provided).
2. Verify `aidd/` exists and core templates were copied (`aidd/AGENTS.md`, `aidd/docs/prompting/conventions.md`).
3. If `--detect-build-tools` was used, confirm `.claude/settings.json` was updated.
4. Return the output contract and next actions.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.
