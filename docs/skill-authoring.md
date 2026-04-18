# Skill Authoring Policy

> INTERNAL/DEV-ONLY: canonical maintainer contract for `skills/*/SKILL.md` and `agents/*.md`.

Owner: feature-dev-aidd
Last reviewed: 2026-04-18
Status: active

## Scope
- Applies to `skills/*/SKILL.md`.
- Applies to `agents/*.md`.
- Drives `tests/repo_tools/lint-prompts.py` and skill-eval maintenance.

## Non-negotiables
- Prompt corpus is EN-only for `skills/*/SKILL.md` and `agents/*.md`.
- Keep top-level prompts compact; move walkthroughs and long examples into templates, references, or runtime docs.
- Stage skills own orchestration; agents stay role-scoped and must not duplicate self-stage routing.
- Shared and stage skills must include `## Command contracts` and `## Additional resources`.
- Agent prompts must keep these sections:
  - `## Context`
  - `## Input Artifacts`
  - `## Automation`
  - `## Steps`
  - `## Fail-fast and Questions`
  - `## Response Format`

## Frontmatter Contract
- Every skill must include `name`, `description`, `lang`, `model`, and `user-invocable`.
- Every agent must include `name`, `description`, `lang`, `model`, `permissionMode`, and `skills`.
- Stage skills must keep matching `prompt_version` and `source_version` in `X.Y.Z`.
- Stage skills must expose canonical Python runtime entrypoints under `skills/<stage>/runtime/*.py`.
- Stage skills must not use `context` or `agent` frontmatter.

## Routing Contract
- Start with one ownership sentence.
- Include one positive trigger: `Use when ...`
- Include one anti-trigger: `Do not use when ...`
- Put `Use when` before `Do not use when`.
- Anti-trigger text must name neighboring skills or explicit outside-AIDD scope.

| Skill | Use when | Do not use when |
| --- | --- | --- |
| `aidd-core` | shared runtime ownership or command boundary resolution | request is about output/read/question policy (`aidd-policy`) or ticket status (`status`) |
| `aidd-docio` | markdown slicing, context expansion, actions apply/validate | primary need is lifecycle mutation (`aidd-flow-state`) |
| `aidd-flow-state` | active stage/feature, progress, tasklist, or stage-result lifecycle | primary need is markdown/action mechanics (`aidd-docio`) |
| `aidd-init` | bootstrap the canonical `aidd/` workspace | request is feature ideation (`idea-new`) or simple status lookup (`status`) |
| `aidd-loop` | loop-mode discipline and stage-chain safety | request is direct execution of `implement`, `review`, or `qa` |
| `aidd-observability` | diagnostics, tool inventory, tests log, or DAG export | request is status summary (`status`) |
| `aidd-policy` | output contract, question protocol, read policy, or loop safety policy | request is runtime ownership (`aidd-core`) |
| `aidd-rlm` | shared RLM slice/build/verify/finalize/pack operations | request is direct research-stage execution (`researcher`) |
| `aidd-stage-research` | research-stage handoff and RLM pending/ready boundaries | request is shared RLM runtime behavior (`aidd-rlm`) |
| `idea-new` | start a ticket and prepare PRD question flow | request is research refresh (`researcher`) or plan drafting (`plan-new`) |
| `researcher` | refresh research artifacts and canonical RLM readiness | request is idea bootstrap (`idea-new`) or planning (`plan-new`) |
| `plan-new` | derive implementation plan from ready PRD/research | request is idea kickoff (`idea-new`) or readiness review (`review-spec`) |
| `review-spec` | review plan and PRD readiness before implementation | request is plan authoring (`plan-new`) or task derivation (`tasks-new`) |
| `tasks-new` | derive or refine tasklist from PRD and plan | request is plan authoring (`plan-new`) or loop execution (`implement`) |
| `implement` | implement-stage loop execution | request is findings validation (`review`) or QA verification (`qa`) |
| `review` | review-stage findings validation and follow-up derivation | request is direct implementation (`implement`) or QA verification (`qa`) |
| `qa` | QA-stage verification and report generation | request is review findings synthesis (`review`) or implementation (`implement`) |
| `status` | consolidated ticket/stage status summary | request is diagnostics (`aidd-observability`) or lifecycle mutation (`aidd-flow-state`) |

## Command Cards
Use compact interface cards only:

```md
### `<command>`
- When to run: ...
- Inputs: ...
- Outputs: ...
- Failure mode: ...
- Next action: ...
```

- Every stage skill must cover its canonical Python runtime entrypoint.
- Loop stages must also cover `actions_apply.py`.

## Agent Rules
- Agents describe role, evidence, boundaries, and handoff only.
- Agents must not include own slash-stage self-links.
- Cross-stage handoffs are allowed only when they point forward and do not duplicate orchestration.
- Keep the anchor line `Output follows aidd-core skill`.

## Skill-Eval Rule
- Benchmark routing with `tests/repo_tools/skill_eval_run.py` and `tests/repo_tools/skill_eval_compare.py`.
- Keep the eval corpus small and representative; fix descriptions before adding prompt mass.

## Official Reference Docs
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview>
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices>
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/skill-format>
- <https://docs.claude.com/en/docs/agents-and-tools/agent-skills/subagents>
