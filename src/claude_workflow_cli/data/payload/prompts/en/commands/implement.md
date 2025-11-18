---
description: "Feature implementation + selective tests"
argument-hint: "<TICKET>"
lang: en
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools: Bash("$CLAUDE_PROJECT_DIR/.claude/hooks/format-and-test.sh:*"),Bash(claude-workflow progress:*),Read,Edit,Write,Grep,Glob
model: inherit
---

## Context
`/implement` drives development by delegating to the implementer agent, running format/tests, and keeping the tasklist updated.

## Input Artifacts
- `docs/plan/<ticket>.md`, `docs/tasklist/<ticket>.md`.
- Research/PRD for context.
- Current git diff/config.

## When to Run
- After `/tasks-new`. Repeat throughout development until the feature is done.

## Automation & Hooks
- `.claude/hooks/format-and-test.sh` auto-runs post-write. Adjust via env vars: `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `TEST_CHANGED_ONLY`.
- Finish with `claude-workflow progress --source implement --ticket <ticket>`; the CLI warns if no new `[x]` items exist.

## What is Edited
- Source code, configs, docs according to the plan.
- `docs/tasklist/<ticket>.md` checkboxes after each iteration.

## Step-by-step Plan
1. Call **implementer** with the ticket ID.
2. Observe auto format/test results; rerun manually with `!"$CLAUDE_PROJECT_DIR"/.claude/hooks/format-and-test.sh` when necessary.
3. Update tasklist entries (switch `[ ]` to `[x]`, add timestamps/notes/links).
4. Document any env overrides and non-default test scopes.
5. Run `claude-workflow progress --source implement --ticket "$1"`.
6. Report closed checkboxes, remaining work, and test status.

## Fail-fast & Questions
- No plan/tasklist — request `/plan-new`/`/tasks-new` first.
- Unclear requirements/integrations/migrations — stop and ask.
- Tests failing? Do not proceed without resolution or explicit approval to skip.

## Expected Output
- Updated code + tasklist with `Checkbox updated: …` in the final response.
- Clear status of tests and next steps.

## CLI Examples
- `/implement ABC-123`
- `!bash -lc 'SKIP_AUTO_TESTS=1 "$CLAUDE_PROJECT_DIR"/.claude/hooks/format-and-test.sh'`
