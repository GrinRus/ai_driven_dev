# Shared Agent Contract

Common skeleton for `agents/*.md`.

- Read the available artifacts before asking questions or returning blockers.
- Stay inside the role's write scope; the parent stage command owns orchestration, gate execution, and final verdict normalization.
- Missing canonical artifacts or unresolved contract prerequisites should return `BLOCKED`, not guessed recovery.
- Shared output anchor remains `Output follows aidd-core skill.` in each concrete agent prompt.
- Role prompts should keep only role-specific constraints and artifact deltas; do not re-copy generic routing or ownership prose.
