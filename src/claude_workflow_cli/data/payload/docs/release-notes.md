# Release Notes Process

Документ описывает, как готовить и публиковать релизы Claude Code workflow.

## Версионирование
- Используем семантическую схему `MAJOR.MINOR.PATCH`.
- `MAJOR` — несовместимые изменения (структура артефактов, критические API-изменения скриптов).
- `MINOR` — новые возможности и улучшения, сохраняющие обратную совместимость.
- `PATCH` — исправления багов, обновления документации или улучшения, не влияющие на интерфейсы.
- Текущая версия указывается в README и релизных заметках.

## Структура release notes
Каждый релиз получает файл/раздел вида:

```
## vX.Y.Z — YYYY-MM-DD
### Added
- ...

### Changed
- ...

### Fixed
- ...

### Migration
- ...
```

Секции «Migration» и «Breaking changes» заполняются только при необходимости.

## Подготовка релиза
- [ ] Обновить `README.md` и `README.en.md` (TL;DR, список фич, ссылки на новые документы).
- [ ] Проверить Wave backlog — закрыть выполненные пункты и создать Wave 2/3 для новых задач.
- [ ] Обновить демо (`examples/gradle-demo/`) и убедиться, что `examples/apply-demo.sh` отрабатывает без ошибок.
- [ ] Убедиться, что CI (`.github/workflows/ci.yml`) проходит на ветке `main`.
- [ ] Выполнить `scripts/ci-lint.sh` локально.
- [ ] Синхронизировать RU/EN промпты: `./scripts/prompt-release.sh --part patch` (или `--dry-run`) — скрипт выполняет bump, lint, pytest и проверку payload/gate. При необходимости дополнительно запустите `python3 tools/prompt_diff.py --kind agent --name <name>` точечно.
- [ ] Синхронизировать payload: `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py && pytest tests/test_init_hook_paths.py`. Только после этого публикуйте пакет/релиз.
- [ ] Зафиксировать изменения в `docs/release-notes.md`.

## Публикация релиза
- [ ] Проставить тег `vX.Y.Z` (annotated tag).
- [ ] Создать GitHub Release и вложить основные тезисы из release notes.
- [ ] Загрузить артефакты из `dist/`: wheel/tarball, `claude-workflow-payload-<tag>.zip`, `claude-workflow-manifest-<tag>.json` и соответствующие `.sha256`.
- [ ] Приложить ссылки на новые/обновлённые документы (usage/customization/command reference).
- [ ] Обновить `workflow.md` (и при необходимости `docs/customization.md`), если поведение установки изменилось.
- [ ] Сообщить в выбранных каналах (Slack, email, команда).

## Пост-релиз
- [ ] Создать задачу на планирование следующего релиза.
- [ ] Собрать обратную связь от пользователей (issues, комментарии).
- [ ] Проверить, что `.claude/settings.json` соответствует политике доступа.
- [ ] Обновить Wave backlog: перенести оставшиеся задачи в следующую волну.

Храните заметки в одном файле (`docs/release-notes.md`), добавляя записи в обратном хронологическом порядке.

## vNext — YYYY-MM-DD

### Added
- `tools/migrate_ticket.py` — миграция существующих slug-ориентированных установок на ticket-first layout (`docs/.active_ticket`, обновлённый front-matter tasklist).
- Автосоздание PRD: `tools/set_active_feature.py` и `claude_workflow_cli.feature_ids` теперь сразу создают `docs/prd/<ticket>.prd.md` со статусом `Status: draft`, так что гейты видят артефакт до начала диалога.
- Двуязычные промпты: EN-варианты в `prompts/en/**`, линтер синхронизирует RU/EN, добавлены `docs/prompt-versioning.md`, `tools/prompt_diff.py`, `scripts/prompt-version`, а gate-workflow блокирует несогласованные обновления.
- Добавлен флаг `--prompt-locale en` для `init-claude-workflow.sh`/`claude-workflow init`, который устанавливает EN-вариант `.claude/agents|commands`, а в проект копируется каталог `prompts/en/**` для дальнейшей синхронизации.

### Changed
- Workflow, документация и шаблоны переведены на ticket-first модель: команды принимают `--ticket`, slug-hint стал опциональным алиасом, обновлены README, playbook-и, tasklist-шаблон и smoke-сценарий.
- `scripts/prd_review_gate.py` и `analyst-check` учитывают `Status: draft`: гейты блокируют PRD до тех пор, пока диалог не доведён до READY и PRD Review не утверждён; smoke и unit-тесты обновлены под новый сценарий.
- `scripts/ci-lint.sh` запускает `scripts/lint-prompts.py`, dry-run `scripts/prompt-version`, новые юнит-тесты (`tests/test_prompt_lint.py`, `tests/test_prompt_diff.py`, `tests/test_prompt_versioning.py`), а `scripts/smoke-workflow.sh` проверяет блокировку RU-only изменений промптов.

### Migration
- Выполните `python3 tools/migrate_ticket.py` в корне проекта, чтобы создать `docs/.active_ticket` (если отсутствует) и дополнить `docs/tasklist/*.md` полями `Ticket` и `Slug hint`. После миграции повторите smoke-тест `scripts/smoke-workflow.sh`.
