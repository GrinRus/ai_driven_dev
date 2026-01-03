# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and semantic versioning.

## [Unreleased]

### Added
- New review-plan stage with `plan-reviewer`, `## Plan Review` in plans, and a `plan_review` gate.
- SDLC contract docs: `aidd/docs/sdlc-flow.md` and `aidd/docs/status-machine.md`.
- `aidd/AGENTS.md` plus root `AGENTS.md` as the primary agent entrypoint.
- Plan template (`aidd/docs/plan/template.md`) with mandatory executability sections.
- Payload manifest (`manifest.json`) with per-file checksums enforced at runtime.
- `claude-workflow sync/upgrade --release` for fetching payloads from GitHub Releases with caching and bundled fallback.
- Release packaging script (`scripts/package_payload_archive.py`) that produces versioned payload zip, manifest copy and checksum files for publication.
- QA gate: `aidd/hooks/gate-qa.sh`, heuristic agent `scripts/qa-agent.py`, `aidd/docs/qa-playbook.md`, and `aidd/agents/qa.md` with severity guidance.
- CI now executes the QA gate (`.github/workflows/ci.yml`) with diff-aware analysis (`QA_AGENT_DIFF_BASE`).
- Analyst dialog enforcement: updated `aidd/agents/analyst.md`, PRD template with `## Диалог analyst`, new CLI command `claude-workflow analyst-check`, gate-workflow integration, smoke coverage, and docs/tests showing the `Ответ N:` workflow.
- Progress tracking: CLI command `claude-workflow progress`, new `tasklist_progress` gate in `config/gates.json`, gate-workflow integration, smoke coverage, and unit tests validating missing/updated checkboxes.
- Iteration playbooks updated for implementer/reviewer/qa agents, tasklist template guidance (`Checkbox updated: …`), and docs (`README`, `workflow.md`, `docs/agents-playbook.md`, `docs/qa-playbook.md`) reflecting the mandatory tasklist sync.
- Migration helper `tools/migrate_ticket.py` (and payload copy) for converting legacy slug-based repositories to the ticket-first layout.
- Auto PRD scaffolding: `tools/set_active_feature.py` and `claude_workflow_cli.feature_ids` now create `aidd/docs/prd/<ticket>.prd.md` with `Status: draft`, so agents/gates always work against an existing artefact.
- Prompt locale selector: `init-claude-workflow.sh`/`claude-workflow init` accept `--prompt-locale en`, копируя английские шаблоны в `aidd/agents|commands` и добавляя `aidd/prompts/en/**` в проект.
- Release helper `scripts/prompt-release.sh` автоматизирует цепочку `prompt-version bump → lint → pytest → payload sync → gate-tests` перед публикацией payload/релиза.
- Bilingual prompt workflow: EN prompts live under `aidd/prompts/en/**`, added `aidd/docs/prompt-versioning.md`, `tools/prompt_diff.py`, `scripts/prompt-version`, lint parity, and gate-workflow blocks commits when RU/EN локали расходятся.
- Agent-first documentation set: updated `/idea-new`, `templates/prompt-agent.md`, `templates/prompt-command.md`, PRD/tasklist/research templates, README (RU/EN), `workflow.md`, `aidd/docs/feature-cookbook.md`, `aidd/docs/customization.md`, `aidd/docs/agents-playbook.md`, ensuring agents log repository inputs and CLI commands before asking the user.

### Changed
- Canonical flow now includes plan review: idea → research → plan → review-plan → review-prd → tasklist → implement → review → qa.
- Commands are thin orchestrators; agents carry algorithms/stop-conditions with a unified question format (Blocker/Clarification + rationale/options/default).
- Output contract standardized (`Checkbox updated` + `Status` + `Artifacts updated` + `Next actions`), search unified on `rg`.
- Research/tasklist/QA templates updated with Context Pack, Next 3, Handoff inbox, and QA traceability to acceptance criteria.
- `gate-workflow` and smoke/tests updated to enforce review-plan before PRD review/tasklist.
- Tasklist артефакты перемещены в `aidd/docs/tasklist/<ticket>.md`: обновлены шаблоны, init/CLI пресеты, гейты, тесты и документация; добавлен скрипт миграции `scripts/migrate-tasklist.py` и автоперенос в `set_active_feature.py`.
- Workflow, commands, и агентские инструкции переведены на ticket-first модель (`--ticket`, `aidd/docs/.active_ticket`, slug-hint как опциональный контекст); обновлены README, `workflow.md`, `aidd/docs/agents-playbook.md`, `aidd/docs/qa-playbook.md`, `aidd/docs/feature-cookbook.md`, `aidd/docs/customization.md`, дизайн-пресеты и шаблоны tasklist.
- `scripts/prd_review_gate.py`, smoke tests, и `analyst-check` теперь трактуют `Status: draft` как черновой PRD, блокируя коммиты до заполнения диалога и обновления статусов.
- `scripts/ci-lint.sh` запускает линтер промптов, dry-run `scripts/prompt-version`, новые тесты (`tests/test_prompt_lint.py`, `tests/test_prompt_diff.py`, `tests/test_prompt_versioning.py`), а smoke/gate-workflow проверяют синхронность RU/EN.
- Analyst/researcher/implementer prompts now require citing checked files and executed commands (`rg`, `claude-workflow progress`, `<test-runner> <args>`), while tasklist/research templates embed `Commands/Reports` blocks so downstream agents inherit reproducible context.
- Prompt specs now standardize PRD/PRD Review statuses to `READY/BLOCKED/PENDING`, accept free-form notes after the ticket in every command, and align `allowed-tools` with subagent requirements.
- Prompt linting validates duplicate front matter keys, disallowed statuses, HTML-escaped `<ticket>`, `Checkbox updated` placement hints, and tool parity across paired prompts.
- EN prompt parity tightened: report paths use `${CLAUDE_PLUGIN_ROOT:-./aidd}`, `/review-spec` accepts free-form notes, tasklist ownership is clarified for research/review agents, and the prompt linter now validates `Статус:` markers.
- RU prompt placeholders normalized to `@aidd/docs/.../<ticket>...`, EN `/implement` instructions now reference `${CLAUDE_PLUGIN_ROOT:-./aidd}`, and prompt-lint tests cover `Статус:` validation.
- EN `/qa` now uses `${CLAUDE_PLUGIN_ROOT:-./aidd}` for the default test hook path, and implementer tools include the `format-and-test.sh` hook.
- `tools/check_payload_sync.py` now has a standard payload path list and warns when the runtime snapshot (`aidd/`) is missing.
- Внутренний backlog (`doc/dev/backlog.md`) оставлен dev-only и исключён из payload/manifest; sync/check скрипты больше не ожидают каталог `doc/` и предотвращают попадание файла в релиз.

### Fixed
- CLI now falls back to the bundled payload when release downloads fail.

## [0.1.0] - 2025-02-XX

### Added
- Initial release of `claude-workflow-cli` packaging and installation instructions.
