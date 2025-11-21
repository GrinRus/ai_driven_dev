---
description: "Feature initiation: capture idea → clarifications → PRD"
argument-hint: "<TICKET> [slug-hint]"
lang: en
prompt_version: 1.1.1
source_version: 1.1.1
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(python3 tools/set_active_feature.py:*),Bash(claude-workflow research:*),Bash(claude-workflow analyst:*),Bash(claude-workflow analyst-check:*)
model: inherit
---

## Context
`/idea-new` registers the active feature, scaffolds a PRD, runs Researcher, and kicks off the analyst dialog. It enforces the agent-first flow: analysts and researchers mine the slug-hint (`docs/.active_feature`), `docs/research/*.md`, `reports/research/*.json`, and run allowed CLI commands before escalating to the user. The analyst can trigger an extra research pass if context is thin (refining paths/keywords).

## Input Artifacts
- Slug-hint / user notes (argument `[slug-hint]` and `rg <ticket> docs/**`).
- `docs/prd.template.md` — used for scaffolding.
- `docs/research/<ticket>.md`, `reports/research/<ticket>-(context|targets).json` — created/updated automatically; when missing, `docs/templates/research-summary.md` is used as baseline.
- User-provided `slug-hint` from `/idea-new <ticket> [slug-hint]` — treat it as the primary raw idea; record it in PRD (overview/context) and backlog notes if applicable.

## When to Run
- At the very beginning of a feature lifecycle.
- Rerun only if you intentionally reset the active ticket (use `--force` cautiously).

## Automation & Hooks
- `python3 tools/set_active_feature.py <ticket> [--slug-note ...]` writes `docs/.active_ticket`, `.active_feature`, and scaffolds `docs/prd/<ticket>.prd.md` (Status: draft).
- `claude-workflow research --ticket <ticket> --auto` gathers repo context and refreshes `reports/research/<ticket>-context.json` / `-targets.json`. Extra `--paths/--keywords/--note` flags are optional and used only when the repo scope has to be narrowed.
- `claude-workflow analyst --ticket <ticket> --auto` launches the analyst agent; it re-reads research + slug-hint, applies `rg`, and if context is still weak can start another `claude-workflow research --ticket <ticket> --auto --paths ... --keywords ...` before asking the user.
- `claude-workflow analyst-check --ticket <ticket>` ensures the dialog block is structured and `Status` is not `draft`.

## What is Edited
- `docs/.active_ticket`, `docs/.active_feature`.
- `docs/prd/<ticket>.prd.md` — filled per template, status updated from draft to READY/BLOCKED.
- `docs/research/<ticket>.md` — created/updated (baseline recorded when no context is found).
- Auto-generated `reports/research/<ticket>-(context|targets).json`.

## Step-by-step Plan
1. Run `python3 tools/set_active_feature.py "$1" [--slug-note "$2"]` — it updates `docs/.active_ticket`, `.active_feature` (capturing the slug-hint as the raw user request), and scaffolds the PRD (use `--force` only after confirming you may overwrite the current ticket).
2. Execute `claude-workflow research --ticket "$1" --auto` to collect repository context. Pass `--paths/--keywords/--note` only when the default scan misses important modules; otherwise rely on the repo-driven output.
3. If the CLI reports `0 matches`, expand `docs/templates/research-summary.md` into `docs/research/$1.md`, add the “Context empty, baseline required” note, and list all commands/paths that returned nothing.
4. Launch the **analyst** agent automatically: `claude-workflow analyst --ticket "$1" --auto`. The agent reads slug-hint (`docs/.active_feature`), `docs/research/<ticket>.md`, `reports/research/*.json`, applies `rg`, and when context is insufficient can trigger another `claude-workflow research --ticket "$1" --auto --paths ... --keywords ...` before asking the user (answers must follow `Answer N:` format).
5. Analyst fills `docs/prd/$1.prd.md`: references to research/backlog, goals, scenarios, metrics, risks, dialog block. Switch the status from draft to READY once repo data plus any needed answers cover all sections.
6. Run `claude-workflow analyst-check --ticket "$1"` and fix any reported mismatches before continuing.
7. Optionally apply preset `feature-prd` or attach notes via `--note @file.md` to pre-populate research/PRD context.

## Fail-fast & Questions
- Missing ticket or slug-hint — stop and request it.
- Do not overwrite a filled PRD unless the user confirms (`--force`).
- If `claude-workflow research --auto` still lacks context after scanning, describe the commands/paths you already used, kick off another research pass with refined scope if needed, and only then ask the user for extra `--paths/--keywords` or `--note`.

## Expected Output
- Active ticket/slug set, PRD scaffolded + filled, Researcher report created/updated, status READY/BLOCKED reflecting dialog state.
- User understands remaining questions if BLOCKED.

## CLI Examples
- `/idea-new ABC-123 checkout-demo`
- `/idea-new ABC-123 --paths src/app --keywords "checkout,pay" --slug-note checkout-demo`
