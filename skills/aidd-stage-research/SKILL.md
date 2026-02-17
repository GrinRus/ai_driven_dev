---
name: aidd-stage-research
description: Stage-specific research contract for subagent evidence reading and handoff behavior.
lang: en
model: inherit
user-invocable: false
---

## Scope
- Preload-only reference for `feature-dev-aidd:researcher` subagent.
- Defines stage behavior for research content work in the RLM-only pipeline.
- Keeps stage rules separate from the user-invocable `researcher` command skill.

## Stage Contract
- `skills/researcher/SKILL.md` owns orchestration only (state sync, pipeline run, explicit subagent call, handoff).
- `agents/researcher.md` owns content updates (`aidd/docs/research/<ticket>.md`) based on existing evidence.
- Subagent must not run shared RLM owner internals directly (`rlm_nodes_build.py`, `rlm_links_build.py`, `rlm_finalize.py`).
- Stage runtime may run bounded canonical finalize recovery once in `--auto` mode; manual recovery paths remain outside subagent scope.

## Evidence Policy
- Read pack-first: `aidd/reports/research/<ticket>-rlm.pack.json`.
- If pack is missing, read `*-rlm.worklist.pack.json` and return BLOCKED with explicit handoff.
- Use slice for targeted evidence only:
  - `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py --ticket <ticket> --query "<token>"`.
- Avoid full JSONL scans unless pack/worklist is insufficient.

## Handoff Policy
- When `rlm_status` is not ready, return BLOCKED with deterministic next action:
  - `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py --ticket <ticket>`.
- Pending output must include deterministic `reason_code` + `next_action` and append research handoff tasks.
- When evidence is ready, update research document and return READY with next stage command hint.
