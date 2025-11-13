# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and semantic versioning.

## [Unreleased]

### Added
- Payload manifest (`manifest.json`) with per-file checksums enforced at runtime.
- `claude-workflow sync/upgrade --release` for fetching payloads from GitHub Releases with caching and bundled fallback.
- Release packaging script (`scripts/package_payload_archive.py`) that produces versioned payload zip, manifest copy and checksum files for publication.
- QA gate: `.claude/hooks/gate-qa.sh`, heuristic agent `scripts/qa-agent.py`, `docs/qa-playbook.md`, and `/.claude/agents/qa.md` with severity guidance.
- CI now executes the QA gate (`.github/workflows/ci.yml`) with diff-aware analysis (`QA_AGENT_DIFF_BASE`).
- Analyst dialog enforcement: updated `/.claude/agents/analyst.md`, PRD template with `## Диалог analyst`, new CLI command `claude-workflow analyst-check`, gate-workflow integration, smoke coverage, and docs/tests showing the `Ответ N:` workflow.
- Progress tracking: CLI command `claude-workflow progress`, new `tasklist_progress` gate in `config/gates.json`, gate-workflow integration, smoke coverage, and unit tests validating missing/updated checkboxes.
- Iteration playbooks updated for implementer/reviewer/qa agents, tasklist template guidance (`Checkbox updated: …`), and docs (`README`, `workflow.md`, `docs/agents-playbook.md`, `docs/qa-playbook.md`) reflecting the mandatory tasklist sync.
- Migration helper `tools/migrate_ticket.py` (and payload copy) for converting legacy slug-based repositories to the ticket-first layout.
- Auto PRD scaffolding: `tools/set_active_feature.py` and `claude_workflow_cli.feature_ids` now create `docs/prd/<ticket>.prd.md` with `Status: draft`, so agents/gates always work against an existing artefact.

### Changed
- Tasklist артефакты перемещены в `docs/tasklist/<ticket>.md`: обновлены шаблоны, init/CLI пресеты, гейты, тесты и документация; добавлен скрипт миграции `scripts/migrate-tasklist.py` и автоперенос в `set_active_feature.py`.
- Workflow, commands, и агентские инструкции переведены на ticket-first модель (`--ticket`, `docs/.active_ticket`, slug-hint как опциональный контекст); обновлены README, `workflow.md`, `docs/agents-playbook.md`, `docs/qa-playbook.md`, `docs/feature-cookbook.md`, `docs/customization.md`, дизайн-пресеты и шаблоны tasklist.
- `scripts/prd_review_gate.py`, smoke tests, и `analyst-check` теперь трактуют `Status: draft` как черновой PRD, блокируя коммиты до заполнения диалога и обновления статусов.

### Fixed
- CLI now falls back to the bundled payload when release downloads fail.

## [0.1.0] - 2025-02-XX

### Added
- Initial release of `claude-workflow-cli` packaging and installation instructions.
