# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and semantic versioning.

## [Unreleased]

### Added
- Test profiles `fast/targeted/full/none` via `aidd/.cache/test-policy.env` and `AIDD_TEST_*` flags for `format-and-test.sh`.
- Dedupe cache `aidd/.cache/format-and-test.last.json` to avoid repeating test runs when diff/profile are unchanged.
- `claude-workflow research-check` to validate research artefacts before planning.
- PRD template section `## Research Hints` for passing paths/keywords to `/researcher`.
- New review-plan stage with `plan-reviewer`, `## Plan Review` in plans, and a `plan_review` gate.
- SDLC contract docs: `aidd/docs/sdlc-flow.md` and `aidd/docs/status-machine.md`.
- `aidd/AGENTS.md` as the primary agent entrypoint.
- Plan template (`aidd/docs/plan/template.md`) with mandatory executability sections.
- Payload manifest (`manifest.json`) with per-file checksums enforced at runtime.
- `claude-workflow sync/upgrade --release` for fetching payloads from GitHub Releases with caching and bundled fallback.
- Release packaging script (`scripts/package_payload_archive.py`) that produces versioned payload zip, manifest copy and checksum files for publication.
- QA gate: `aidd/hooks/gate-qa.sh`, heuristic agent via `claude-workflow qa`, `doc/dev/qa-playbook.md`, and `aidd/agents/qa.md` with severity guidance.
- CI now executes the QA gate (`.github/workflows/ci.yml`) with diff-aware analysis (`QA_AGENT_DIFF_BASE`).
- Analyst dialog enforcement: updated `aidd/agents/analyst.md`, PRD template with `## Диалог analyst`, new CLI command `claude-workflow analyst-check`, gate-workflow integration, smoke coverage, and docs/tests showing the `Ответ N:` workflow.
- Progress tracking: CLI command `claude-workflow progress`, new `tasklist_progress` gate in `config/gates.json`, gate-workflow integration, smoke coverage, and unit tests validating missing/updated checkboxes.
- Iteration playbooks updated for implementer/reviewer/qa agents, tasklist template guidance (`Checkbox updated: …`), and docs (`README`, `workflow.md`, `doc/dev/agents-playbook.md`, `doc/dev/qa-playbook.md`) reflecting the mandatory tasklist sync.
- Auto PRD scaffolding: `claude-workflow set-active-feature` and `claude_workflow_cli.feature_ids` now create `aidd/docs/prd/<ticket>.prd.md` with `Status: draft`, so agents/gates always work against an existing artefact.
- CLI-first workflow tools: `claude-workflow prd-review`, `plan-review-gate`, `prd-review-gate`, `researcher-context`, and `context-gc`.
- Release helper `scripts/prompt-release.sh` автоматизирует цепочку `prompt-version bump → lint → pytest → payload sync → gate-tests` перед публикацией payload/релиза.
- Agent-first documentation set: updated `/idea-new`, `templates/prompt-agent.md`, `templates/prompt-command.md`, PRD/tasklist/research templates, README (RU/EN), `workflow.md`, `doc/dev/feature-cookbook.md`, `aidd/docs/customization.md`, `doc/dev/agents-playbook.md`, ensuring agents log repository inputs and CLI commands before asking the user.

### Changed
- `/implement` and `implementer` prompts now require a test policy, iteration budget, and report `Test profile`/`Tests run` in the response.
- `format-and-test.sh` selects tasks by profile (`fastTasks/fullTasks/targetedTask`) and honors `AIDD_TEST_FORCE` when repeating runs.
- `/idea-new` no longer triggers research; analyst captures `Research Hints`, research is run in `/researcher`.
- `analyst-check` no longer validates research; research validation is handled by `research-check` and `gate-workflow`.
- `/plan-new` now runs `research-check` before planning.
- Canonical flow now includes plan review: idea → research → plan → review-plan → review-prd → tasklist → implement → review → qa.
- Commands are thin orchestrators; agents carry algorithms/stop-conditions with a unified question format (Blocker/Clarification + rationale/options/default).
- Output contract standardized (`Checkbox updated` + `Status` + `Artifacts updated` + `Next actions`), search unified on `rg`.
- Research/tasklist/QA templates updated with Context Pack, Next 3, Handoff inbox, and QA traceability to acceptance criteria.
- `gate-workflow` and smoke/tests updated to enforce review-plan before PRD review/tasklist.
- Tasklist артефакты перемещены в `aidd/docs/tasklist/<ticket>.md`: обновлены шаблоны, init/CLI команды, гейты, тесты и документация; legacy `tasklist.md` больше не мигрируется автоматически.
- `claude-workflow set-active-feature` больше не нормализует front-matter tasklist и не переносит legacy `tasklist.md`.
- Workflow, commands, и агентские инструкции переведены на ticket-first модель (`--ticket`, `aidd/docs/.active_ticket`, slug-hint как опциональный контекст); обновлены README, `workflow.md`, `doc/dev/agents-playbook.md`, `doc/dev/qa-playbook.md`, `doc/dev/feature-cookbook.md`, `aidd/docs/customization.md` и шаблоны tasklist.
- `claude-workflow prd-review-gate`, smoke tests, и `analyst-check` теперь трактуют `Status: draft` как черновой PRD, блокируя коммиты до заполнения диалога и обновления статусов.
- Payload hooks now call `claude-workflow` directly; legacy `aidd/scripts` and `aidd/tools` copies are removed from the payload.
- `scripts/ci-lint.sh` запускает линтер промптов, dry-run `scripts/prompt-version`, новые тесты (`tests/test_prompt_lint.py`, `tests/test_prompt_versioning.py`) и smoke/gate-workflow проверки.
- Analyst/researcher/implementer prompts now require citing checked files and executed commands (`rg`, `claude-workflow progress`, `<test-runner> <args>`), while tasklist/research templates embed `Commands/Reports` blocks so downstream agents inherit reproducible context.
- Prompt specs now standardize PRD/PRD Review statuses to `READY/BLOCKED/PENDING`, accept free-form notes after the ticket in every command, and align `allowed-tools` with subagent requirements.
- Prompt linting validates duplicate front matter keys, disallowed statuses, HTML-escaped `<ticket>`, `Checkbox updated` placement hints, and tool parity across paired prompts.
- `tools/check_payload_sync.py` now has a standard payload path list and warns when the runtime snapshot (`aidd/`) is missing.
- Внутренний backlog (`doc/dev/backlog.md`) оставлен dev-only и исключён из payload/manifest; sync/check скрипты больше не ожидают каталог `doc/` и предотвращают попадание файла в релиз.

### Fixed
- CLI now falls back to the bundled payload when release downloads fail.

## [0.1.0] - 2025-02-XX

### Added
- Initial release of `claude-workflow-cli` packaging and installation instructions.
