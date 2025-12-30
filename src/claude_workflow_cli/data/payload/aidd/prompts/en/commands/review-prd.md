---
description: "PRD review and readiness status"
argument-hint: "<TICKET> [note...]"
lang: en
prompt_version: 1.0.3
source_version: 1.0.3
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(python3 ${CLAUDE_PLUGIN_ROOT:-./aidd}/scripts/prd-review-agent.py:*)
model: inherit
disable-model-invocation: false
---

## Context
`/review-prd`runs after the analyst finishes the PRD. It calls`prd-reviewer`, updates`## PRD Review`, and records findings. Treat free-form notes after the ticket as review context.

## Input Artifacts
-`aidd/docs/prd/<ticket>.prd.md`.
-`aidd/docs/plan/<ticket>.md`, ADRs, related tasks.
-`aidd/docs/research/<ticket>.md`.

## When to Run
- Before`/plan-new`or whenever the PRD receives significant edits.

## Automation & Hooks
-`scripts/prd-review-agent.py`writes the structured report to`${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json`(`--emit-text`prints summary).
-`gate-workflow`blocks code changes until`## PRD Review`has`Status: READY`(or explicitly allowed states).

## What is Edited
-`aidd/docs/prd/<ticket>.prd.md`(`## PRD Review`).
-`aidd/docs/tasklist/<ticket>.md`— blocking action items from the review.
-`${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/<ticket>.json`.

## Step-by-step Plan
1. Collect context: PRD, plan, ADRs, known risks.
2. Call **prd-reviewer** via the command palette or CLI, pointing it at the ticket.
3. Update the`## PRD Review`section with status, summary, findings, action items.
4. Copy blocking action items to the tasklist with owners/deadlines.
5. Run`!bash -lc 'python3 "${CLAUDE_PLUGIN_ROOT:-./aidd}/scripts/prd-review-agent.py" --ticket "$1" --report "${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/$1.json" --emit-text'`to store the JSON log.

## Fail-fast & Questions
- Missing PRD/plan/ADR links? Pause and request them.
- Empty sections or unresolved risks? Keep status BLOCKED and list required fixes.

## Expected Output
- PRD updated with a full review block, JSON report stored, action items synced.

## CLI Examples
-`/review-prd ABC-123`
-`!bash -lc 'python3 "${CLAUDE_PLUGIN_ROOT:-./aidd}/scripts/prd-review-agent.py" --ticket "ABC-123" --report "${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/prd/ABC-123.json" --emit-text'`
