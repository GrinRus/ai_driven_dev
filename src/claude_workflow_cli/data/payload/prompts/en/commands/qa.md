---
description: "Final QA gate for the feature"
argument-hint: "<TICKET>"
lang: en
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools: Bash(claude-workflow qa:*),Bash(claude-workflow progress:*),Read,Grep,Glob,Write,Edit
model: inherit
---

## Context
`/qa` runs the mandatory QA stage after `/review`: it invokes the **qa** sub-agent via `claude-workflow qa --gate`, produces `reports/qa/<ticket>.json`, updates the QA section in `docs/tasklist/<ticket>.md`, and records progress before release.

## Inputs
- Active ticket (`docs/.active_ticket`), slug hint (`docs/.active_feature`).
- `docs/prd/<ticket>.prd.md`, `docs/plan/<ticket>.md`, `docs/tasklist/<ticket>.md` (QA section), logs from previous gates (`gate-tests`, `gate-api-contract`, `gate-db-migration`).
- Diff/logs (`git diff`, `reports/reviewer/<ticket>.json`, test outputs, demo/staging info).

## Automation
- Required call: `!("claude-workflow" qa --ticket "<ticket>" --report "reports/qa/<ticket>.json" --gate --emit-json)`.
- Gate `.claude/hooks/gate-qa.sh` uses `config/gates.json: qa.command` (default `claude-workflow qa --gate`), blocks merge on `blocker/critical` or missing `reports/qa/<ticket>.json`.
- Record progress: `!("claude-workflow" progress --source qa --ticket "<ticket>")`.

## What to edit
- `docs/tasklist/<ticket>.md` — QA checkboxes, run dates, links to logs/report.
- `reports/qa/<ticket>.json` — fresh QA report.

## Step-by-step
1. Run **qa** sub-agent via CLI (see command above); ensure `reports/qa/<ticket>.json` is written with READY/WARN/BLOCKED.
2. Map diff to the QA checklist; capture findings with severity and recommendations.
3. Update `docs/tasklist/<ticket>.md`: switch relevant items `- [ ] → - [x]`, add date/iteration, link to report and command logs.
4. Execute `claude-workflow progress --source qa --ticket <ticket>` and confirm new `[x]` entries; with WARN list known issues.
5. Reply with status, `Checkbox updated: ...`, link to `reports/qa/<ticket>.json`, and next steps if WARN/BLOCKED.

## Fail-fast & Questions
- No active ticket/QA checklist? Ask to run `/tasks-new` or set `docs/.active_ticket`.
- Report missing? Rerun the CLI and include stderr; gate requires the report.
- Missing tests/env logs — request them or document uncovered scope explicitly.

## Expected output
- `Checkbox updated: <QA items>` and `Status: READY|WARN|BLOCKED`.
- Link to `reports/qa/<ticket>.json`, summary of findings, next actions.

## CLI examples
- `/qa ABC-123`
- `!bash -lc 'claude-workflow qa --ticket "ABC-123" --branch "$(git rev-parse --abbrev-ref HEAD)" --report "reports/qa/ABC-123.json" --gate'`
