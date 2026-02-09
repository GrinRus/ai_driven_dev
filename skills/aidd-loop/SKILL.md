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
4. REVISE: reuse the same scope, follow fix_plan.json, and do not widen boundaries.
5. Scope guard: out-of-scope -> WARN + handoff; forbidden -> BLOCKED. Never expand boundaries yourself.
6. Tests: follow loop pack or reviewer policy; do not invent new test requirements.
7. No large logs/diffs in chat; link to `aidd/reports/**`.

## Canonical shared wrappers
- `skills/aidd-loop/scripts/loop-pack.sh`
- `skills/aidd-loop/scripts/loop-step.sh`
- `skills/aidd-loop/scripts/loop-run.sh`
- `skills/aidd-loop/scripts/preflight-prepare.sh`
- `skills/aidd-loop/scripts/preflight-result-validate.sh`
- `skills/aidd-loop/scripts/output-contract.sh`

## Additional resources
- For wrapper paths and fallback details, see [reference.md](reference.md).
- Loop pack template source: [templates/loop-pack.template.md](templates/loop-pack.template.md) (seeded to `aidd/docs/loops/template.loop-pack.md` by init).
