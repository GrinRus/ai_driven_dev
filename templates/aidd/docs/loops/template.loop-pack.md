---
schema: aidd.loop_pack.v1
updated_at: <UTC>
ticket: <ABC-123>
work_item_id: <I1>
work_item_key: <iteration_id=I1>
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
- goal: <1–2 строки>

## Do not read
- PRD/Plan/Research — только если есть ссылка в pack
- Полный tasklist — только excerpt ниже

## Boundaries
- allowed_paths:
  - src/feature/**
- forbidden_paths: []

## Commands required
- <doc/ref or command>

## Tests required
- <test command>

## Work item excerpt (required)
> goal/DoD/boundaries/refs from the tasklist work item.
