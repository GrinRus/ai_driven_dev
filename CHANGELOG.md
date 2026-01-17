# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and semantic versioning.

## [Unreleased]

### Added
- `${CLAUDE_PLUGIN_ROOT}/tools/doctor.sh` for environment/path diagnostics and workspace checks.
- Test profiles `fast/targeted/full/none` via `aidd/.cache/test-policy.env` and `AIDD_TEST_*` flags for `format-and-test.sh`.
- Dedupe cache `aidd/.cache/format-and-test.last.json` to avoid repeating test runs when diff/profile are unchanged.
- `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh` to validate research artefacts before planning.
- PRD template section `## AIDD:RESEARCH_HINTS` for passing paths/keywords to `/feature-dev-aidd:researcher`.
- New review-plan stage with `plan-reviewer`, `## Plan Review` in plans, and a `plan_review` gate.
- SDLC contract docs: `aidd/docs/sdlc-flow.md` and `aidd/docs/status-machine.md`.
- `aidd/AGENTS.md` as the primary agent entrypoint.
- Plan template (`aidd/docs/plan/template.md`) with mandatory executability sections.
- QA gate: `aidd/hooks/gate-qa.sh`, heuristic agent via `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh`, and `aidd/agents/qa.md` with severity guidance.
- CI now executes the QA gate (`dev/.github/workflows/ci.yml`) with diff-aware analysis (`QA_AGENT_DIFF_BASE`).
- Analyst dialog enforcement: updated `aidd/agents/analyst.md`, PRD template with `## Диалог analyst`, script `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh`, gate-workflow integration, smoke coverage, and docs/tests showing the `Ответ N:` workflow.
- Progress tracking: script `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh`, new `tasklist_progress` gate in `config/gates.json`, gate-workflow integration, smoke coverage, and unit tests validating missing/updated checkboxes.
- Iteration guidance updated for implementer/reviewer/qa agents, tasklist template guidance (`Checkbox updated: …`), and docs (`README`, `dev/doc/workflow.md`) reflecting the mandatory tasklist sync.
- Auto PRD scaffolding: `${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh` and `tools/feature_ids.py` now create `aidd/docs/prd/<ticket>.prd.md` with `Status: draft`, so agents/gates always work against an existing artefact.
- Runtime workflow tools: `${CLAUDE_PLUGIN_ROOT}/tools/prd-review.sh`, `plan-review-gate`, `prd-review-gate`, `research`, and `context-gc-*.sh`.
- Agent-first documentation set: updated `/feature-dev-aidd:idea-new`, `dev/doc/templates/prompts/prompt-agent.md`, `dev/doc/templates/prompts/prompt-command.md`, PRD/tasklist/research templates, README (RU/EN), `dev/doc/workflow.md`, `dev/doc/feature-cookbook.md`, `dev/doc/customization.md`, ensuring agents log repository inputs and script commands before asking the user.

### Changed
- Docs and prompts now use namespaced slash commands (`/feature-dev-aidd:*`) for marketplace installs.
- Marketplace manifest uses a GitHub source for the plugin, and `plugin.json` now includes author/repository/homepage/license metadata.
- Marketplace-only distribution: replaced `claude-workflow` CLI with `${CLAUDE_PLUGIN_ROOT}/tools/*.sh` entrypoints; payload sync/upgrade and release packaging removed.
- `/feature-dev-aidd:implement` and `implementer` prompts now require a test policy, iteration budget, and report `Test profile`/`Tests run` in the response.
- `format-and-test.sh` selects tasks by profile (`fastTasks/fullTasks/targetedTask`) and honors `AIDD_TEST_FORCE` when repeating runs.
- `/feature-dev-aidd:idea-new` no longer triggers research; analyst captures `AIDD:RESEARCH_HINTS`, research is run in `/feature-dev-aidd:researcher`.
- `analyst-check` no longer validates research; research validation is handled by `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh` and `gate-workflow`.
- `/feature-dev-aidd:plan-new` now runs `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh` before planning.
- Canonical flow now includes plan review: idea → research → plan → review-plan → review-prd → tasklist → implement → review → qa.
- Commands are thin orchestrators; agents carry algorithms/stop-conditions with a unified question format (Blocker/Clarification + rationale/options/default).
- Output contract standardized (`Checkbox updated` + `Status` + `Artifacts updated` + `Next actions`), search unified on `rg`.
- Research/tasklist/QA templates updated with Context Pack, AIDD:NEXT_3, AIDD:HANDOFF_INBOX, and QA traceability to AIDD:ACCEPTANCE.
- `gate-workflow` and smoke/tests updated to enforce review-plan before PRD review/tasklist.
- Tasklist артефакты перемещены в `aidd/docs/tasklist/<ticket>.md`: обновлены шаблоны, init/CLI команды, гейты, тесты и документация; legacy `tasklist.md` больше не мигрируется автоматически.
- `set-active-feature` больше не нормализует front-matter tasklist и не переносит legacy `tasklist.md`.
- Workflow, commands, и агентские инструкции переведены на ticket-first модель (`--ticket`, `aidd/docs/.active_ticket`, slug-hint как опциональный контекст); обновлены README, `dev/doc/workflow.md`, `dev/doc/feature-cookbook.md`, `dev/doc/customization.md` и шаблоны tasklist.
- `prd-review-gate`, smoke tests, и `analyst-check` теперь трактуют `Status: draft` как черновой PRD, блокируя коммиты до заполнения диалога и обновления статусов.
- Hooks call `${CLAUDE_PLUGIN_ROOT}/hooks/*.sh` and runtime tools call `${CLAUDE_PLUGIN_ROOT}/tools/*.sh`; no `claude-workflow` dependency.
- `dev/repo_tools/ci-lint.sh` запускает линтер промптов, dry-run `dev/repo_tools/prompt-version`, новые тесты (`dev/tests/test_prompt_lint.py`, `dev/tests/test_prompt_versioning.py`) и smoke/gate-workflow проверки.
- Analyst/researcher/implementer prompts now require citing checked files and executed commands (`rg`, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh`, `<test-runner> <args>`), while tasklist/research templates embed `Commands/Reports` blocks so downstream agents inherit reproducible context.
- Prompt specs now standardize PRD/PRD Review statuses to `READY/BLOCKED/PENDING`, accept free-form notes after the ticket in every command, and align `allowed-tools` with subagent requirements.
- Prompt linting validates duplicate front matter keys, disallowed statuses, HTML-escaped `<ticket>`, `Checkbox updated` placement hints, and tool parity across paired prompts.
- Внутренний backlog (`dev/doc/backlog.md`) оставлен dev-only и исключён из marketplace-плагина; lint/check скрипты больше не ожидают каталог `doc/`.

### Fixed
- Updated `aidd` snapshot to match marketplace scripts and docs (removed stale `claude-workflow` references).

## [0.1.0] - 2025-02-XX

### Added
- Initial release of `claude-workflow-cli` packaging and installation instructions.
