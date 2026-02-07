---
name: implement
description: Implement the next work item with loop discipline.
argument-hint: $1 [note...] [test=fast|targeted|full|none] [tests=<filters>] [tasks=<task1,task2>]
lang: ru
prompt_version: 1.1.39
source_version: 1.1.39
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(cat:*)"
  - "Bash(xargs:*)"
  - "Bash(npm:*)"
  - "Bash(pnpm:*)"
  - "Bash(yarn:*)"
  - "Bash(pytest:*)"
  - "Bash(python:*)"
  - "Bash(go:*)"
  - "Bash(mvn:*)"
  - "Bash(make:*)"
  - "Bash(./gradlew:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/prd-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/diff-boundary-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/stage-result.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/status-summary.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/tasklist-normalize.sh:*)"
  - "Bash(git status:*)"
  - "Bash(git diff:*)"
  - "Bash(git log:*)"
  - "Bash(git show:*)"
  - "Bash(git rev-parse:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
context: fork
agent: implementer
---

Follow `feature-dev-aidd:aidd-core` and `feature-dev-aidd:aidd-loop`.

## Steps
1. Preflight reference: `skills/implement/scripts/preflight.sh`. Ensure active feature/stage, PRD gate, and loop pack are ready.
2. Use the existing rolling context pack; do not regenerate it in loop mode.
3. Run subagent `feature-dev-aidd:implementer` (fork). First action: loop pack -> review pack (if any) -> rolling context pack.
4. Fill actions.json: create `aidd/reports/actions/<ticket>/<scope_key>/implement.actions.json` from template and validate schema before postflight.
5. Postflight reference: `skills/implement/scripts/postflight.sh`. Run boundary check, progress check, stage-result, status-summary.

## Notes
- Implement stage does not run tests; format-only is allowed.
