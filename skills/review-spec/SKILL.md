---
name: review-spec
description: Reviews plan and PRD, then gates readiness for task derivation. Use when plan and PRD artifacts are ready for downstream planning readiness. Do not use when the request is plan authoring in `plan-new` or task derivation in `tasks-new`.
argument-hint: $1 [note...]
lang: en
prompt_version: 1.0.28
source_version: 1.0.28
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg *)"
  - "Bash(sed *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress_cli.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/prd_review.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/plan_review_gate.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_stage.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/set_active_feature.py *)"
model: inherit
disable-model-invocation: true
user-invocable: true
---

Follow `feature-dev-aidd:aidd-core`.

## Steps
1. Set active stage `review-plan`, then `review-prd`; keep active feature in sync via canonical active-state runtime commands only.
2. Run plan readiness gate before verdict: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/plan_review_gate.py --ticket <ticket>`.
3. Canonical plan path for all checks and narrative is only `aidd/docs/plan/<ticket>.md`; alias paths like `aidd/docs/plan/<ticket>.plan.md` are forbidden.
4. Run `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/prd_review.py --ticket <ticket>` to refresh structured PRD report payload.
5. Gate PRD readiness with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/prd_check.py`; block on failure.
6. Use the existing rolling context pack as review input; do not invoke standalone context-pack builder scripts from this stage.
7. Run subagent `feature-dev-aidd:plan-reviewer`. Treat its output as narrative review input only; if the plan gate already yields a terminal blocker, keep that blocker authoritative for the stage verdict.
8. Run subagent `feature-dev-aidd:prd-reviewer` after the plan-reviewer handoff whenever PRD artifacts remain readable; if the plan path is WARN-only, continue the PRD pass, but do not let narrative reviewers override gate/report payloads.
9. Persist PRD review report with `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/prd_review.py --ticket <ticket> --report aidd/reports/prd/<ticket>.json --require-ready` for READY-path validation.
10. Review-stage RLM policy: if RLM links are empty, the runtime performs bounded auto-heal (`rlm_links_build`, then finalize probe) and returns WARN attribution with evidence instead of terminal block when review can continue.
11. Report payload (`aidd/reports/prd/<ticket>.json|.pack.json`) is the source of truth for final verdict: READY is allowed only when `recommended_status=ready`; otherwise return WARN/BLOCKED with canonical next action on upstream PRD/plan fixes, then rerun `/feature-dev-aidd:review-spec <ticket>`.
12. If narrative text conflicts with gate/report payload, mark `WARN(review_spec_report_mismatch)` and follow gate/report payload only.
13. `Proceed to implementation` is forbidden when `recommended_status != ready`.
14. Runtime-path safety: execute only canonical runtime commands from this contract (`python3 ${CLAUDE_PLUGIN_ROOT}/skills/.../runtime/...`).
15. Root-relative `/skills/...` runtime paths are forbidden; use only `python3 ${CLAUDE_PLUGIN_ROOT}/skills/.../runtime/...`.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/prd_review.py`
- When to run: as canonical review-spec stage entrypoint before PRD approval decisions.
- Inputs: `--ticket <ticket>` plus active PRD/plan artifacts.
- Outputs: normalized PRD review report payload; verdict decisions use report payload (`recommended_status`) as source of truth.
- Failure mode: non-zero exit when review inputs are incomplete or report validation fails; RLM links-empty path is handled as bounded auto-heal then WARN attribution.
- Next action: fix missing artifacts/review findings or unresolved RLM prerequisites and rerun the CLI.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/plan_review_gate.py`
- When to run: before the plan-reviewer narrative pass and before deciding whether the stage can continue on a WARN path.
- Inputs: `--ticket <ticket>` and the canonical plan artifact.
- Outputs: structured plan gate verdict used as an authoritative source for early-stop semantics.
- Failure mode: non-zero exit when the plan artifact is missing, invalid, or blocked by the gate contract.
- Next action: fix the plan blockers and rerun the gate before claiming review-spec readiness.

## Notes
- Planning stage: `AIDD:ACTIONS_LOG: n/a`.

## Additional resources
- PRD review runtime: [../aidd-core/runtime/prd_review.py](../aidd-core/runtime/prd_review.py) (when: review-spec gate behavior is unclear; why: confirm report contract and status mapping).
