---
name: idea-new
description: Bootstraps a new feature ticket by setting active context, deriving `slug_hint`, and preparing PRD questions. Use when the idea stage starts for a new ticket. Do not use when the request is to refresh research artifacts (`researcher`) or draft implementation plans (`plan-new`).
argument-hint: $1 [note...]
lang: en
prompt_version: 1.3.25
source_version: 1.3.25
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg *)"
  - "Bash(sed *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py *)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Inputs: resolve `<ticket>`, parse `idea_note` from user text, and verify PRD/context artifacts are readable for idea stage.
2. Slug synthesis: generate a short LLM summary from `idea_note`, normalize it into kebab-case token (`[a-z0-9-]`, 2-6 words), and use it as internal `slug_hint`; if `idea_note` is empty, fallback to `<ticket>` token. Do not ask user for `slug_hint`.
3. Preflight: set active stage `idea` and active feature with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py` and `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py <ticket> --slug-note "<generated-slug>"`.
4. Orchestration: build/update the rolling context pack `aidd/reports/context/<ticket>.pack.md` and run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py --ticket <ticket>`.
5. Run subagent `feature-dev-aidd:analyst`. First action: read the rolling context pack. For the persisted PRD artifact, override the global interactive question wording and copy the analyst-dialog labels from `templates/prd.template.md` verbatim.
6. Answer ownership: the stage command is the only owner allowed to materialize `## AIDD:ANSWERS`. The analyst subagent must never fill `AIDD:ANSWERS` from `Default:` suggestions, inferred choices, or its own assumptions.
7. Retry semantics: only when the current invocation explicitly contains compact retry payload `AIDD:ANSWERS Q1=...; Q2=...` may the persisted PRD include concrete answers. In that case rerun `python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py --ticket <ticket> --answers-origin explicit-retry`.
8. Postflight: reject comment-only placeholders as invalid analyst output. Read-time compatibility still accepts transitional `Question / Why / Options / Default`, but the canonical persisted PRD write format remains the template-native Russian wording.
9. Sync-from-review semantics: when the input contains `AIDD:SYNC_FROM_REVIEW ...`, apply every directive across duplicated PRD sections in one pass (`AIDD:NON_GOALS`, `AIDD:ACCEPTANCE`, `AIDD:METRICS`, `Summary`, `Requirements`, `Scenarios`). Remove or rewrite stale conflicting statements instead of only appending a partial note.
10. PRD review authority: `idea-new` must not mark `## PRD Review` as `READY`. After any sync/update, keep that section at `Status: PENDING` unless the current artifact explicitly describes unresolved blockers as `BLOCKED`; only `/feature-dev-aidd:review-spec <ticket>` may move PRD review to READY.
11. Validation semantics: if answers are present without the explicit retry provenance of the current or a previously validated run, `analyst_check.py` must fail with a deterministic question-bypass validation error instead of returning READY.
12. Ready path: return `/feature-dev-aidd:researcher <ticket>` only when `analyst_check.py` confirms idea-stage readiness.
13. Pending path: if required questions remain or PRD fields are incomplete, return PENDING with the full current remaining-question set in the top-level response and keep the next action on `idea-new`.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py`
- When to run: once ticket and idea note are parsed, before analyst execution.
- Inputs: `<ticket>` and generated `--slug-note <slug_hint>` derived from `idea_note`.
- Outputs: updated `aidd/docs/.active.json` (`ticket` + internal `slug_hint`) and PRD scaffold.
- Failure mode: non-zero exit when workspace paths/permissions are invalid.
- Next action: fix workspace issue, keep the same generated slug policy, rerun the command.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py`
- When to run: before/after analyst execution to validate PRD readiness and Q/A synchronization.
- Inputs: `--ticket <ticket>` and active workspace artifacts. Add `--answers-origin explicit-retry` only when the current run received an explicit compact retry payload from the caller.
- Outputs: deterministic readiness status for idea-stage gate decisions.
- Failure mode: non-zero exit when required PRD fields or answer alignment are missing.
- Next action: update PRD/QA artifacts, then rerun the same validator.

## Notes
- Interactive chat questions still follow the shared aidd-policy format.
- Persisted PRD artifact language is stage-local here: the analyst dialog must use the exact labels from `templates/prd.template.md`, and placeholder comments do not count as a valid question block.
- Non-interactive callers must rely on the latest top-level stage-return as the source of truth for retry payloads; do not rely only on `AskUserQuestion` panel state or stale example payloads.
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.

## Additional resources
- PRD template source: [templates/prd.template.md](templates/prd.template.md) (when: defining or validating required PRD structure; why: keep analyst output aligned with canonical sections).
