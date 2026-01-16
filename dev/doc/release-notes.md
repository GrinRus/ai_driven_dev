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
> Repo-only: чеклист рассчитан на работу в репозитории; утилиты `dev/repo_tools/*` не входят в установленный плагин.

- [ ] Обновить `README.md` и `README.en.md` (TL;DR, список фич, ссылки на новые документы).
- [ ] Проверить Wave backlog (`dev/doc/backlog.md`) — закрыть выполненные пункты и создать Wave 2/3 для новых задач.
- [ ] Убедиться, что CI (`dev/.github/workflows/ci.yml`) проходит на ветке `main`.
- [ ] Выполнить локальный прогон CI lint (см. `dev/.github/workflows/ci.yml`).
- [ ] Проверить промпты: `python3 dev/repo_tools/prompt-version bump --root <workflow-root> --prompts <name> --kind agent|command --lang ru --part patch --dry-run`, затем `python3 dev/repo_tools/lint-prompts.py --root <workflow-root>` и pytest промптов.
- [ ] Проверить `templates/aidd/` и идемпотентность `/aidd-init` (новые файлы появляются без перезаписи).
- [ ] Убедиться, что dev-only артефакты (например, `dev/doc/backlog.md`) не попали в дистрибутив.

## Migration: legacy root installs → `./aidd` (marketplace-only)
- Legacy CLI больше не используется; устанавливайте плагин через marketplace и запускайте `/aidd-init`.
- Для старых установок: удалите корневые снапшоты `.claude/`, `.claude-plugin/`, `config/`, `docs/`, `scripts`, `templates`, `tools`; перенесите активные маркеры (`.active_ticket/.active_feature`), PRD/plan/research/tasklist и отчёты в `aidd/docs` и `aidd/reports`.
- Проверьте гейты через `dev/repo_tools/smoke-workflow.sh`. Подробнее — `dev/doc/migration-aidd.md`.
- [ ] Зафиксировать изменения в `dev/doc/release-notes.md`.

## Публикация релиза
- [ ] Проставить тег `vX.Y.Z` (annotated tag).
- [ ] Создать GitHub Release и вложить основные тезисы из release notes.
- [ ] Загрузить артефакты из `dist/` (wheel/tarball) при публикации Python-пакета.
- [ ] Приложить ссылки на новые/обновлённые документы (usage/customization/command reference).
- [ ] Обновить `dev/doc/workflow.md` (и при необходимости `dev/doc/customization.md`), если поведение установки изменилось.
- [ ] Сообщить в выбранных каналах (Slack, email, команда).

## Пост-релиз
- [ ] Создать задачу на планирование следующего релиза.
- [ ] Собрать обратную связь от пользователей (issues, комментарии).
- [ ] Проверить, что `.claude/settings.json` соответствует политике доступа.
- [ ] Обновить Wave backlog: перенести оставшиеся задачи в следующую волну.

Храните заметки в одном файле (`dev/doc/release-notes.md`), добавляя записи в обратном хронологическом порядке.

## vNext — YYYY-MM-DD

### Added
- Профили тестов `FAST/TARGETED/FULL/NONE` через `aidd/.cache/test-policy.env` и переменные `AIDD_TEST_*`.
- Дедуп тестов: кэш `aidd/.cache/format-and-test.last.json` для пропуска повторов без изменений.
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli research-check` — отдельная проверка research перед `/plan-new`.
- `## AIDD:RESEARCH_HINTS` в PRD-шаблоне для передачи путей/ключевых слов в `/researcher`.
- Новый этап review-plan с агентом `plan-reviewer`, секцией `## Plan Review` в плане и гейтом `plan_review`.
- Команда `/review-spec`, объединяющая review-plan и review-prd в один шаг.
- Документы `aidd/docs/sdlc-flow.md` и `aidd/docs/status-machine.md` как единый контракт стадий/статусов.
- `aidd/AGENTS.md` как основной вход для агентного контекста.
- Шаблон плана `aidd/docs/plan/template.md` с обязательными секциями и блоком Plan Review.
- Автосоздание PRD: `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli set-active-feature` и `aidd_runtime.feature_ids` теперь сразу создают `aidd/docs/prd/<ticket>.prd.md` со статусом `Status: draft`, так что гейты видят артефакт до начала диалога.
- Agent-first шаблоны и команды: обновлены `aidd/docs/prd/template.md`, `aidd/docs/tasklist/template.md`, `aidd/docs/research/template.md`, `/idea-new`, `dev/doc/templates/prompts/prompt-agent.md` и `dev/doc/templates/prompts/prompt-command.md`, чтобы агенты фиксировали используемые команды/артефакты и задавали вопросы только после анализа репозитория. README/README.en, `dev/doc/workflow.md`, `dev/doc/agents-playbook.md`, `dev/doc/feature-cookbook.md`, `dev/doc/customization.md` описывают новые правила.
- Каталог `aidd/reports/prd` разворачивается при `/aidd-init` (через `.gitkeep`), ручной `mkdir` больше не нужен.

### Changed
- `/implement` и `implementer` теперь фиксируют test policy, лимит итерации и тест-бюджет, ожидаемый вывод включает `Test profile`/`Tests run`.
- `${CLAUDE_PLUGIN_ROOT:-.}/hooks/format-and-test.sh` выбирает задачи через профили (`fastTasks/fullTasks/targetedTask`) и уважает `AIDD_TEST_FORCE` при повторных прогонах.
- `/idea-new` больше не запускает research; аналитик фиксирует подсказки, а `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli research` выполняется на стадии `/researcher`.
- `analyst-check` больше не валидирует research; проверка вынесена в `research-check` и `gate-workflow`.
- `/plan-new` вызывает `research-check` перед запуском planner.
- Канонический SDLC обновлён: `idea → research → plan → review-plan → review-prd → tasklist → implement → review → qa` (для ревью доступен `/review-spec`).
- Команды стали “тонкими”, а агенты содержат алгоритмы и stop-conditions; формат вопросов стандартизирован (`Вопрос N (Blocker|Clarification)` + `Зачем/Варианты/Default`).
- Output-контракт унифицирован (`Checkbox updated` + `Status` + `Artifacts updated` + `Next actions`), поиск стандартизирован на `rg`.
- Шаблоны research/tasklist/QA обновлены: Context Pack и Definition of reviewed, секции `AIDD:NEXT_3` и `AIDD:HANDOFF_INBOX`, traceability к AIDD:ACCEPTANCE.
- `gate-workflow` теперь проверяет `review-plan` перед PRD review и tasklist; для удобства есть `/review-spec`, smoke/тесты синхронизированы с новым порядком.
- Workflow, документация и шаблоны переведены на ticket-first модель: команды принимают `--ticket`, slug-hint стал опциональным алиасом, обновлены README, playbook-и, tasklist-шаблон и smoke-сценарий.
- `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli prd-review-gate` и `analyst-check` учитывают `Status: draft`: гейты блокируют PRD до тех пор, пока диалог не доведён до READY и PRD Review не переведён в READY; smoke и unit-тесты обновлены под новый сценарий.
- Промпты команд/агентов унифицированы под `READY/BLOCKED/PENDING`, команды принимают свободные заметки после тикета, а `allowed-tools` синхронизирован с инструментами саб-агентов.
- Линтер промптов проверяет дубли ключей, запрещённые статусы, HTML-эскейпы `<ticket>`, некорректные формулировки `Checkbox updated` и несоответствие `allowed-tools` ↔ `tools`.
- Проверки CI используют `dev/repo_tools/ci-lint.sh` и `dev/repo_tools/smoke-workflow.sh` для контроля целостности.
- CI lint запускает `dev/repo_tools/lint-prompts.py`, dry-run `dev/repo_tools/prompt-version`, юнит-тесты (`dev/tests/test_prompt_lint.py`, `dev/tests/test_prompt_versioning.py`), а `dev/repo_tools/smoke-workflow.sh` проверяет блокировку RU-only изменений промптов.
- Аналитик/исследователь/исполнитель работают в agent-first режиме: промпты требуют перечислять просмотренные файлы, команды (`rg`, `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli progress`, `<test-runner>`) и ссылки на логи; tasklist/research шаблоны и `/idea-new` CLI фиксируют baseline и списки команд по умолчанию.
- Внутренний backlog (`dev/doc/backlog.md`) оставлен только для разработки и исключён из дистрибутива.

### Migration
- Если у вас есть legacy `tasklist.md`, перенесите его вручную в `aidd/docs/tasklist/<ticket>.md` и добавьте front-matter (`Ticket`, `Slug hint`, `Feature`, `Status`, `PRD`, `Plan`, `Research`, `Updated`).
- Обновите шаблоны: сравните `templates/aidd` с `aidd` и перенесите новые секции в рабочие артефакты.
- Для активных тикетов перезапустите `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli research --ticket <ticket> --auto` и `PYTHONPATH=${CLAUDE_PLUGIN_ROOT:-.} python3 -m aidd_runtime.cli analyst-check --ticket <ticket>`, чтобы PRD/research перешли на новые секции «Commands/Reports». При необходимости вручную перенесите новые блоки в существующие документы.
- Запустите smoke-тесты (`dev/repo_tools/smoke-workflow.sh`) и общий прогон CI lint, чтобы убедиться, что tasklist содержит поля `Reports/Commands`, а промпты не используют устаревшие инструкции `Answer N`.
