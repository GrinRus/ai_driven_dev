---
name: idea-new
description: Kick off a feature: set ticket/slug, build PRD draft, ask questions.
argument-hint: $1 [slug=<slug-hint>] [note...]
lang: ru
prompt_version: 1.3.16
source_version: 1.3.16
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg:*)"
  - "Bash(sed:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/scripts/rlm-slice.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set-active-stage.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/skills/idea-new/scripts/analyst-check.sh:*)"
model: inherit
disable-model-invocation: true
user-invocable: true
context: fork
agent: analyst
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active stage `idea` and active feature/slug with `set-active-stage.sh` and `set-active-feature.sh`.
2. Build the rolling context pack `aidd/reports/context/<ticket>.pack.md`.
3. Run subagent `feature-dev-aidd:analyst` in forked context. First action: read the rolling context pack.
4. If answers already exist, run `analyst-check.sh` and update PRD status.
5. Return questions (if any) and the next step `/feature-dev-aidd:researcher <ticket>`.

## Notes
- Use the aidd-core question format.
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.
