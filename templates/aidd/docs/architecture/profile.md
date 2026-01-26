---
schema: aidd.arch_profile.v1
updated_at: YYYY-MM-DD
style: ""
conventions: aidd/config/conventions.json
stack_hint: []
modules: []
allowed_deps: []
interfaces:
  api: []
  db: []
  events: []
---

# AIDD Architecture Profile

## Style / Pattern
- <e.g., Hexagonal, Clean Architecture, Layered, Modular Monolith>
- Notes: <optional>

## Modules / Layers
> List the real modules/layers and their folder roots.

| Module/Layer (id) | Root path(s) | Responsibility | Public interfaces |
| --- | --- | --- | --- |
| <module-id> | <path/> | <what it owns> | <public API> |

## Allowed dependencies
> Express as rules; keep it explicit and enforceable.

### Rules
- Allowed:
  - <moduleA> -> <moduleB>
- Forbidden:
  - <moduleX> -> <moduleY>

### Rationale
- <why these boundaries exist>

## Invariants (Non-negotiables)
- <invariant>
- Security constraints: <...>
- DB/migration constraints: <...>

## Interface pointers (API / DB / Events)
- API schemas: <path or link>
- DB schema/migrations: <path or link>
- Events/contracts: <path or link>

## Repo conventions
- Conventions: `aidd/config/conventions.json`
- Lint/format policy: <link to project skill or doc>
