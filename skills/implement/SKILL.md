---
name: implement
description: Implement the next work item with loop discipline.
argument-hint: $1 [note...] [test=fast|targeted|full|none] [tests=<filters>] [tasks=<task1,task2>]
lang: ru
prompt_version: 1.1.40
source_version: 1.1.40
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/preflight.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/run.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/implement/scripts/postflight.sh:*)"
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
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/prd-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/diff-boundary-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/progress.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/stage-result.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/status-summary.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/tasklist-check.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/tasklist-normalize.sh:*)"
  - "Bash(git status:*)"
  - "Bash(git diff:*)"
  - "Bash(git log:*)"
  - "Bash(git show:*)"
  - "Bash(git rev-parse:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/set-active-feature.sh:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
context: fork
agent: implementer
---

Follow `feature-dev-aidd:aidd-core` and `feature-dev-aidd:aidd-loop`.

## Steps
1. Preflight reference: `skills/implement/scripts/preflight.sh`. This step is mandatory and must produce `readmap/writemap`, actions template, and `stage.preflight.result.json`.
2. Read order after preflight: `readmap.md` -> loop pack -> review pack (if exists) -> rolling context pack; do not perform broad repo scan before these artifacts.
3. Use the existing rolling context pack; do not regenerate it in loop mode.
4. Run subagent `feature-dev-aidd:implementer` (fork).
5. Fill actions.json (v1): create `aidd/reports/actions/<ticket>/<scope_key>/implement.actions.json` from template and validate schema via `skills/implement/scripts/run.sh` before postflight.
6. Postflight reference: `skills/implement/scripts/postflight.sh`. Apply actions via DocOps, then run boundary check, progress check, stage-result, status-summary.

## Notes
- Implement stage does not run tests; format-only is allowed.
