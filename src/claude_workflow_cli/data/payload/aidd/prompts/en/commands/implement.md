---
description: "Feature implementation + selective tests"
argument-hint: "<TICKET> [note...]"
lang: en
prompt_version: 1.1.6
source_version: 1.1.6
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(python3 tools/set_active_stage.py:*),Bash(${CLAUDE_PLUGIN_ROOT:-./aidd}/.claude/hooks/format-and-test.sh:*),Bash(claude-workflow progress:*),Bash(./gradlew:*),Bash(gradle:*),Bash(git:*),Bash(git add:*)
model: inherit
disable-model-invocation: false
---

## Context
`/implement` drives development by delegating to the implementer agent, keeping tasklist aligned with the plan, consulting PRD/research only when plan/tasklist lack detail, and running format/tests before handing results back. Free-form notes after the ticket should be treated as iteration context and noted in the response.

## Input Artifacts
- `aidd/docs/plan/<ticket>.md`, `aidd/docs/tasklist/<ticket>.md`.
- Research/PRD for supplemental context when plan/tasklist miss details.
- Current git diff/config.

## When to Run
- After `/tasks-new`. Repeat throughout development until the feature is done.

## Automation & Hooks
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/.claude/hooks/format-and-test.sh` auto-runs post-write. Adjust via env vars: `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`, `TEST_CHANGED_ONLY`.
- Finish with `claude-workflow progress --source implement --ticket <ticket>`; the CLI warns if no new `[x]` items exist.
- `python3 tools/set_active_stage.py implement` records the `implement` stage (rerun when returning to implementation).

## What is Edited
- Source code, configs, docs according to the plan.
- `aidd/docs/tasklist/<ticket>.md` checkboxes after each iteration.

## Step-by-step Plan
1. Record the `implement` stage: `python3 tools/set_active_stage.py implement`.
2. Call **implementer** with the ticket ID.
3. Observe auto format/test results; rerun manually with `!${CLAUDE_PLUGIN_ROOT:-./aidd}/.claude/hooks/format-and-test.sh` when necessary.
4. Update tasklist entries (switch `[ ]` to `[x]`, add timestamps/notes/links).
5. Document any env overrides and non-default test scopes.
6. Run `claude-workflow progress --source implement --ticket "$1"`.
7. Report closed checkboxes, remaining work, and test status.

## Fail-fast & Questions
- No plan/tasklist — request `/plan-new`/`/tasks-new` first.
- Unclear requirements/integrations/migrations — stop and ask.
- Tests failing? Do not proceed without resolution or explicit approval to skip.

## Expected Output
- Updated code + tasklist with `Checkbox updated: …` in the final response.
- Clear status of tests and next steps.

## CLI Examples
- `/implement ABC-123`
- `!bash -lc 'SKIP_AUTO_TESTS=1 ${CLAUDE_PLUGIN_ROOT:-./aidd}/.claude/hooks/format-and-test.sh'`
