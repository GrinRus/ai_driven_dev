---
name: aidd-rlm
description: Shared RLM evidence workflow for subagents (slice, build, verify, finalize, pack).
lang: en
allowed-tools:
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-nodes-build.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-verify.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-links-build.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-jsonl-compact.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-finalize.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/reports-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/reports-pack.sh:*)"
model: inherit
user-invocable: false
---

## Scope
- This skill is preload-only for subagents.
- Use it to keep RLM behavior consistent across agents without duplicating long instructions.

## Canonical command paths
- Slice (shared): `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh`
- Researcher stage wrappers:
  - `${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-nodes-build.sh`
  - `${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-verify.sh`
  - `${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-links-build.sh`
  - `${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-jsonl-compact.sh`
  - `${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-finalize.sh`
  - `${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/reports-pack.sh`

## Fallback compatibility
- Legacy `${CLAUDE_PLUGIN_ROOT}/tools/rlm-*.sh` and `${CLAUDE_PLUGIN_ROOT}/tools/reports-pack.sh` remain compatibility shims.
- If a shim is used, expect a `DEPRECATED` warning and prefer canonical skill paths in new prompts.

## Evidence policy
- Read pack-first: `aidd/reports/research/<ticket>-rlm.pack.json`.
- Use slice queries for targeted context extraction.
- Avoid full JSONL reads unless pack/slice is insufficient.
