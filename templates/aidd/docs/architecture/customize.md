# Customize architecture & stack

Use the Architecture Profile as the single source of truth for boundaries and invariants.

## Stack hints and skills
- Run `/feature-dev-aidd:aidd-init --detect-stack` to prefill `stack_hint` and `enabled_skills`.
- Update `enabled_skills` when you add or remove tooling (tests/format/run).

## When to update
- New modules or changed directory roots.
- Updated dependency boundaries or invariants.
- Changes in test/format/run commands (skills).
