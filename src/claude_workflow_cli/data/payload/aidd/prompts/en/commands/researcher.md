---
description: "Prepare Researcher report: collect context and run agent"
argument-hint: "<TICKET> [note...] [--paths path1,path2] [--keywords kw1,kw2] [--note text]"
lang: en
prompt_version: 1.1.4
source_version: 1.1.4
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_feature.py:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py:*)"
  - "Bash(claude-workflow research:*)"
model: inherit
disable-model-invocation: false
---

## Context
`/researcher` gathers codebase context: runs `claude-workflow research`, then updates `aidd/docs/research/<ticket>.md` via the `researcher` agent. Free-form notes after the ticket should be stored in the report.

## Input Artifacts
- `aidd/docs/.active_ticket`, `aidd/docs/.active_feature`.
- `@aidd/docs/prd/<ticket>.prd.md`.
- `@aidd/docs/templates/research-summary.md`.
- `aidd/reports/research/<ticket>-context.json`.

## When to Run
- After `/idea-new`, before `/plan-new`.
- Re-run when modules/risks change.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/tools/set_active_stage.py research` sets stage `research`.
- `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph [--paths ... --keywords ... --note ...]` updates JSON context.
- Optionally append handoff tasks via `claude-workflow tasks-derive --source research --append --ticket <ticket>`.

## What is Edited
- `aidd/docs/research/<ticket>.md`.
- PRD/tasklist links to the report.

## Step-by-step Plan
1. Ensure the active ticket is set; use `set_active_feature` if needed.
2. Set stage `research`.
3. Run `claude-workflow research ...` and update JSON context.
4. Invoke `researcher` and update `aidd/docs/research/<ticket>.md`.
5. Add handoff tasks if needed.

## Fail-fast & Questions
- Missing active ticket or PRD → stop and request `/idea-new`.
- If report stays `pending`, return questions and conditions for `reviewed`.

## Expected Output
- Updated `aidd/docs/research/<ticket>.md` (status `pending|reviewed`).
- Fresh `aidd/reports/research/<ticket>-context.json`.
- Response includes `Checkbox updated`, `Status`, `Artifacts updated`, `Next actions`.

## CLI Examples
- `/researcher ABC-123 --paths src/app:src/shared --keywords "payment,checkout" --deep-code`
