---
description: "Feature kickoff: set ticket/slug → analyst → PRD draft + questions"
argument-hint: "<TICKET> [slug-hint] [note...]"
lang: en
prompt_version: 1.2.6
source_version: 1.2.6
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(claude-workflow analyst-check:*)"
  - "Bash(claude-workflow research:*)"
model: inherit
disable-model-invocation: false
---

## Context
`/idea-new` sets the active ticket/slug, marks stage `idea`, runs the analyst, and produces a PRD draft with questions. READY is only allowed after user answers and fresh research. Free-form notes after the ticket should be stored in the PRD.

## Input Artifacts
- `@aidd/docs/prd.template.md` — PRD template (Status: draft, `## Диалог analyst`).
- `@aidd/docs/research/<ticket>.md`, `aidd/reports/research/*` — updated if needed.
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`.

## When to Run
- At the start of a feature, before planning or code.
- Re-run to refresh PRD/questions when context changes.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py` syncs `.active_*` and scaffolds PRD.
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py idea` sets stage `idea`.
- The analyst triggers `claude-workflow research --ticket <ticket> --auto` when context is missing.
- `claude-workflow analyst-check --ticket <ticket>` validates dialog/status after answers.

## What is Edited
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`.
- `aidd/docs/prd/<ticket>.prd.md`.
- `aidd/docs/research/<ticket>.md` and `aidd/reports/research/*` (if needed).

## Step-by-step Plan
1. Set stage `idea`.
2. Update active ticket/slug via `set_active_feature`.
3. Run analyst; if needed, research is triggered and PRD updated.
4. Return questions and PRD status.

## Fail-fast & Questions
- Missing ticket/slug → stop and request correct arguments.
- Questions must follow the format `Question N (Blocker|Clarification)` + Why/Options/Default; answers: `Answer N: ...`.

## Expected Output
- Active ticket/slug set in `aidd/docs/.active_*`.
- `aidd/docs/prd/<ticket>.prd.md` created/updated (PENDING/BLOCKED until answers).
- Research docs/reports updated if needed.
- Response includes `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## CLI Examples
- `/idea-new ABC-123 checkout-demo`
