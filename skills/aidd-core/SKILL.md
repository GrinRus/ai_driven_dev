---
description: Core runtime policy for AIDD skills (pack-first, output contract, DocOps).
lang: en
model: inherit
user-invocable: false
---

## Pack-first / read budget
- Read packs and excerpts before full documents.
- Slice-first rule: for markdown sources use block refs (`path#AIDD:SECTION`, `path@handoff:<id>`) via the `md-slice` wrapper before full Read.
- Full-file Read is allowed only when the slice is insufficient; record the reason in `AIDD:READ_LOG`.
- Prefer RLM packs and slices for research evidence.
- Use the read budget: avoid large logs/diffs; link to `aidd/reports/**` instead.

## Output contract (required)
- Status: ...
- Work item key: ...
- Artifacts updated: ...
- Tests: ...
- Blockers/Handoff: ...
- Next actions: ...
- AIDD:READ_LOG: ... (packs/excerpts only)
- AIDD:ACTIONS_LOG: ... (loop stages) / n/a (planning)

Include `Checkbox updated: ...` when the stage or agent expects it.

## DocOps policy v1 (stage-scoped)
- Loop stages (implement/review/qa/status): do not directly Edit/Write `aidd/docs/tasklist/**` or `aidd/reports/context/**`. Use actions/intents and DocOps automation only; do not manually edit or regenerate context packs. `aidd/docs/.active.json` is command-owned; subagents must not edit it.
- Planning stages (idea/research/plan/tasks/spec): direct Edit/Write is allowed for creation or major edits. Structured sections (progress/iterations/next3) are DocOps-managed; leave untouched unless explicitly instructed.

## Progressive disclosure
- Use `skills/aidd-core/scripts/context_expand.sh` to expand `readmap/writemap` with explicit `reason_code` + `reason`.
- Write-boundary expansion requires explicit `--expand-write` and must leave an audit trace under `aidd/reports/actions/<ticket>/<scope_key>/context-expand.audit.jsonl`.

## Actions log
- Loop stages MUST output `AIDD:ACTIONS_LOG: <path>` and keep the file updated.
- Status is read-only: reference the most recent actions log without modifying it.
- Planning stages may use `AIDD:ACTIONS_LOG: n/a`.

## Wrapper safety
- `AIDD_SKIP_STAGE_WRAPPERS=1` is debug-only and unsafe for normal loop execution.
- Runtime policy:
  - `strict` mode or stages `review|qa` => BLOCK (`reason_code=wrappers_skipped_unsafe`).
  - `fast` mode on `implement` => WARN (`reason_code=wrappers_skipped_warn`) and continue only for diagnostics.
- If wrappers are skipped, treat missing preflight/readmap/writemap/actions/log artifacts as contract violation.

## Question format
Use this exact format when you must ask the user:

```
Question N (Blocker|Clarification): ...
Why: ...
Options: A) ... B) ...
Default: ...
```

## Subagent guard
Subagents must never edit `aidd/docs/.active.json`. If it happens or is required, stop and return BLOCKED with the offending path.
