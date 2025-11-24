---
description: "Research report prep: collect context + run agent"
argument-hint: "<TICKET> [--paths path1,path2] [--keywords kw1,kw2] [--note text]"
lang: en
prompt_version: 1.1.0
source_version: 1.1.0
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(claude-workflow research:*),Bash(python3 tools/set_active_feature.py:*),Bash(claude-workflow preset:*)
model: inherit
---

## Context
`/researcher` ensures every feature has an up-to-date research report. It reuses the CLI scan, updates `docs/research/<ticket>.md`, and syncs links with PRD/tasklist.

## Input Artifacts
- Active ticket (`docs/.active_ticket` or CLI arg).
- PRD, plan, tasklist (if present).
- `docs/templates/research-summary.md` for new reports.

## When to Run
- After `/idea-new`, before `/plan-new`.
- Re-run when architecture changes or codebase diverges significantly.

## Automation & Hooks
- `claude-workflow research --ticket <ticket> --auto --deep-code [--reuse-only] [--paths/--keywords/--langs/--note]` populates `reports/research/<ticket>-context.json` with `code_index` and `reuse_candidates`.
- `--dry-run` writes only JSON; `--targets-only` refreshes target paths without scanning; `--reuse-only` focuses on reuse candidates; `--langs` filters languages; `--no-agent` skips launching the Claude agent.

## What is Edited
- `docs/research/<ticket>.md` (per template) and references in PRD/tasklist.

## Step-by-step Plan
1. Ensure active ticket matches `$1`; run `/idea-new` or `python3 tools/set_active_feature.py` if needed.
2. Execute `claude-workflow research --ticket "$1" --auto --deep-code [extra options like --langs/--reuse-only]`.
3. If no matches are found, scaffold `docs/research/$1.md` and mark the baseline.
4. Launch **researcher** with the generated JSON, build the call/import graph in Claude Code using `code_index`, fill reuse/patterns/anti-patterns, gaps, notes.
5. Set status to `reviewed` once the team approved recommendations; otherwise `pending` with TODOs.
6. Verify PRD (`## Analyst dialog`) and tasklist reference the report.

## Fail-fast & Questions
- No active ticket or PRD? Pause until `/idea-new` runs.
- Missing paths/keywords? Request them so the scan is meaningful.
- Report `pending` states and next steps when context is incomplete.

## Expected Output
- Updated research doc, context JSON, and references in PRD/tasklist.

## CLI Examples
- `/researcher ABC-123 --paths src/service:src/lib --keywords "checkout,pay" --deep-code --langs py,kt`
- `!bash -lc 'claude-workflow research --ticket "ABC-123" --auto --deep-code --note "Reuse checkout facade" --reuse-only'`
