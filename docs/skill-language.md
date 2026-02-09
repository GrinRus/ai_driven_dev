# Skill Language Policy

This document defines the canonical prompt-language and structure policy used by `tests/repo_tools/lint-prompts.py`.

## Scope
- Applies to every `skills/*/SKILL.md` file.
- Applies to stage-command skill frontmatter parity checks via migration baseline.

## Rules
- Skill prompts are EN-only for shared consistency checks.
- Every stage skill must keep `prompt_version` and `source_version` in semver format.
- `source_version` must match `prompt_version` for current workflow policy.
- User-invocable stage skills must expose canonical Python runtime entrypoints:
  - `skills/<stage>/runtime/*.py`
  - `allowed-tools` must include `Bash(python3 ${CLAUDE_PLUGIN_ROOT}/skills/<stage>/runtime/<entrypoint>.py:*)`.
- Stage skills may reference wrappers/runtime only from:
  - their own stage path (`skills/<stage>/{runtime,scripts}/*`), and
  - approved shared skills (`aidd-core`, `aidd-loop`, `aidd-rlm`, `aidd-policy`, `aidd-docio`, `aidd-flow-state`, `aidd-observability`).
- Runtime references to `scripts/run.sh` are forbidden for stage skills.
- User-invocable stage skills must include:
  - `## Command contracts` with interface cards (`When to run`, `Inputs`, `Outputs`, `Failure mode`, `Next action`),
  - `## Additional resources` with progressive-disclosure markers (`when:` and `why:` per item).
- Target compactness:
  - warning: skill files above 220 lines,
  - error: skill files above 300 lines.

## Baseline Source
- Frontmatter parity baseline is stored in:
  - `aidd/reports/migrations/commands_to_skills_frontmatter.json`
  - fallback: `dev/reports/migrations/commands_to_skills_frontmatter.json`
