---
description: "Final QA gate for the feature"
argument-hint: "<TICKET>"
lang: en
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools: Bash(claude-workflow qa:*),Bash(claude-workflow progress:*),Read,Grep,Glob,Write,Edit
model: inherit
disable-model-invocation: false
---

## Context
`/qa`runs the mandatory QA stage after`/review`: it invokes the **qa** sub-agent via`claude-workflow qa --gate`, produces`reports/qa/&lt;ticket&gt;.json`, updates the QA section in`docs/tasklist/&lt;ticket&gt;.md`, and records progress before release.

## Input Artifacts
- Active ticket (`docs/.active_ticket`), slug hint (`docs/.active_feature`).
-`docs/prd/&lt;ticket&gt;.prd.md`,`docs/plan/&lt;ticket&gt;.md`,`docs/tasklist/&lt;ticket&gt;.md`(QA section), logs from previous gates (`gate-tests`).
- Diff/logs (`git diff`,`reports/reviewer/&lt;ticket&gt;.json`, test outputs, demo/staging info).

## When to Run
- After`/review`, before release/merge.
- Re-run whenever new commits land or QA checks change.

## Automation & Hooks
- Required call:`!("claude-workflow" qa --ticket "&lt;ticket&gt;" --report "reports/qa/&lt;ticket&gt;.json" --gate --emit-json)`.
- QA auto-runs tests from`config/gates.json: qa.tests`(default`.claude/hooks/format-and-test.sh`); logs to`reports/qa/&lt;ticket&gt;-tests*.log`, summary in report (`tests_summary`,`tests_executed`). Overrides:`--skip-tests`/`--allow-no-tests`or env`CLAUDE_QA_SKIP_TESTS`/`CLAUDE_QA_ALLOW_NO_TESTS`.
- Gate`.claude/hooks/gate-qa.sh`uses`config/gates.json: qa.command`(default`claude-workflow qa --gate`), blocks merge on`blocker/critical`or missing`reports/qa/&lt;ticket&gt;.json`, checks tasklist progress (`progress --source qa|handoff`), and runs`tasks-derive --source qa --append`when`handoff=true`.
- Record progress:`!("claude-workflow" progress --source qa --ticket "&lt;ticket&gt;")`.

## What is Edited
-`docs/tasklist/&lt;ticket&gt;.md`— QA checkboxes, run dates, links to logs/report.
-`reports/qa/&lt;ticket&gt;.json`— fresh QA report.

## Step-by-step Plan
1. Run **qa** sub-agent via CLI (see command above); ensure`reports/qa/&lt;ticket&gt;.json`is written with READY/WARN/BLOCKED and test logs are captured.
2. Map diff to the QA checklist; capture findings with severity and recommendations.
3. Update`docs/tasklist/&lt;ticket&gt;.md`: switch relevant items`- [ ] → - [x]`, add date/iteration, link to report and test logs (`reports/qa/&lt;ticket&gt;-tests*.log`).
4. Execute`claude-workflow progress --source qa --ticket &lt;ticket&gt;`and confirm new`[x]`entries; add handoff`- [ ] ... (source: reports/qa/&lt;ticket&gt;.json)`or run`claude-workflow tasks-derive --source qa --append`.
5. Reply with status,`Checkbox updated: ...`, link to report/test logs, and next steps if WARN/BLOCKED.

## Fail-fast & Questions
- No active ticket/QA checklist? Ask to run`/tasks-new`or set`docs/.active_ticket`.
- Report missing? Rerun the CLI and include stderr; gate requires the report.
- Missing tests/env logs — request them or document uncovered scope explicitly.

## Expected Output
-`Checkbox updated: <QA items>`and`Status: READY|WARN|BLOCKED`.
- Link to`reports/qa/&lt;ticket&gt;.json`, summary of findings, next actions.

## CLI Examples
-`/qa ABC-123`
-`!bash -lc 'claude-workflow qa --ticket "ABC-123" --branch "$(git rev-parse --abbrev-ref HEAD)" --report "reports/qa/ABC-123.json" --gate'`
