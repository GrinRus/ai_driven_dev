# Shared Loop Agent Contract

Common contract for `implementer`, `reviewer`, and `qa`.

## Shared Inputs
- `aidd/reports/loops/<ticket>/<scope_key>.loop.pack.md`
- `aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md` when present
- `aidd/reports/context/<ticket>.pack.md`
- `aidd/docs/tasklist/<ticket>.md`

## Shared Guardrails
- Stay inside the current bounded scope and work item.
- Do not run ad-hoc shell retry loops or invent manual recovery paths.
- Runtime or test failures become evidence-backed `BLOCKED` or handoff, not optimistic retries.
- Loop-mode subagents do not ask the user direct questions; they return blocker or handoff language only.
