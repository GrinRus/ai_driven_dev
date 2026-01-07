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
- [ ] Обновить демо (`examples/`) и убедиться, что `examples/apply-demo.sh` отрабатывает без ошибок.
- [ ] Убедиться, что CI (`.github/workflows/ci.yml`) проходит на ветке `main`.
- [ ] Выполнить локальный прогон CI lint (см. `.github/workflows/ci.yml`).
- [ ] Проверить промпты: `python3 scripts/prompt-version bump --root <workflow-root> --prompts <name> --kind agent|command --lang ru --part patch --dry-run`, затем `python3 scripts/lint-prompts.py --root <workflow-root>` и pytest промптов.
- [ ] Синхронизировать payload: `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py && pytest tests/test_init_hook_paths.py`. Только после этого публикуйте пакет/релиз.
- [ ] Проверить состав payload: `python3 tools/payload_audit.py`.
- [ ] Убедиться, что dev-only артефакты (например, `backlog.md` в корне) не попали в payload/manifest; каталог `doc/` исключён из sync по умолчанию.

## Migration: legacy root installs → `./aidd` (Wave 51)
- CLI и хуки больше не поддерживают произвольный `--target`; workflow всегда в `./aidd` относительно workspace.
- Для старых установок: удалите корневые снапшоты `.claude/`, `.claude-plugin/`, `config/`, `docs/`, `scripts/`, `templates/`, `tools/`; запустите `claude-workflow init --target .` и перенесите активные маркеры (`.active_ticket/.active_feature`), PRD/plan/research/tasklist и отчёты в `aidd/docs` и `aidd/reports`.
- Проверьте гейты через `scripts/smoke-workflow.sh` или `claude-workflow smoke`. Подробнее — `doc/dev/migration-aidd.md`.
- [ ] Зафиксировать изменения в `doc/dev/release-notes.md`.

## Публикация релиза
- [ ] Проставить тег `vX.Y.Z` (annotated tag).
- [ ] Создать GitHub Release и вложить основные тезисы из release notes.
- [ ] Загрузить артефакты из `dist/`: wheel/tarball, `claude-workflow-payload-<tag>.zip`, `claude-workflow-manifest-<tag>.json` и соответствующие `.sha256`.
- [ ] Приложить ссылки на новые/обновлённые документы (usage/customization/command reference).
- [ ] Обновить `doc/dev/workflow.md` (и при необходимости `doc/dev/customization.md`), если поведение установки изменилось.
- [ ] Сообщить в выбранных каналах (Slack, email, команда).

## Пост-релиз
- [ ] Создать задачу на планирование следующего релиза.
- [ ] Собрать обратную связь от пользователей (issues, комментарии).
- [ ] Проверить, что `.claude/settings.json` соответствует политике доступа.
- [ ] Обновить Wave backlog: перенести оставшиеся задачи в следующую волну.

Храните заметки в одном файле (`doc/dev/release-notes.md`), добавляя записи в обратном хронологическом порядке.

## vNext — YYYY-MM-DD

### Added
- Профили тестов `FAST/TARGETED/FULL/NONE` через `aidd/.cache/test-policy.env` и переменные `AIDD_TEST_*`.
- Дедуп тестов: кэш `aidd/.cache/format-and-test.last.json` для пропуска повторов без изменений.
- `claude-workflow research-check` — отдельная проверка research перед `/plan-new`.
- `## Research Hints` в PRD-шаблоне для передачи путей/ключевых слов в `/researcher`.
- Новый этап review-plan с агентом `plan-reviewer`, секцией `## Plan Review` в плане и гейтом `plan_review`.
- Команда `/review-spec`, объединяющая review-plan и review-prd в один шаг.
- Документы `aidd/docs/sdlc-flow.md` и `aidd/docs/status-machine.md` как единый контракт стадий/статусов.
- `aidd/AGENTS.md` как основной вход для агентного контекста.
- Шаблон плана `aidd/docs/plan/template.md` с обязательными секциями и блоком Plan Review.
- Автосоздание PRD: `claude-workflow set-active-feature` и `claude_workflow_cli.feature_ids` теперь сразу создают `aidd/docs/prd/<ticket>.prd.md` со статусом `Status: draft`, так что гейты видят артефакт до начала диалога.
- Agent-first шаблоны и команды: обновлены `aidd/docs/prd/template.md`, `aidd/docs/tasklist/template.md`, `aidd/docs/research/template.md`, `/idea-new`, `doc/dev/templates/prompts/prompt-agent.md` и `doc/dev/templates/prompts/prompt-command.md`, чтобы агенты фиксировали используемые команды/артефакты и задавали вопросы только после анализа репозитория. README/README.en, `doc/dev/workflow.md`, `doc/dev/agents-playbook.md`, `doc/dev/feature-cookbook.md`, `doc/dev/customization.md` описывают новые правила.
- Каталог `reports/prd` разворачивается при `claude-workflow init` (payload содержит `.gitkeep`), ручной `mkdir` больше не нужен.

### Changed
- `/implement` и `implementer` теперь фиксируют test policy, лимит итерации и тест-бюджет, ожидаемый вывод включает `Test profile`/`Tests run`.
- `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh` выбирает задачи через профили (`fastTasks/fullTasks/targetedTask`) и уважает `AIDD_TEST_FORCE` при повторных прогонах.
- `/idea-new` больше не запускает research; аналитик фиксирует подсказки, а `claude-workflow research` выполняется на стадии `/researcher`.
- `analyst-check` больше не валидирует research; проверка вынесена в `research-check` и `gate-workflow`.
- `/plan-new` вызывает `research-check` перед запуском planner.
- Канонический SDLC обновлён: `idea → research → plan → review-plan → review-prd → tasklist → implement → review → qa` (для ревью доступен `/review-spec`).
- Команды стали “тонкими”, а агенты содержат алгоритмы и stop-conditions; формат вопросов стандартизирован (`Вопрос N (Blocker|Clarification)` + `Зачем/Варианты/Default`).
- Output-контракт унифицирован (`Checkbox updated` + `Status` + `Artifacts updated` + `Next actions`), поиск стандартизирован на `rg`.
- Шаблоны research/tasklist/QA обновлены: Context Pack и Definition of reviewed, секции `Next 3` и `Handoff inbox`, traceability к acceptance criteria.
- `gate-workflow` теперь проверяет `review-plan` перед PRD review и tasklist; для удобства есть `/review-spec`, smoke/тесты синхронизированы с новым порядком.
- Workflow, документация и шаблоны переведены на ticket-first модель: команды принимают `--ticket`, slug-hint стал опциональным алиасом, обновлены README, playbook-и, tasklist-шаблон и smoke-сценарий.
- `claude-workflow prd-review-gate` и `analyst-check` учитывают `Status: draft`: гейты блокируют PRD до тех пор, пока диалог не доведён до READY и PRD Review не переведён в READY; smoke и unit-тесты обновлены под новый сценарий.
- Промпты команд/агентов унифицированы под `READY/BLOCKED/PENDING`, команды принимают свободные заметки после тикета, а `allowed-tools` синхронизирован с инструментами саб-агентов.
- Линтер промптов проверяет дубли ключей, запрещённые статусы, HTML-эскейпы `<ticket>`, некорректные формулировки `Checkbox updated` и несоответствие `allowed-tools` ↔ `tools`.
- `tools/check_payload_sync.py` использует стандартный список путей payload и предупреждает, если runtime snapshot (`aidd/`) не развернут.
- CI lint запускает `scripts/lint-prompts.py`, dry-run `scripts/prompt-version`, юнит-тесты (`tests/test_prompt_lint.py`, `tests/test_prompt_versioning.py`), а `scripts/smoke-workflow.sh` проверяет блокировку RU-only изменений промптов.
- Аналитик/исследователь/исполнитель работают в agent-first режиме: промпты требуют перечислять просмотренные файлы, команды (`rg`, `claude-workflow progress`, `<test-runner>`) и ссылки на логи; tasklist/research шаблоны и `/idea-new` CLI фиксируют baseline и списки команд по умолчанию.
- Внутренний backlog (`backlog.md`) оставлен только для разработки и исключён из payload/manifest; sync/check скрипты игнорируют `doc/` по умолчанию.

### Migration
- Если у вас есть legacy `tasklist.md`, перенесите его вручную в `aidd/docs/tasklist/<ticket>.md` и добавьте front-matter (`Ticket`, `Slug hint`, `Feature`, `Status`, `PRD`, `Plan`, `Research`, `Updated`).
- Обновите payload/шаблоны: `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py`, затем скопируйте свежие `aidd/agents|commands`.
- Для активных тикетов перезапустите `claude-workflow research --ticket <ticket> --auto` и `claude-workflow analyst-check --ticket <ticket>`, чтобы PRD/research перешли на новые секции «Commands/Reports». При необходимости вручную перенесите новые блоки в существующие документы.
- Запустите smoke-тесты (`claude-workflow smoke`) и общий прогон CI lint, чтобы убедиться, что tasklist содержит поля `Reports/Commands`, а промпты не используют устаревшие инструкции `Answer N`.
