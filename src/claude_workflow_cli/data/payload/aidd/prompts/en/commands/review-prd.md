---
description: "PRD review and readiness status"
argument-hint: "<TICKET>"
lang: en
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(python3 scripts/prd-review-agent.py:*)
model: inherit
disable-model-invocation: false
---

## Context
`/review-prd`runs after the analyst finishes the PRD. It calls`prd-reviewer`, updates`## PRD Review`, and records findings.

## Input Artifacts
-`docs/prd/&lt;ticket&gt;.prd.md`.
-`docs/plan/&lt;ticket&gt;.md`, ADRs, related tasks.
-`docs/research/&lt;ticket&gt;.md`.

## When to Run
- Before`/plan-new`or whenever the PRD receives significant edits.

## Automation & Hooks
-`scripts/prd-review-agent.py`writes the structured report to`reports/prd/&lt;ticket&gt;.json`(`--emit-text`prints summary).
-`gate-workflow`blocks code changes until`## PRD Review`has`Status: approved`(or explicitly allowed states).

## What is Edited
-`docs/prd/&lt;ticket&gt;.prd.md`(`## PRD Review`).
-`docs/tasklist/&lt;ticket&gt;.md`— blocking action items from the review.
-`reports/prd/&lt;ticket&gt;.json`.

## Step-by-step Plan
1. Collect context: PRD, plan, ADRs, known risks.
2. Call **prd-reviewer** via the command palette or CLI, pointing it at the ticket.
3. Update the`## PRD Review`section with status, summary, findings, action items.
4. Copy blocking action items to the tasklist with owners/deadlines.
5. Run`!bash -lc 'python3 scripts/prd-review-agent.py --ticket "$1" --report "reports/prd/$1.json" --emit-text'`to store the JSON log.

## Fail-fast & Questions
- Missing PRD/plan/ADR links? Pause and request them.
- Empty sections or unresolved risks? Keep status BLOCKED and list required fixes.

## Expected Output
- PRD updated with a full review block, JSON report stored, action items synced.

## CLI Examples
-`/review-prd ABC-123`
-`!bash -lc 'python3 scripts/prd-review-agent.py --ticket "ABC-123" --report "reports/prd/ABC-123.json" --emit-text'`
