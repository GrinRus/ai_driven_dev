---
schema: aidd.loop_pack.v1
updated_at: <UTC>
ticket: <ABC-123>
work_item_id: <I1>
work_item_key: <iteration_id=I1>
scope_key: <iteration_id_I1>
boundaries:
  allowed_paths:
    - src/feature/**
  forbidden_paths: []
commands_required:
  - <doc/ref or command>
tests_required:
  - <test command>
arch_profile: aidd/docs/architecture/profile.md
evidence_policy: RLM-first
---

# Loop Pack — <ABC-123> / <iteration_id=I1>

## Work item
- work_item_id: <I1>
- work_item_key: <iteration_id=I1>
- scope_key: <iteration_id_I1>
- goal: <1–2 строки>

## Read policy
- Prefer excerpt; read full tasklist/PRD/Plan/Research/Spec только если excerpt не содержит **Goal/DoD/Boundaries/Expected paths/Size budget/Tests/Acceptance** или если REVISE требует контекста.

## Boundaries
- allowed_paths:
  - src/feature/**
- forbidden_paths: []

## Commands required
- <doc/ref or command>

## Tests required
- <test command>

## Work item excerpt (required)
> Должно включать: Goal/DoD/Boundaries/Expected paths/Size budget/Tests/Acceptance.
