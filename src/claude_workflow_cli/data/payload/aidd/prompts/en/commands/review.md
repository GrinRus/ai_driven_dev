---
description: "Code review and feedback"
argument-hint: "<TICKET> [note...]"
lang: en
prompt_version: 1.0.2
source_version: 1.0.2
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(git diff:*),Bash(python3 tools/set_active_stage.py:*),Bash(claude-workflow reviewer-tests:*),Bash(claude-workflow progress:*)
model: inherit
disable-model-invocation: false
---

## Context
`/review` launches the reviewer agent to analyze the diff, record findings, and update the tasklist before QA. Use any free-form notes after the ticket as additional review context.

## Input Artifacts
- `git diff`/ PR.
- `aidd/docs/prd/<ticket>.prd.md`,`aidd/docs/plan/<ticket>.md`,`aidd/docs/tasklist/<ticket>.md`.
- Test logs, reviewer test markers.

## When to Run
- After `/implement`, before `/qa`. Use it as many times as needed.

## Automation & Hooks
- `claude-workflow reviewer-tests --status required/optional/clear` toggles mandatory tests.
- `claude-workflow progress --source review --ticket <ticket>` confirms `[x]` updates.
- Preset `feature-release` can help with release notes if required.
- `python3 tools/set_active_stage.py review` records the `review` stage.

## What is Edited
- Source files for quick fixes (optional) and `aidd/docs/tasklist/<ticket>.md` entries.

## Step-by-step Plan
1. Record the `review` stage: `python3 tools/set_active_stage.py review`.
2. Call **reviewer** with the ticket ID; share priorities to inspect.
3. If necessary, set reviewer tests to `required` and restore to `optional` after green runs.
4. Update tasklist (what’s done, what remains, references to files/lines).
5. Execute `!bash -lc 'claude-workflow progress --source review --ticket "$1"'`.
6. Report status/follow-ups.

## Fail-fast & Questions
- Missing plan/tasklist? Pause and request updates.
- Unable to run tests? Keep status BLOCKED and explain requirements.
- Scope mismatch? Clarify before approving.

## Expected Output
- Tasklist updated, status (READY/WARN/BLOCKED) with findings.
- Notation on reviewer-tests marker if changed.

## CLI Examples
- `/review ABC-123`
- `!bash -lc 'claude-workflow reviewer-tests --status required --ticket "ABC-123"'`
