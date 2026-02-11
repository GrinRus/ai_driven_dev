---
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

## Preload matrix v2
- Roles: `implementer`, `reviewer`, `qa`.
- This skill must not be preloaded for other subagents.

## Canonical shared Python entrypoints
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_pack.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/preflight_prepare.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/preflight_result_validate.py`
- `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/output_contract.py`

## Additional resources
- For wrapper paths and fallback details, see [reference.md](reference.md).
- Loop pack template source: [templates/loop-pack.template.md](templates/loop-pack.template.md) (seeded to `aidd/docs/loops/template.loop-pack.md` by init).
