# AGENTS (Repo development guide)

> INTERNAL/DEV-ONLY: maintainer contract for repository development and release.

Owner: feature-dev-aidd
Last reviewed: 2026-04-18
Status: active

This file is the repo-level maintainer contract. User-facing workspace guidance lives in `skills/aidd-core/templates/workspace-agents.md`.

## Repo contract
- Runtime/plugin surface: `agents/`, `skills/`, `hooks/`, `.claude-plugin/`.
- Workspace bootstrap templates: `templates/aidd/` for config/placeholders only.
- User/workspace artifacts live under `aidd/**`.
- Repo-only tooling lives under `tests/repo_tools/`.
- Generated E2E prompt copies live under `docs/e2e/*.txt` for operator copy/paste use.
- Canonical runtime entrypoints stay at `skills/<stage>/runtime/*.py`.
- Public slash commands, hook command names, and artifact names are compatibility surface and must stay stable unless explicitly versioned.

## Source of truth map
- Skill/agent authoring policy: `docs/skill-authoring.md`.
- Stage content templates: `skills/*/templates/*`.
- E2E audit prompt source fragments: `tests/repo_tools/e2e_prompt/*`; assembled tracked copies: `docs/e2e/*.txt`.
- Workspace bootstrap source: `templates/aidd/**`.
- Hook wiring: `hooks/hooks.json`.
- Prompt/version lint baseline: `docs/migrations/stage_skills_frontmatter.json`.
- Release/public docs split: `docs/release-docs-manifest.yaml`.
- User guide template copied into workspaces: `skills/aidd-core/templates/workspace-agents.md`.

## Lifecycle rules
- Default bias: delete, archive, or collapse inactive repo surface unless there is a current runtime, CI, or release consumer.
- Do not keep repo-only utilities in active surface without CI, release, or explicit operator ownership.
- Archive historical RFCs, closure notes, and runbooks under `docs/archive/**`; keep active docs short and operational.
- `aidd_runtime/**`, compatibility layers, and `legacy|compat|fallback|shadow` branches require explicit validation before deletion.
- Generated outputs may stay in git only when CI or release tooling reads them directly.

## Runtime and path rules
- `aidd_runtime/` is the explicit Python package namespace. Do not rely on package `__path__` mutation to expose `skills/*/runtime`.
- Reusable runtime/library code belongs in `aidd_runtime/**`.
- `skills/*/runtime/*.py` should stay thin entrypoints or compatibility wrappers around explicit package modules.
- Shell entrypoints are allowed only for hooks or platform glue.
- Hooks and runtime code must resolve workspace/project root from payload or explicit args, not by writing into plugin cache.

## Release checks
- Required local gates:
  - `tests/repo_tools/ci-lint.sh`
  - `tests/repo_tools/smoke-workflow.sh`
- Prompt/policy checks:
  - `python3 tests/repo_tools/lint-prompts.py --root .`
  - `python3 tests/repo_tools/build_e2e_prompts.py --check`
- Release docs/checklist:
  - `docs/runbooks/marketplace-release.md`
  - `docs/release-docs-manifest.yaml`

## Minimal dependencies
- Required: `python3`, `rg`, `git`
- Extra repo-tool lint deps may be soft-skipped by CI helpers: `shellcheck`, `markdownlint`, `yamllint`
