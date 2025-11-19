---
description: "Manage reviewer test markers"
argument-hint: "[ticket]"
lang: en
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools: Bash(claude-workflow reviewer-tests:*)
model: inherit
---

## Context
Utility command to set/reset the reviewer-test marker stored in `reports/reviewer/<ticket>.json`. Format-and-test respects this marker when deciding whether to run full suites.

## Input Artifacts
- Active ticket (`docs/.active_ticket`) or explicit `--ticket` argument.
- Existing `reports/reviewer/<ticket>.json` (created automatically on first use).

## When to Run
- Before review/QA when additional tests must run.
- After tests pass to block/unblock gating.
- When clearing the marker for closed tickets.

## Automation & Hooks
- `claude-workflow reviewer-tests --status required|optional|not-required` adjusts the JSON marker.
- `--clear` removes the file entirely.

## What is Edited
- `reports/reviewer/<ticket>.json`.

## Step-by-step Plan
1. Need tests? `claude-workflow reviewer-tests --status required [--ticket $1]`.
2. Tests passed? `claude-workflow reviewer-tests --status optional [--ticket $1]` (or `not-required`).
3. Done with the ticket? `claude-workflow reviewer-tests --clear [--ticket $1]`.

## Fail-fast & Questions
- Ticket unspecified and no active ticket — prompt the user to provide one.
- Warn that `required` forces format-and-test to fail on errors.

## Expected Output
- Marker updated/cleared, along with a short explanation if needed.

## CLI Examples
- `/reviewer ABC-123`
- `!bash -lc 'claude-workflow reviewer-tests --status required --ticket "ABC-123"'`
