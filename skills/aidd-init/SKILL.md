---
name: aidd-init
description: Initializes AIDD workspace scaffolding for the current project. Use when bootstrapping canonical `aidd/` templates and project-owned test execution contract in `aidd/config/gates.json`. Do not use when the request is to start feature ideation (`idea-new`) or to inspect existing ticket progress (`status`).
argument-hint: "[--force]"
lang: en
prompt_version: 0.1.12
source_version: 0.1.12
allowed-tools:
  - Read
  - Write
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py *)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py`.
2. Runtime-path safety: never call relative runtime paths; use only `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py`; if `${CLAUDE_PLUGIN_ROOT}` is not set, return BLOCKED with env hint.
3. Default behavior is idempotent: existing workspace files stay untouched unless `--force` is explicitly passed.
4. `--force` is limited to refreshing managed bootstrap/config artifacts and the `qa.tests` contract; it is not permission to overwrite user-authored workspace docs or reports.
5. Verify `aidd/` exists and core templates were copied (`aidd/AGENTS.md`, `aidd/docs/shared/stage-lexicon.md`).
6. Verify `aidd/config/gates.json` contains `qa.tests` contract fields (`contract_version`, `profile_default`, `commands`, defaults).
7. Return the output contract and next actions, explicitly stating whether the run was non-destructive or a forced refresh.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py`
- When to run: always for canonical workspace bootstrap.
- Inputs: optional `--force`.
- Outputs: initialized `aidd/` structure and synced managed bootstrap/config templates with bootstrapped `qa.tests` contract.
- Failure mode: non-zero exit on invalid workspace, write failures, or template contract mismatch.
- Next action: fix workspace path/permissions or choose the correct `--force` mode, then rerun the same entrypoint.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.
- Without `--force`, do not overwrite user-authored workspace docs or reports.
- With `--force`, refresh only managed bootstrap/config artifacts; user-authored workspace docs or reports still stay out of scope.

## Additional resources
- Runtime implementation: [runtime/init.py](runtime/init.py) (when: init behavior or flags are unclear; why: verify exact bootstrap logic and exit conditions).
