# Skill Trigger Taxonomy

> INTERNAL/DEV-ONLY: maintainer routing taxonomy used for prompt lint and skill eval.

Owner: feature-dev-aidd
Last reviewed: 2026-04-12
Status: active

This registry defines routing boundaries for all AIDD skills.
Each skill must keep frontmatter `description` aligned with this table using explicit positive (`Use when`) and negative (`Do not use when`) triggers.

## Rules
- Keep a clear ownership phrase (`What it does`) at the beginning of each description.
- Include one `Use when` clause with concrete request signals.
- Include one `Do not use when` clause with neighbor-skill boundaries or explicit outside-AIDD scope.
- Prefer neighbor references by skill name to reduce overlap and false positives.

## Boundaries
- `aidd-core`
  - Use when: shared runtime ownership or canonical command boundary resolution is requested.
  - Do not use when: policy formatting/question rules (`aidd-policy`) or ticket summary (`status`) is requested.
- `aidd-docio`
  - Use when: markdown slicing, actions validation/apply, or context map expansion behavior is requested.
  - Do not use when: stage lifecycle state transitions (`aidd-flow-state`) are the primary need.
- `aidd-flow-state`
  - Use when: active stage/feature, progress/tasklist checks, or stage-result lifecycle actions are requested.
  - Do not use when: markdown/action patch mechanics (`aidd-docio`) or plain status readout (`status`) is requested.
- `aidd-init`
  - Use when: workspace bootstrap or idempotent initialization of canonical `aidd/` structure is requested.
  - Do not use when: active ticket ideation (`idea-new`) or post-bootstrap status lookup (`status`) is requested.
- `aidd-loop`
  - Use when: loop mode discipline and stage-chain safety for implement/review/qa is requested.
  - Do not use when: direct execution of `implement`, `review`, or `qa` stage commands is requested.
- `aidd-observability`
  - Use when: diagnostics, tool inventory, tests log, identifiers, or DAG export is requested.
  - Do not use when: ticket-level status summary (`status`) or runtime ownership navigation (`aidd-core`) is requested.
- `aidd-policy`
  - Use when: output contract, question protocol, read policy, or loop safety policy is requested.
  - Do not use when: runtime ownership mapping (`aidd-core`) or loop orchestration execution (`aidd-loop`) is requested.
- `aidd-rlm`
  - Use when: shared RLM slice/build/verify/finalize/pack operations are requested.
  - Do not use when: stage-local research command execution (`researcher`) is requested.
- `aidd-stage-research`
  - Use when: stage-specific research handoff and RLM pending/ready boundary is requested.
  - Do not use when: shared RLM runtime operations (`aidd-rlm`) or direct research stage execution (`researcher`) is requested.
- `idea-new`
  - Use when: starting a new ticket, deriving `slug_hint`, and preparing PRD question flow is requested.
  - Do not use when: research artifact refresh (`researcher`) or planning from ready PRD (`plan-new`) is requested.
- `researcher`
  - Use when: refreshing research artifacts and canonical RLM readiness for a ticket is requested.
  - Do not use when: ticket bootstrap (`idea-new`) or plan drafting (`plan-new`) is requested.
- `plan-new`
  - Use when: deriving implementation plan from ready PRD and research artifacts is requested.
  - Do not use when: idea kickoff (`idea-new`) or final readiness review (`review-spec`) is requested.
- `review-spec`
  - Use when: reviewing plan and PRD readiness gate before implementation is requested.
  - Do not use when: plan authoring (`plan-new`) or task derivation (`tasks-new`) is requested.
- `tasks-new`
  - Use when: deriving/refining tasklist from PRD and plan artifacts is requested.
  - Do not use when: plan authoring (`plan-new`) or loop-stage execution (`implement`) is requested.
- `implement`
  - Use when: implement-stage loop execution and actions/postflight update is requested.
  - Do not use when: review findings validation (`review`) or QA verification (`qa`) is requested.
- `review`
  - Use when: review-stage findings validation and follow-up task derivation is requested.
  - Do not use when: direct code implementation (`implement`) or QA verification (`qa`) is requested.
- `qa`
  - Use when: QA-stage validation, report generation, and postflight action handling is requested.
  - Do not use when: review-stage findings synthesis (`review`) or implementation execution (`implement`) is requested.
- `status`
  - Use when: consolidated stage/ticket status summary and artifact pointer retrieval is requested.
  - Do not use when: diagnostics/inventory (`aidd-observability`) or flow-state mutation (`aidd-flow-state`) is requested.

## Maintenance
- Any skill description change must keep this taxonomy synchronized in the same PR.
- `tests/repo_tools/lint-prompts.py` enforces `Use when` and `Do not use when` clauses in all skill descriptions.
