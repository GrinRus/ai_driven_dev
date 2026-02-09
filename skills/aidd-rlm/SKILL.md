---
name: aidd-rlm
description: Shared RLM evidence workflow for subagents (slice, build, verify, finalize, pack).
lang: en
allowed-tools:
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_nodes_build.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_verify.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_links_build.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_jsonl_compact.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py:*)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/reports_pack.py:*)"
model: inherit
user-invocable: false
---

## Scope
- This skill is preload-only for subagents.
- Use it to keep RLM behavior consistent across agents without duplicating long instructions.
- Preload matrix v2 roles: `analyst`, `planner`, `plan-reviewer`, `prd-reviewer`, `researcher`, `reviewer`, `spec-interview-writer`, `tasklist-refiner`, `validator`.
- Do not preload for `implementer` or `qa`.

## Canonical command paths
- Slice (shared): `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py`
- RLM runtime entrypoints:
  - `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_nodes_build.py`
  - `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_verify.py`
  - `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_links_build.py`
  - `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_jsonl_compact.py`
  - `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py`
  - `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/reports_pack.py`

## Fallback paths
- Use canonical Python runtime entrypoints only for new prompts/integrations.

## Evidence policy
- Read pack-first: `aidd/reports/research/<ticket>-rlm.pack.json`.
- Use slice queries for targeted context extraction.
- Avoid full JSONL reads unless pack/slice is insufficient.
