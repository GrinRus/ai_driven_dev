# Skill Language Policy

> INTERNAL/DEV-ONLY: maintainer lint/prompt policy source of truth.

Owner: feature-dev-aidd
Last reviewed: 2026-04-12
Status: active

This document defines the canonical prompt-language and structure policy used by `tests/repo_tools/lint-prompts.py`.

## Scope
- Applies to every `skills/*/SKILL.md` file.
- Applies to every `agents/*.md` prompt file.
- Applies to stage-command skill frontmatter parity checks via migration baseline.

## Sources of Truth
- `https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview`
- `https://docs.claude.com/en/docs/agents-and-tools/agent-skills/best-practices`
- `https://docs.claude.com/en/docs/agents-and-tools/agent-skills/skill-format`
- `https://docs.claude.com/en/docs/agents-and-tools/agent-skills/subagents`
- `https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf?hsLang=en`

## Rules
- Prompt corpus is EN-only: both `skills/*/SKILL.md` and `agents/*.md` must remain free of Cyrillic text.
- Every skill frontmatter must include `name`, and `name` must match the skill directory.
- Every skill frontmatter must include `description`, `lang`, `model`, and `user-invocable`.
- Every agent frontmatter must include `name`, `description`, `lang`, `model`, `permissionMode`, and `skills`.
- Every skill `description` must contain both:
  - positive trigger clause: `Use when ...`
  - anti-trigger clause: `Do not use when ...`
- `Use when` must appear before `Do not use when`, and both clauses must be non-trivial.
- Anti-trigger clause must reference neighboring skill names or explicit outside-AIDD scope.
- Trigger boundaries must be aligned with `docs/skill-trigger-taxonomy.md`.
- Skill routing quality policy lives in `tests/repo_tools/skill_eval/policy.v1.json` and is evaluated by:
  - `tests/repo_tools/skill_eval_run.py` (benchmark run),
  - `tests/repo_tools/skill_eval_compare.py` (baseline vs candidate + advisory/hard gate checks).
- Shared skills and stage skills must include:
  - `## Command contracts` with interface cards (`When to run`, `Inputs`, `Outputs`, `Failure mode`, `Next action`),
  - `## Additional resources` with progressive-disclosure markers (`when:` and `why:` per item).
- Agent prompts must use canonical EN section headers:
  - `## Context`
  - `## Input Artifacts`
  - `## Automation`
  - `## Steps`
  - `## Fail-fast and Questions`
  - `## Response Format`
- Every stage skill must keep `prompt_version` and `source_version` in semver format.
- `source_version` must match `prompt_version` for current workflow policy.
- User-invocable stage skills must expose canonical Python runtime entrypoints:
  - `skills/<stage>/runtime/*.py`
  - `allowed-tools` must include `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/<stage>/runtime/<entrypoint>.py *)`.
- Bash wildcard grammar:
  - canonical: `Bash(<command> *)`,
  - legacy transitional: colon-wildcard form (default policy is `error`; temporary compatibility requires `AIDD_BASH_LEGACY_POLICY=warn|allow`).
- Stage skills may reference runtime only from:
  - their own stage path (`skills/<stage>/runtime/*`), and
  - approved shared skills (`aidd-core`, `aidd-loop`, `aidd-rlm`, `aidd-policy`, `aidd-docio`, `aidd-flow-state`, `aidd-observability`).
- Stage skills must not set `context` or `agent` frontmatter; explicit `Run subagent` orchestration is required instead.
- Runtime references to stage `scripts/*` are forbidden for stage skills.
- Target compactness:
  - warning: skill files above 220 lines,
  - error: skill files above 300 lines.

## Baseline Source
- Frontmatter parity baseline is stored in:
  - `aidd/reports/migrations/commands_to_skills_frontmatter.json`
  - fallback: `docs/migrations/commands_to_skills_frontmatter.json`
