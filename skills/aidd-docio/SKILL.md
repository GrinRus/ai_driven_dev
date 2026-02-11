---
name: aidd-docio
description: Shared DocIO runtime ownership for markdown slicing/patching, actions validation/apply, and context-map expansion.
lang: en
model: inherit
user-invocable: false
---

## Scope
- This skill owns shared DocIO runtime entrypoints.
- Stage skills consume these APIs for preflight/postflight and deterministic document updates.
- Flow-state orchestration remains in `feature-dev-aidd:aidd-core` and `feature-dev-aidd:aidd-loop`.

## Canonical shared Python entrypoints
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/md_slice.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/md_patch.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_validate.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/actions_apply.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/context_map_validate.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-docio/runtime/context_expand.py`

## Ownership guard
- DocIO-facing runtime modules must be implemented under `skills/aidd-docio/runtime/*`.
- Consumers should reference `skills/aidd-docio/runtime/*` as canonical paths.

## Additional resources
- [references/read-write-maps.md](references/read-write-maps.md) (when: readmap/writemap behavior is in question; why: align map validation and expansion semantics).
- [references/actions-flow.md](references/actions-flow.md) (when: actions schema/apply behavior is unclear; why: follow validator-to-apply lifecycle).
