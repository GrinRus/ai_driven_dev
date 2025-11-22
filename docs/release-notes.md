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

## Автоматизация
- Версия берётся из `pyproject.toml`. Пуш в `main` запускает job Auto Tag: если версия больше последнего `v*`, создаётся аннотированный тег `vX.Y.Z`; даунгрейд блокируется; итоги пишутся в `GITHUB_STEP_SUMMARY`.
- Тег `v*` запускает workflow Release: `uv build` собирает wheel+sdist, `scripts/package_payload_archive.py` добавляет payload zip и manifest с checksum; артефакты уходят в GitHub Release и как CI artefact. Тело релиза берётся из верхней секции `## v…` этого файла.
- Если верхний блок не обновлён под целевую версию (или отсутствует), Release упадёт на шаге извлечения заметок — поправьте файл и перезапустите workflow.

## Шаблон раздела (используется в Release)
Удерживайте верхний блок актуальным — он попадёт в GitHub Release.

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

## Подготовка релиза
- [ ] Обновить `README.md` и `README.en.md` (TL;DR, список фич, ссылки на новые документы).
- [ ] Проверить Wave backlog — закрыть выполненные пункты и создать Wave 2/3 для новых задач.
- [ ] Обновить демо (`examples/gradle-demo/`) и убедиться, что `examples/apply-demo.sh` отрабатывает без ошибок.
- [ ] Убедиться, что CI (`.github/workflows/ci.yml`) проходит на ветке `main`.
- [ ] Выполнить `scripts/ci-lint.sh` локально.
- [ ] Синхронизировать RU/EN промпты: `./scripts/prompt-release.sh --part patch` (или `--dry-run`) — скрипт выполняет bump, lint, pytest и проверку payload/gate. При необходимости дополнительно запустите `python3 tools/prompt_diff.py --kind agent --name <name>` точечно.
- [ ] Синхронизировать payload: `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py && pytest tests/test_init_hook_paths.py`. Только после этого публикуйте пакет/релиз.
- [ ] Убедиться, что dev-only артефакты (например, `doc/backlog.md`) не попали в payload/manifest; каталог `doc/` исключён из sync по умолчанию.
- [ ] Зафиксировать изменения в `docs/release-notes.md`.

## Публикация релиза
- [ ] Убедиться, что Auto Tag в Actions проставил аннотированный тег `vX.Y.Z` (при необходимости перезапустить job после обновления версии в `pyproject.toml`).
- [ ] Подождать workflow Release: он сам создаст GitHub Release, подтянет верхний блок этого файла в тело и загрузит артефакты (`*.whl`, `*.tar.gz`, `claude-workflow-payload-<tag>.zip`, `claude-workflow-manifest-<tag>.json` + `.sha256`).
- [ ] Приложить ссылки на новые/обновлённые документы (usage/customization/command reference).
- [ ] Обновить `workflow.md` (и при необходимости `docs/customization.md`), если поведение установки изменилось.
- [ ] Сообщить в выбранных каналах (Slack, email, команда).

## Пост-релиз
- [ ] Создать задачу на планирование следующего релиза.
- [ ] Собрать обратную связь от пользователей (issues, комментарии).
- [ ] Проверить, что `.claude/settings.json` соответствует политике доступа.
- [ ] Обновить Wave backlog: перенести оставшиеся задачи в следующую волну.

## E2E проверка цепочки
- Bump версии в `pyproject.toml` и верхнем блоке `docs/release-notes.md`; синхронизировать `CHANGELOG.md`.
- Запушить в `main`, дождаться успешного Auto Tag (при ошибке — читать summary о причине пропуска).
- Дождаться workflow Release: проверить, что в GitHub Release появились wheel/tarball, payload zip, manifest и соответствующие checksum, а тело совпадает с верхним блоком.
- Поставить релиз на чистый каталог: `uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git@vX.Y.Z` (или `pipx install ...@vX.Y.Z`) и прогнать `scripts/smoke-workflow.sh`.

Храните заметки в одном файле (`docs/release-notes.md`), добавляя записи в обратном хронологическом порядке.

## vNext — YYYY-MM-DD

### Added
- `tools/migrate_ticket.py` — миграция существующих slug-ориентированных установок на ticket-first layout (`docs/.active_ticket`, обновлённый front-matter tasklist).
- Автосоздание PRD: `tools/set_active_feature.py` и `claude_workflow_cli.feature_ids` теперь сразу создают `docs/prd/<ticket>.prd.md` со статусом `Status: draft`, так что гейты видят артефакт до начала диалога.
- Двуязычные промпты: EN-варианты в `prompts/en/**`, линтер синхронизирует RU/EN, добавлены `docs/prompt-versioning.md`, `tools/prompt_diff.py`, `scripts/prompt-version`, а gate-workflow блокирует несогласованные обновления.
- Добавлен флаг `--prompt-locale en` для `init-claude-workflow.sh`/`claude-workflow init`, который устанавливает EN-вариант `.claude/agents|commands`, а в проект копируется каталог `prompts/en/**` для дальнейшей синхронизации.
- Agent-first шаблоны и команды: обновлены `docs/prd.template.md`, `docs/tasklist.template.md`, `docs/templates/research-summary.md`, `/idea-new`, `templates/prompt-agent.md` и `templates/prompt-command.md`, чтобы агенты фиксировали используемые команды/артефакты и задавали вопросы только после анализа репозитория. README/README.en, `workflow.md`, `docs/agents-playbook.md`, `docs/feature-cookbook.md`, `docs/customization.md` описывают новые правила.

### Changed
- Workflow, документация и шаблоны переведены на ticket-first модель: команды принимают `--ticket`, slug-hint стал опциональным алиасом, обновлены README, playbook-и, tasklist-шаблон и smoke-сценарий.
- `scripts/prd_review_gate.py` и `analyst-check` учитывают `Status: draft`: гейты блокируют PRD до тех пор, пока диалог не доведён до READY и PRD Review не утверждён; smoke и unit-тесты обновлены под новый сценарий.
- `scripts/ci-lint.sh` запускает `scripts/lint-prompts.py`, dry-run `scripts/prompt-version`, новые юнит-тесты (`tests/test_prompt_lint.py`, `tests/test_prompt_diff.py`, `tests/test_prompt_versioning.py`), а `scripts/smoke-workflow.sh` проверяет блокировку RU-only изменений промптов.
- Аналитик/исследователь/исполнитель работают в agent-first режиме: промпты требуют перечислять просмотренные файлы, команды (`rg`, `claude-workflow progress`, `./gradlew test`) и ссылки на логи; tasklist/research шаблоны и `/idea-new` CLI фиксируют baseline и списки команд по умолчанию.
- Внутренний backlog (`doc/backlog.md`) оставлен только для разработки и исключён из payload/manifest; sync/check скрипты игнорируют `doc/` по умолчанию.

### Migration
- Выполните `python3 tools/migrate_ticket.py` в корне проекта, чтобы создать `docs/.active_ticket` (если отсутствует) и дополнить `docs/tasklist/*.md` полями `Ticket` и `Slug hint`. После миграции повторите smoke-тест `scripts/smoke-workflow.sh`.
- Обновите payload/шаблоны: `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py`, затем скопируйте свежие `.claude/agents|commands` и `prompts/en/**`.
- Для активных тикетов перезапустите `claude-workflow research --ticket <ticket> --auto` и `claude-workflow analyst-check --ticket <ticket>`, чтобы PRD/research перешли на новые секции «Commands/Reports». При необходимости вручную перенесите новые блоки в существующие документы.
- Запустите `scripts/ci-lint.sh` и smoke-тесты, чтобы убедиться, что tasklist содержит поля `Reports/Commands`, а промпты не используют устаревшие инструкции `Answer N`.
