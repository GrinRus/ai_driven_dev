---
description: "Feature initiation: capture idea → clarifications → PRD"
argument-hint: "<TICKET> [slug-hint]"
lang: en
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(python3 tools/set_active_feature.py:*),Bash(claude-workflow research:*),Bash(claude-workflow analyst-check:*)
model: inherit
---

## Context
`/idea-new` registers the active feature, scaffolds a PRD, runs Researcher, and kicks off the analyst dialog. Run it before any planning/implementation steps.

## Input Artifacts
- Backlog idea / user notes.
- `docs/prd.template.md` — used for scaffolding.
- `docs/research/<ticket>.md` — created or updated during this command.

## When to Run
- At the very beginning of a feature lifecycle.
- Rerun only if you intentionally reset the active ticket (use `--force` cautiously).

## Automation & Hooks
- `python3 tools/set_active_feature.py <ticket> [--slug-note ...]` writes `docs/.active_ticket`, `.active_feature`, and scaffolds `docs/prd/<ticket>.prd.md` (Status: draft).
- `claude-workflow research --ticket <ticket> --auto` gathers context and creates `reports/research/<ticket>-context.json`.
- `claude-workflow analyst-check --ticket <ticket>` validates the dialog/result.

## What is Edited
- `docs/.active_ticket`, `docs/.active_feature`.
- `docs/prd/<ticket>.prd.md` — filled per template, status updated from draft to READY/BLOCKED.
- `docs/research/<ticket>.md` — created if needed and referenced in the PRD.

## Step-by-step Plan
1. Run `python3 tools/set_active_feature.py "$1" [--slug-note "$2"]` (supports `--skip-prd-scaffold` but default is to scaffold).
2. Execute `claude-workflow research --ticket "$1" --auto` (extend with `--paths`, `--keywords`, `--note` when helpful).
3. If the CLI reports `0 matches`, create `docs/research/$1.md` from the template and mark the baseline (“Context empty, baseline required”).
4. Fill `docs/prd/$1.prd.md`: dialog section, goals, scenarios, metrics, risks, dependencies. Keep `Status: draft` until the dialog is done.
5. Call the **analyst** agent and instruct the user to answer with `Answer N:`.
6. When all questions are resolved, run `claude-workflow analyst-check --ticket "$1"` and apply fixes as needed.
7. Optionally expand preset `feature-prd` for example goals.

## Fail-fast & Questions
- Missing ticket argument — stop and request it.
- Do not overwrite a filled PRD unless the user confirms (use `--force`).
- If context is insufficient, ask for directories/keywords via `--paths`/`--keywords` or additional notes.

## Expected Output
- Active ticket/slug set, PRD scaffolded + filled, Researcher report created/updated, status READY/BLOCKED reflecting dialog state.
- User understands remaining questions if BLOCKED.

## CLI Examples
- `/idea-new ABC-123 checkout-demo`
- `/idea-new ABC-123 --paths src/app --keywords "checkout,pay" --slug-note checkout-demo`
