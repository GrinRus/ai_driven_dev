---
description: "Feature kickoff: set ticket/slug → analyst → PRD draft + questions"
argument-hint: "<TICKET> [slug-hint] [note...]"
lang: en
prompt_version: 1.3.0
source_version: 1.3.0
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(claude-workflow analyst-check:*)"
model: inherit
disable-model-invocation: false
---

## Context
`/idea-new` sets the active ticket/slug, marks stage `idea`, runs sub-agent **analyst**, and produces a PRD draft with questions. The command does not run `claude-workflow research`: the analyst records context and fills `## Research Hints` in the PRD, while research itself happens in `/researcher`. READY is set after user answers (research is validated separately before planning). Free-form notes after the ticket should be stored in the PRD.

## Input Artifacts
- `@aidd/docs/prd.template.md` — PRD template (Status: draft, `## Диалог analyst`).
- `@aidd/docs/research/<ticket>.md`, `aidd/reports/research/*` — if already present, use as context.
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`.

## When to Run
- At the start of a feature, before planning or code.
- Re-run to refresh PRD/questions when context changes.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py` syncs `.active_*` and scaffolds PRD.
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py idea` sets stage `idea`.
- The command must **invoke the sub-agent** **analyst** (Claude: Run agent → analyst).
- `claude-workflow analyst-check --ticket <ticket>` validates dialog/status after answers.

## What is Edited
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`.
- `aidd/docs/prd/<ticket>.prd.md`.
- `aidd/docs/research/<ticket>.md` and `aidd/reports/research/*` — only via `/researcher`.

## Step-by-step Plan
1. Set stage `idea`.
2. Update active ticket/slug via `set_active_feature`.
3. Run sub-agent **analyst**; it updates the PRD and fills `## Research Hints` (paths/keywords/notes).
4. Return questions and PRD status; next step is `/researcher <ticket>`.

## Fail-fast & Questions
- Missing ticket/slug → stop and request correct arguments.
- Questions must follow the format `Question N (Blocker|Clarification)` + Why/Options/Default; answers: `Answer N: ...`. Use `## Research Hints` for research guidance.

## Expected Output
- Active ticket/slug set in `aidd/docs/.active_*`.
- `aidd/docs/prd/<ticket>.prd.md` created/updated (PENDING/BLOCKED until answers).
- Research runs as a separate `/researcher` command.
- Response includes `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## CLI Examples
- `/idea-new ABC-123 checkout-demo`
