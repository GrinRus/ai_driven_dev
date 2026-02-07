---
name: researcher
description: Run research pipeline and produce researcher report artifacts.
argument-hint: $1 [note...] [--paths path1,path2] [--keywords kw1,kw2] [--note text]
lang: ru
prompt_version: 1.2.30
source_version: 1.2.30
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/research.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-nodes-build.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-verify.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-links-build.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-jsonl-compact.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-finalize.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/reports-pack.sh:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
context: fork
agent: researcher
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active feature and stage `research`.
2. Run `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket $1 --auto` (apply optional paths/keywords/note).
3. Build/update the rolling context pack.
4. Run subagent `feature-dev-aidd:researcher` (fork). First action: read the rolling context pack.
5. If RLM is pending or packs are missing, run the `rlm-*` pipeline and `reports-pack.sh` until `rlm_status=ready`; otherwise return BLOCKED.
6. Optionally append handoff tasks via `tasks-derive.sh --source research --append`.
7. Return the output contract.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.
