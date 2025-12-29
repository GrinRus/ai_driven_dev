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
> Repo-only: чеклист рассчитан на работу в репозитории; скрипты `scripts/*` и `tools/*` не входят в установленный payload.

- [ ] Обновить `README.md` и `README.en.md` (TL;DR, список фич, ссылки на новые документы).
- [ ] Проверить Wave backlog — закрыть выполненные пункты и создать Wave 2/3 для новых задач.
- [ ] Обновить демо (`examples/gradle-demo/`) и убедиться, что `examples/apply-demo.sh` отрабатывает без ошибок.
- [ ] Убедиться, что CI (`.github/workflows/ci.yml`) проходит на ветке `main`.
- [ ] Выполнить локальный прогон CI lint (см. `.github/workflows/ci.yml`).
- [ ] Синхронизировать RU/EN промпты: `./scripts/prompt-release.sh --part patch` (или `--dry-run`) — скрипт выполняет bump, lint, pytest и проверку payload/gate. При необходимости дополнительно запустите `python3 tools/prompt_diff.py --root <workflow-root> --kind agent --name <name>` точечно.
- [ ] Синхронизировать payload: `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py && pytest tests/test_init_hook_paths.py`. Только после этого публикуйте пакет/релиз.
- [ ] Проверить состав payload: `python3 tools/payload_audit.py`.
- [ ] Убедиться, что dev-only артефакты (например, `backlog.md` в корне) не попали в payload/manifest; каталог `doc/` исключён из sync по умолчанию.

## Migration: legacy root installs → `./aidd` (Wave 51)
- CLI и хуки больше не поддерживают произвольный `--target`; workflow всегда в `./aidd` относительно workspace.
- Для старых установок: удалите корневые снапшоты `.claude/`, `.claude-plugin/`, `config/`, `docs/`, `prompts/`, `scripts/`, `templates/`, `tools/`; запустите `claude-workflow init --target .` и перенесите активные маркеры (`.active_ticket/.active_feature`), PRD/plan/research/tasklist и отчёты в `aidd/docs` и `aidd/reports`.
- Проверьте гейты через `aidd/scripts/smoke-workflow.sh` или `claude-workflow smoke`. Подробнее — `aidd/docs/migration-aidd.md`.
- [ ] Зафиксировать изменения в `aidd/docs/release-notes.md`.

## Публикация релиза
- [ ] Проставить тег `vX.Y.Z` (annotated tag).
- [ ] Создать GitHub Release и вложить основные тезисы из release notes.
- [ ] Загрузить артефакты из `dist/`: wheel/tarball, `claude-workflow-payload-<tag>.zip`, `claude-workflow-manifest-<tag>.json` и соответствующие `.sha256`.
- [ ] Приложить ссылки на новые/обновлённые документы (usage/customization/command reference).
- [ ] Обновить `workflow.md` (и при необходимости `aidd/docs/customization.md`), если поведение установки изменилось.
- [ ] Сообщить в выбранных каналах (Slack, email, команда).

## Пост-релиз
- [ ] Создать задачу на планирование следующего релиза.
- [ ] Собрать обратную связь от пользователей (issues, комментарии).
- [ ] Проверить, что `.claude/settings.json` соответствует политике доступа.
- [ ] Обновить Wave backlog: перенести оставшиеся задачи в следующую волну.

Храните заметки в одном файле (`aidd/docs/release-notes.md`), добавляя записи в обратном хронологическом порядке.

## vNext — YYYY-MM-DD

### Added
- `tools/migrate_ticket.py` — миграция существующих slug-ориентированных установок на ticket-first layout (`aidd/docs/.active_ticket`, обновлённый front-matter tasklist).
- Автосоздание PRD: `tools/set_active_feature.py` и `claude_workflow_cli.feature_ids` теперь сразу создают `aidd/docs/prd/<ticket>.prd.md` со статусом `Status: draft`, так что гейты видят артефакт до начала диалога.
- Двуязычные промпты: EN-варианты в `aidd/prompts/en/**`, линтер синхронизирует RU/EN, добавлены `aidd/docs/prompt-versioning.md`, `tools/prompt_diff.py`, `scripts/prompt-version`, а gate-workflow блокирует несогласованные обновления.
- Добавлен флаг `--prompt-locale en` для `init-claude-workflow.sh`/`claude-workflow init`, который устанавливает EN-вариант `aidd/agents|commands`, а в проект копируется каталог `aidd/prompts/en/**` для дальнейшей синхронизации.
- Agent-first шаблоны и команды: обновлены `aidd/docs/prd.template.md`, `aidd/docs/tasklist.template.md`, `aidd/docs/templates/research-summary.md`, `/idea-new`, `templates/prompt-agent.md` и `templates/prompt-command.md`, чтобы агенты фиксировали используемые команды/артефакты и задавали вопросы только после анализа репозитория. README/README.en, `workflow.md`, `aidd/docs/agents-playbook.md`, `aidd/docs/feature-cookbook.md`, `aidd/docs/customization.md` описывают новые правила.

### Changed
- Workflow, документация и шаблоны переведены на ticket-first модель: команды принимают `--ticket`, slug-hint стал опциональным алиасом, обновлены README, playbook-и, tasklist-шаблон и smoke-сценарий.
- `scripts/prd_review_gate.py` и `analyst-check` учитывают `Status: draft`: гейты блокируют PRD до тех пор, пока диалог не доведён до READY и PRD Review не переведён в READY; smoke и unit-тесты обновлены под новый сценарий.
- Промпты команд/агентов унифицированы под `READY/BLOCKED/PENDING`, команды принимают свободные заметки после тикета, а `allowed-tools` синхронизирован с инструментами саб-агентов.
- Линтер промптов проверяет дубли ключей, запрещённые статусы, HTML-эскейпы `<ticket>`, некорректные формулировки `Checkbox updated` и несоответствие `allowed-tools` ↔ `tools`.
- EN промпты дополнительно синхронизированы с RU: пути отчётов указывают `${CLAUDE_PLUGIN_ROOT:-./aidd}`, `/review-prd` учитывает свободный ввод, tasklist‑ответственность закреплена за командами, линтер валидирует `Статус:`.
- Приведены к единому виду `@aidd/docs/.../<ticket>...` placeholder-и в RU промптах, EN `/implement` использует `${CLAUDE_PLUGIN_ROOT:-./aidd}` в инструкциях, тесты линтера покрывают `Статус:`.
- EN `/qa` теперь ссылается на `${CLAUDE_PLUGIN_ROOT:-./aidd}` в дефолтном пути тестов, а implementer получает доступ к хукe `format-and-test.sh` в инструментах.
- `tools/check_payload_sync.py` использует стандартный список путей payload и предупреждает, если runtime snapshot (`aidd/`) не развернут.
- CI lint запускает `scripts/lint-prompts.py`, dry-run `scripts/prompt-version`, новые юнит-тесты (`tests/test_prompt_lint.py`, `tests/test_prompt_diff.py`, `tests/test_prompt_versioning.py`), а `scripts/smoke-workflow.sh` проверяет блокировку RU-only изменений промптов.
- Аналитик/исследователь/исполнитель работают в agent-first режиме: промпты требуют перечислять просмотренные файлы, команды (`rg`, `claude-workflow progress`, `./gradlew test`) и ссылки на логи; tasklist/research шаблоны и `/idea-new` CLI фиксируют baseline и списки команд по умолчанию.
- Внутренний backlog (`backlog.md`) оставлен только для разработки и исключён из payload/manifest; sync/check скрипты игнорируют `doc/` по умолчанию.

### Migration
- Выполните `python3 tools/migrate_ticket.py` в корне проекта, чтобы создать `aidd/docs/.active_ticket` (если отсутствует) и дополнить `aidd/docs/tasklist/*.md` полями `Ticket` и `Slug hint`. После миграции повторите smoke-тест `scripts/smoke-workflow.sh`.
- Обновите payload/шаблоны: `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py`, затем скопируйте свежие `aidd/agents|commands` и `aidd/prompts/en/**`.
- Для активных тикетов перезапустите `claude-workflow research --ticket <ticket> --auto` и `claude-workflow analyst-check --ticket <ticket>`, чтобы PRD/research перешли на новые секции «Commands/Reports». При необходимости вручную перенесите новые блоки в существующие документы.
- Запустите smoke-тесты (`claude-workflow smoke`) и общий прогон CI lint, чтобы убедиться, что tasklist содержит поля `Reports/Commands`, а промпты не используют устаревшие инструкции `Answer N`.
