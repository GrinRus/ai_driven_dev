---
description: "Feature initiation: analyst + (opt.) auto-research → user questions → PRD draft"
argument-hint: "<TICKET> [slug-hint] [note...]"
lang: en
prompt_version: 1.2.2
source_version: 1.2.2
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(python3 tools/set_active_feature.py:*),Bash(claude-workflow analyst:*),Bash(claude-workflow analyst-check:*),Bash(claude-workflow research:*),Bash(rg:*)
model: inherit
disable-model-invocation: false
---

## Context
`/idea-new` is a single run: records the active ticket, runs the analyst, optionally triggers research when context is thin, drafts the PRD and surfaces user questions. READY is set only after answers and up-to-date research; the command finishes in PENDING/BLOCKED with questions for the user.

## Input Artifacts
- Slug-hint / user notes (`[slug-hint]`, `rg <ticket> aidd/docs/**`, `[note...]`).
- `aidd/docs/prd.template.md` — scaffolds PRD (Status: draft, `## Диалог analyst`).
- `aidd/docs/research/<ticket>.md`, `reports/research/<ticket>-(context|targets).json` — auto-created/updated; baseline from `aidd/docs/templates/research-summary.md` if missing.
- Active markers: `aidd/docs/.active_ticket`, `.active_feature` (use `--target aidd` if running from repo root without `docs/`).

## When to Run
- At the start of a feature.
- Rerun only to re-init the ticket with `--force`: re-read existing PRD, don’t overwrite answers, add new questions/sources, and refresh status/Researcher when context changed.

## Automation & Hooks
- `python3 tools/set_active_feature.py <ticket> [--slug-note ...] [--target <root>]` writes `aidd/docs/.active_*` (fallback to `aidd/docs`), scaffolds PRD and research stub if missing.
- Inside `/idea-new` the **analyst** runs automatically; when context is thin, it triggers `claude-workflow research --ticket <ticket> --auto [--paths ... --keywords ...]` (or asks the user if `--no-research`).
- Flags: `--auto-research` (default on), `--no-research` to skip auto research.
- `claude-workflow analyst-check --ticket <ticket>` validates dialog/status after answers.

## What is Edited
- `aidd/docs/.active_ticket`, `.active_feature`.
- `aidd/docs/prd/<ticket>.prd.md` — draft/BLOCKED with questions; READY only after answers.
- `aidd/docs/research/<ticket>.md`, `reports/research/*` — updated/baseline as needed.
- Auto-generated `reports/research/<ticket>-(context|targets).json`.

## Step-by-step Plan
1. Run `python3 tools/set_active_feature.py "$1" [--slug-note "$2"] [--target <root>]` — updates `.active_*`, scaffolds PRD and research stub.
2. Auto-run **analyst**: reads slug-hint/artifacts; if context is thin, triggers `claude-workflow research --ticket "$1" --auto [--paths ... --keywords ...]` (or asks the user if `--no-research`).
3. After research (if any), analyst updates PRD, logs sources, and builds “Questions for the user” in `## Диалог analyst`. Do not set READY until answers and research reviewed (baseline allowed for empty repos).
4. Finish with explicit questions/blockers. User replies as `Ответ N: ...`; after answers run `claude-workflow analyst-check --ticket "$1"` and rerun analyst if needed to reach READY.

## Fail-fast & Questions
- Missing ticket/slug — stop and request it; avoid overwriting PRD without `--force`.
- No research or stale — analyst triggers research; with `--no-research` ask the user to run `/researcher`.
- Thin context even after research — list what you tried (paths/keywords/rg), form questions; do not set READY until answers.

## Expected Output
- Active ticket/slug set; PRD draft/BLOCKED with questions, READY only after answers.
- Research artifacts up to date (or baseline recorded).
- User sees explicit questions to move to READY/plan.

## Troubleshooting
- PRD stays draft/BLOCKED: answer all `Question N:` entries in `## Диалог analyst` and run `claude-workflow analyst-check --ticket <ticket> --target aidd`.
- Research pending/missing: run `claude-workflow research --ticket <ticket> --auto --target aidd` (or `/researcher`) and ensure `Status: reviewed`.
- Artifacts not found: run with `--target aidd` from repo root without `docs/`; verify `aidd/docs/.active_*` exists.

## CLI Examples
- `/idea-new ABC-123 checkout-demo`
- `/idea-new ABC-123 --paths src/app --keywords "checkout,pay" --slug-note checkout-demo`
