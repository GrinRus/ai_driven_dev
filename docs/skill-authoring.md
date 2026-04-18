# Skill Authoring Policy

> INTERNAL/DEV-ONLY: canonical maintainer source of truth for skill/agent prompt authoring, routing, and lint policy.

Owner: feature-dev-aidd
Last reviewed: 2026-04-18
Status: active

This file replaces the previous split between authoring tips, language policy, and trigger taxonomy.

## Scope
- Applies to `skills/*/SKILL.md`.
- Applies to `agents/*.md`.
- Drives `tests/repo_tools/lint-prompts.py` and skill-eval maintenance.

## Hard Rules
- Prompt corpus is EN-only for `skills/*/SKILL.md` and `agents/*.md`.
- Keep top-level prompt files compact; deep detail belongs in `references/*`, templates, or runtime docstrings.
- Stage skills own orchestration. Agents stay role-scoped and must not duplicate slash-stage routing.
- Shared and stage skills must include `## Command contracts` and `## Additional resources`.
- Agent prompts must keep the canonical sections:
  - `## Context`
  - `## Input Artifacts`
  - `## Automation`
  - `## Steps`
  - `## Fail-fast and Questions`
  - `## Response Format`

## Frontmatter Contract
- Every skill must include `name`, `description`, `lang`, `model`, and `user-invocable`.
- Every agent must include `name`, `description`, `lang`, `model`, `permissionMode`, and `skills`.
- Stage skills must keep `prompt_version` and `source_version` in semver format, and both values must match.
- Stage skills must expose canonical Python runtime entrypoints under `skills/<stage>/runtime/*.py`.
- Stage skills must not use `context` or `agent` frontmatter.

## Description And Routing Contract
- Start with a clear ownership sentence: what the skill does.
- Include one explicit positive trigger clause: `Use when ...`
- Include one explicit anti-trigger clause: `Do not use when ...`
- `Use when` must appear before `Do not use when`.
- Anti-trigger text must name neighboring skills or explicit outside-AIDD scope.

## Routing Shorthand
- `aidd-core`: shared runtime ownership and boundary resolution; not policy or status.
- `aidd-docio`: markdown slicing, context expansion, actions apply/validate; not lifecycle mutation.
- `aidd-flow-state`: active stage/feature, progress, tasklist, stage-result lifecycle; not markdown/action mechanics.
- `aidd-init`: bootstrap the canonical `aidd/` workspace; not ideation or simple status lookup.
- `aidd-loop`: loop-mode discipline and stage-chain safety; not direct `implement` / `review` / `qa` execution.
- `aidd-observability`: diagnostics, tool inventory, tests log, DAG export; not status summary.
- `aidd-policy`: output, question, read, and loop-safety policy; not shared runtime ownership.
- `aidd-rlm`: shared RLM slice/build/verify/finalize/pack operations; not direct research-stage execution.
- `aidd-stage-research`: research-stage handoff and RLM pending/ready boundaries; not shared RLM runtime behavior.
- `idea-new`: ticket bootstrap and PRD question flow; not research refresh or plan drafting.
- `researcher`: research artifact refresh and RLM readiness; not idea bootstrap or planning.
- `plan-new`: implementation plan from ready PRD/research; not idea kickoff or readiness review.
- `review-spec`: PRD/plan readiness review; not plan authoring or task derivation.
- `tasks-new`: tasklist derivation/refinement; not plan authoring or loop execution.
- `implement`: implement-stage loop execution; not review or QA verification.
- `review`: review-stage findings validation and follow-up derivation; not direct implementation or QA.
- `qa`: QA-stage verification and report generation; not review findings synthesis or implementation.
- `status`: consolidated ticket/stage summary; not diagnostics or lifecycle mutation.

## Command Contract Policy
Each critical command card documents interface behavior only:

```md
### `<command>`
- When to run: ...
- Inputs: ...
- Outputs: ...
- Failure mode: ...
- Next action: ...
```

Required coverage:
- Every stage skill: its canonical Python runtime entrypoint.
- Loop stages: runtime entrypoint plus `actions_apply.py`.

## Progressive Disclosure Policy
- Keep `SKILL.md` compact and operational.
- Move examples, walkthroughs, and troubleshooting detail into supporting files.
- Every `Additional resources` bullet must say:
  - `when:` when to open the file
  - `why:` what decision it unlocks

## Agent Policy
- Agents describe role, evidence, boundaries, and handoff only.
- Agents must not include own slash-stage self-links.
- Cross-stage handoffs are allowed when they point forward and do not duplicate orchestration.

## Skill-Eval Policy
- Benchmark routing with `tests/repo_tools/skill_eval_run.py` and `tests/repo_tools/skill_eval_compare.py`.
- Keep the eval corpus compact and representative. Prefer a small gold set over template-expanded variants.
- Adjust descriptions before adding body-level prompt mass.

## Official Reference Docs
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview>
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices>
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/skill-format>
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/subagents>
