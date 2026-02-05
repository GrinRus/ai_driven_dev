---
name: aidd-core
description: Core runtime policy for AIDD skills (pack-first, output contract, DocOps).
lang: en
model: inherit
user-invocable: false
---

## Pack-first / read budget
- Read packs and excerpts before full documents.
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

Include `Checkbox updated: ...` when the stage or agent expects it.

## DocOps policy v1 (stage-scoped)
- Loop stages (implement/review/qa/status): do not Edit/Write `aidd/docs/tasklist/**` or `aidd/reports/context/**`. Write actions/intents only. `aidd/docs/.active.json` is command-owned; subagents must not edit it.
- Planning stages (idea/research/plan/tasks/spec): direct Edit/Write is allowed for creation or major edits. Structured sections (progress/iterations/next3) are DocOps-managed; leave untouched unless explicitly instructed.

## Actions log
- Loop stages MUST output `AIDD:ACTIONS_LOG: <path>` and keep the file updated.
- Planning stages may use `AIDD:ACTIONS_LOG: n/a`.

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
