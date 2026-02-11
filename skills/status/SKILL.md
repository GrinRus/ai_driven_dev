---
description: Summarize ticket status and key artifacts.
argument-hint: [$1]
lang: ru
prompt_version: 1.0.5
source_version: 1.0.5
allowed-tools:
  - Read
  - "Bash(rg:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/status.sh:*)"
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/index-sync.sh:*)"
model: inherit
disable-model-invocation: false
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core` and `feature-dev-aidd:aidd-loop`.

## Steps
1. Run `${CLAUDE_PLUGIN_ROOT}/tools/status.sh` for the ticket (use the active ticket if omitted).
2. If index data is missing or stale, run `${CLAUDE_PLUGIN_ROOT}/tools/index-sync.sh --ticket <ticket>`.
3. Return the output contract and the status summary.

## Notes
- Loop stage: set `AIDD:ACTIONS_LOG` to the most recent `*.actions.json` under `aidd/reports/actions/<ticket>/...` (use `rg` if needed).
