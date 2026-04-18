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

## Hard rules
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

## Frontmatter contract
- Every skill must include `name`, `description`, `lang`, `model`, and `user-invocable`.
- Every agent must include `name`, `description`, `lang`, `model`, `permissionMode`, and `skills`.
- Stage skills must keep `prompt_version` and `source_version` in semver format, and both values must match.
- Stage skills must expose canonical Python runtime entrypoints under `skills/<stage>/runtime/*.py`.
- Stage skills must not use `context` or `agent` frontmatter.

## Description and routing contract
- Start with a clear ownership sentence: what the skill does.
- Include one explicit positive trigger clause: `Use when ...`
- Include one explicit anti-trigger clause: `Do not use when ...`
- `Use when` must appear before `Do not use when`.
- Anti-trigger text must name neighboring skills or explicit outside-AIDD scope.

## Routing taxonomy

| Skill | Use when | Do not use when |
| --- | --- | --- |
| `aidd-core` | shared runtime ownership or command boundary resolution | request is about output/read/question policy (`aidd-policy`) or ticket status (`status`) |
| `aidd-docio` | markdown slicing, context expansion, actions apply/validate | primary need is lifecycle mutation (`aidd-flow-state`) |
| `aidd-flow-state` | active stage/feature, progress, tasklist, stage-result lifecycle | primary need is markdown/action mechanics (`aidd-docio`) |
| `aidd-init` | bootstrap the canonical `aidd/` workspace | request is feature ideation (`idea-new`) or simple status lookup (`status`) |
| `aidd-loop` | loop-mode discipline and stage-chain safety | request is direct execution of `implement`, `review`, or `qa` |
| `aidd-observability` | diagnostics, tool inventory, tests log, DAG export | request is status summary (`status`) |
| `aidd-policy` | output contract, question protocol, read policy, loop safety policy | request is runtime ownership (`aidd-core`) |
| `aidd-rlm` | shared RLM slice/build/verify/finalize/pack operations | request is direct research-stage execution (`researcher`) |
| `aidd-stage-research` | research-stage handoff and RLM pending/ready boundaries | request is shared RLM runtime behavior (`aidd-rlm`) |
| `idea-new` | start a ticket and prepare PRD question flow | request is research refresh (`researcher`) or plan drafting (`plan-new`) |
| `researcher` | refresh research artifacts and canonical RLM readiness | request is idea bootstrap (`idea-new`) or planning (`plan-new`) |
| `plan-new` | derive implementation plan from ready PRD/research | request is idea kickoff (`idea-new`) or readiness review (`review-spec`) |
| `review-spec` | review plan and PRD readiness before implementation | request is plan authoring (`plan-new`) or task derivation (`tasks-new`) |
| `tasks-new` | derive/refine tasklist from PRD and plan | request is plan authoring (`plan-new`) or loop execution (`implement`) |
| `implement` | implement-stage loop execution | request is findings validation (`review`) or QA verification (`qa`) |
| `review` | review-stage findings validation and follow-up derivation | request is direct implementation (`implement`) or QA verification (`qa`) |
| `qa` | QA-stage verification and report generation | request is review findings synthesis (`review`) or implementation (`implement`) |
| `status` | consolidated ticket/stage status summary | request is diagnostics (`aidd-observability`) or lifecycle mutation (`aidd-flow-state`) |

## Command contract policy
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

## Progressive disclosure policy
- Keep `SKILL.md` compact and operational.
- Move examples, walkthroughs, and troubleshooting detail into supporting files.
- Every `Additional resources` bullet must say:
  - `when:` when to open the file
  - `why:` what decision it unlocks

## Agent policy
- Agents describe role, evidence, boundaries, and handoff only.
- Agents must not include own slash-stage self-links.
- Cross-stage handoffs are allowed when they point forward and do not duplicate orchestration.

## Skill-eval policy
- Benchmark routing with:
  - `tests/repo_tools/skill_eval_run.py`
  - `tests/repo_tools/skill_eval_compare.py`
- Keep the eval corpus compact and representative. Prefer a small gold set over template-expanded variants.
- Adjust descriptions before adding body-level prompt mass.

## Official reference docs
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview>
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices>
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/skill-format>
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/subagents>
