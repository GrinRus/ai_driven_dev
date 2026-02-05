---
name: aidd-loop
description: Loop-mode discipline for implement/review/qa (packs, scope, no questions).
lang: en
model: inherit
user-invocable: false
---

Follow `feature-dev-aidd:aidd-core` for output contract and DocOps.

## Loop discipline
1. Read order: loop pack -> review pack (if any) -> fix_plan.json when verdict=REVISE -> rolling context pack.
2. Excerpt-first: do not read full PRD/plan/tasklist/spec when the loop pack excerpt covers Goal/DoD/Boundaries/Expected paths/Size budget/Tests/Acceptance.
3. No questions in loop-mode; record blockers/handoff instead.
4. Scope guard: out-of-scope -> WARN + handoff; forbidden -> BLOCKED. Never expand boundaries yourself.
5. No large logs/diffs in chat; link to `aidd/reports/**`.
