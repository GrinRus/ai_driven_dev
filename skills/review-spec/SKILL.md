---
name: review-spec
description: Reviews plan and PRD, then gates readiness for task derivation. Use when plan and PRD artifacts are ready for downstream planning readiness. Do not use when the request is plan authoring in `plan-new` or task derivation in `tasks-new`.
argument-hint: $1 [note...]
lang: en
prompt_version: 1.0.29
source_version: 1.0.29
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - "Bash(rg *)"
  - "Bash(sed *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_links_build.py *)"
  - "Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py *)"
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
10. Review-stage RLM policy: if RLM links are empty, use only canonical shared RLM runtime commands for bounded auto-heal: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_links_build.py --ticket <ticket>` followed by `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py --ticket <ticket> --emit-json` when a finalize probe is still needed.
11. Report payload (`aidd/reports/prd/<ticket>.json|.pack.json`) is the source of truth for final verdict: READY is allowed only when `recommended_status=ready`; otherwise return WARN/BLOCKED with canonical next action on upstream PRD/plan fixes, then rerun `/feature-dev-aidd:review-spec <ticket>`.
12. If narrative text conflicts with gate/report payload, mark `WARN(review_spec_report_mismatch)` and follow gate/report payload only.
13. `Proceed to implementation` is forbidden when `recommended_status != ready`.
14. The PRD narrative must stay aligned with the structured report: when `recommended_status != ready`, keep `## PRD Review` at `Status: PENDING|BLOCKED` and do not claim implementation readiness in findings/action items.
15. Runtime-path safety: execute only canonical runtime commands from this contract (`python3 ${CLAUDE_PLUGIN_ROOT}/skills/.../runtime/...`). Relative plugin-local paths such as `python3 skills/...`, `/skills/...`, or guessed non-canonical helper locations are forbidden.

## Command contracts
### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/prd_review.py`
- When to run: as canonical review-spec stage entrypoint before PRD approval decisions.
- Inputs: `--ticket <ticket>` plus active PRD/plan artifacts.
- Outputs: normalized PRD review report payload; verdict decisions use report payload (`recommended_status`) as source of truth.
- Failure mode: non-zero exit when review inputs are incomplete or report validation fails; RLM links-empty path is handled as bounded auto-heal then WARN attribution.
- Next action: fix missing artifacts/review findings or unresolved RLM prerequisites and rerun the CLI.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_links_build.py`
- When to run: only when review evidence shows empty RLM links and the stage needs the bounded shared-RLM recovery path.
- Inputs: `--ticket <ticket>`.
- Outputs: refreshed `aidd/reports/research/<ticket>-rlm.links.jsonl` plus links stats sidecars.
- Failure mode: non-zero exit when RLM graph inputs are missing or the shared recovery cannot proceed.
- Next action: attribute WARN evidence to the shared RLM owner, then continue with report-payload truth if review can proceed.

### `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py`
- When to run: after canonical links rebuild when the review stage still needs a finalize probe for RLM readiness.
- Inputs: `--ticket <ticket> --emit-json`.
- Outputs: JSON finalize probe payload with `status`, `reason_code`, `next_action`, and bounded recovery attribution.
- Failure mode: non-zero exit when finalize prerequisites are still missing or the shared RLM owner cannot recover automatically.
- Next action: surface the finalize diagnostics as WARN/block evidence without inventing non-canonical helper paths.

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
