# Product Backlog

## Wave 1

### Документация и коммуникация
- [x] `README.md`: добавить краткое TL;DR, оглавление и визуально разбить разделы, вынести дополнительные детали в отдельные ссылки внутри `/doc`.
- [x] `README.md`: подготовить англоязычную версию (двуязычный формат или отдельный файл), описать процедуру синхронизации с основным текстом.
- [x] `AGENTS.md`: создать пошаговый пример запуска `init-claude-workflow.sh` на демо‑проекте, включить скриншоты/структуру «до и после», обновить ссылки в README.
- [x] `AGENTS.md`: описать настройку `.claude/settings.json`, `config/conventions.json`, хуков и команд, добавить примеры override для разных команд.
- [x] `LICENSE` и `CONTRIBUTING.md`: добавить базовую лицензию, правила приёма вкладов, список каналов связи и шаблоны issue/PR.

### Скрипты и шаблоны
- [x] `init-claude-workflow.sh`: разбить логику на функции, добавить проверки зависимостей (bash, python3, gradle/ktlint), флаг `--dry-run`, единый логгер и детальные сообщения об ошибках.
- [x] `init-claude-workflow.sh`: реализовать smoke‑тесты (например, через `bats` или `pytest + subprocess`) для сценариев «первая установка», `--force`, повторный запуск без изменений и проверка прав доступа.
- [x] Демо‑проект: подготовить минимальный Gradle‑монорепо и скрипт `examples/apply-demo.sh`, демонстрирующий автоматическую интеграцию workflow.
- [x] `commands/*.md`: расширить описание слэш‑команд примерами входных данных и ожидаемого результата, добавить hints по типовым ошибкам.
- [x] `docs/tasklist/template.md`: дополнить расширенными чеклистами (QA, релиз, документация) и ссылками на связанные артефакты ADR/PRD.

### Качество и процесс
- [x] `.github/workflows/ci.yml`: настроить CI, запускающий shellcheck, линтеры и тесты скрипта на каждом PR.
- [x] `tests/repo_tools/ci-lint.sh`: собрать единый entrypoint для локального и CI‑прогонов (shellcheck, markdownlint, yamllint).
- [x] `AGENTS.md`: зафиксировать процесс версионирования, формат релизов и чеклист публикации (теги, обновление README и демо).
- [x] `.claude/settings.json`: описать в документации политику доступа к инструментам и добавить автопроверку, что настройки не нарушены (pre-commit или тест).

## Wave 2

### Шаблоны документации
- [x] `docs/prd/template.md`: добавить разделы «Метрики успеха» и «Связанные ADR», примеры заполнения и чеклист для ревью.
- [x] `docs/adr/template.md`: включить блок «Импакт на систему», стандартные критерии принятия и ссылку на соответствующие PRD/таски.
- [x] `docs/tasklist/template.md`: различать этапы (аналитика, разработка, QA, релиз) и предусмотреть ссылку на релизные заметки.

### Шаблоны команд и хуков
- [x] `commands/*.md`: унифицировать формат (описание, входные параметры, побочные эффекты, примеры), добавить quick-reference таблицу.
- [x] `.claude/hooks/format-and-test.sh`: вынести конфигурацию формата/тестов в `.claude/settings.json` или отдельный yaml, добавить переменные окружения для тонкой настройки.

### Настраиваемые файлы
- [x] `config/conventions.json`: описать все поддерживаемые режимы и поля с пояснениями, добавить пример для смешанных команд.
- [x] `.claude/settings.json`: подготовить «стартовый» и «строгий» пресеты, объяснить, как переключаться между ними.
- [x] `AGENTS.md`: собрать каталог примерных Git-хуков (commit-msg, pre-push, prepare-commit-msg) с инструкцией по установке.

## Wave 3

### Многошаговый Claude-процесс
- [x] `init-claude-workflow.sh` / `init-claude-workflow.min.sh`: обновить генерацию каркаса под новый цикл «идея → план → валидация → задачи → реализация → ревью» (агенты analyst/planner/validator/implementer/reviewer, команды `/feature-dev-aidd:idea-new`, `/feature-dev-aidd:plan-new`, `/feature-dev-aidd:tasks-new`, `/feature-dev-aidd:implement`, `/feature-dev-aidd:review`, хук `gate-workflow.sh`, `docs/plan/.gitkeep`).
- [x] Документация и скрипты: убрать упоминания `init-claude-workflow.min.sh`, если мини-версия больше не распространяется, или заменить на актуальный способ доставки (релизный архив/однострочник).
- [x] `tests/repo_tools/smoke-workflow.sh`: добавить сценарий, который последовательно вызывает новые команды на демо-фиче, проверяет создание PRD/плана/тасклиста и что хук блокирует правки кода до готовности артефактов.
- [x] `.claude/settings.json`: автоматизировать включение разрешений `SlashCommand:/test-changed:*`, новых гейтов (`gate-tests.sh`) и `gate-workflow.sh` через presets, чтобы пользователь мог переключать режимы без ручного редактирования.
- [x] `init-claude-workflow.sh`: добавить генерацию `config/gates.json`, allowlist зависимостей, новых саб-агентов и команд (`/api-spec-new`, `/tests-generate`), чтобы базовая установка включала весь расширенный флоу.

### Автоматические проверки и выборочные тесты
- [x] `.claude/hooks/gate-workflow.sh`: покрыть unit-/интеграционными тестами (через `bats` или `pytest`) сценарии: нет активной фичи, отсутствует PRD/план/тасклисты, разрешение правок в документации, блокировка `src/**`.
- [x] Новые гейты (`gate-tests.sh`): добавить тесты на позитивные и негативные сценарии (feature ticket отсутствует, тест найден/отсутствует, исправление документации и т.д.).
- [x] `.claude/hooks/format-and-test.sh`: удостовериться, что при наличии активной фичи и изменениях в общих файлах запускается полный набор тестов; добавить логирование затронутых модулей в артефакты команд.
- [x] `/feature-dev-aidd:implement`: реализовать автоматический перезапуск `/test-changed` после успешных правок (через embedded slash-команду) и добавить fallback-настройку для отключения автозапуска (env `SKIP_AUTO_TESTS`).

### Документация и практики команды
- [x] `AGENTS.md`: подробно описать новый цикл, роли агентов, формат вопросов/ответов с пользователем, обязанности перед каждым гейтом, включая новые проверки контрактов/миграций/тестов.
- [x] `README.md` / `README.en.md`: обновить обзор команд с учётом `/api-spec-new`, `/tests-generate`, описать назначение новых саб-агентов и барьеров.
- [x] `docs/tasklist/template.md`: дополнить секцией «Интеграция с автогейтами» с чекбоксами READY/BLOCKED, отсылкой к `docs/.active_feature` (обновляется через `/feature-dev-aidd:idea-new`) и указанием, какие артефакты нужны для прохождения контракт/миграция/тест-гейтов.
- [x] `AGENTS.md`: добавить раздел «Как включить/отключить гейты и автотесты», описать `config/gates.json`, allowlist зависимостей и варианты кастомизации для проектов без Gradle и monorepo.
- [x] `AGENTS.md`: обновить сценарий, чтобы продемонстрировать работу новых команд и барьеров (создание API контракта, добавление миграции, автогенерацию тестов).

## Wave 4

### Playbook агентов и барьеров
- [x]: описать последовательность работы всех агентов (analyst → planner → validator → implementer → reviewer → api-designer → qa-author), список их команд и ожидаемые входы/выходы.
- [x]: документировать взаимодействие с барьерами (`gate-workflow`, `gate-tests`, `lint-deps`), условия срабатывания, способы обхода и troubleshooting.
- [x] README / onboarding: добавить ссылку на playbook и краткий чеклист запуска фичи, чтобы новая команда понимала полный цикл действий и проверки.

## Wave 5

### Консистентность артефактов и команд
- [x] `scripts/{branch_new.py,commit_msg.py,conventions_set.py}`: вернуть скрипты в репозиторий, синхронизировать их генерацию с `init-claude-workflow.sh` и описать использование в `AGENTS.md`; добавить unittest, который проверяет наличие CLI-утилит после установки. _(устарело, отменено в Wave 9)_
- [x] `.claude/gradle/init-print-projects.gradle`: добавить файл в исходники, включить его копирование инсталлятором и обновить раздел про selective tests в `README.md`/`README.en.md`; дополнить smoke-сценарий проверкой, что карта модулей создаётся.
- [x] `docs/intro.md`: в репозитории отсутствует обзорный документ; определить замену для устаревшей `/docs-generate`, согласовать формат с README и зафиксировать способ поддержания синхронизации.

### Документация и коммуникация
- [x] `README.md` / `README.en.md`: синхронизировать структуры разделов, обновить блок «Незакрытые задачи», привести отметку _Last sync_ к фактической дате и добавить явный чеклист перевода в `CONTRIBUTING.md`/CI.
- [x] `AGENTS.md` / `AGENTS.md`: обновить walkthrough и разделы настройки с учётом новой обзорной документации и сценария синхронизации README.

### CI и тестовый контур
- [x] `init-claude-workflow.sh`: устранить рассинхрон с текущим `.github/workflows/ci.yml` (сейчас генерируется `.github/workflows/gradle.yml`); выбрать единый pipeline и описать его в README и релиз-нотах.
- [x] `tests/test_init_aidd.py`: дополнить проверками на наличие overview-документа, helper-скриптов и актуального CI-файла; добавить негативные сценарии (например, отсутствие AGENTS.md) и очистку временных артефактов.

## Wave 7

### Claude Code feature presets
- [x] `docs/design/feature-presets.md`: описать архитектуру YAML-пресетов на все стадии фичи (PRD, дизайн, тасклист, реализация, релиз), определить обязательные поля (`workflow_step`, `context`, `output`) и схему интеграции с `AGENTS.md`.
- [x] `claude-presets/feature-*.yaml`: создать набор манифестов (`feature-prd`, `feature-design`, `feature-plan`, `feature-impl`, `feature-release`) с плейсхолдерами для `{{feature}}`, `{{acceptance_criteria}}` и ссылками на актуальные артефакты.
- [x] `init-claude-workflow.sh`: добавить установку каталога пресетов, CLI-флаг `--preset <name>` и автоматическое заполнение шаблонов из `backlog.md`/`AGENTS.md`.
- [x] `commands/`: расширить описание `/feature-dev-aidd:idea-new`, `/feature-dev-aidd:plan-new`, `/feature-dev-aidd:tasks-new`, `/feature-dev-aidd:implement`, `/feature-dev-aidd:review` инструкциями по запуску соответствующих пресетов и обновить quick-reference таблицу.
- [x] `tests/repo_tools/smoke-workflow.sh`: включить сценарий end-to-end, который прогоняет пресеты по демо-фиче и проверяет генерацию PRD/ADR/tasklist.
- [x] `AGENTS.md`: обновить walkthrough с разделом «Работа с пресетами» и чеклистом интеграции для новых команд.

## Wave 8

### Чистка устаревших команд и документации
- [x] `commands/{feature-new.md,feature-adr.md,feature-tasks.md,docs-generate.md}`: удалить, синхронизировать quick-reference и init-скрипт под флоу `/feature-dev-aidd:idea-new → /feature-dev-aidd:plan-new → /feature-dev-aidd:tasks-new → /feature-dev-aidd:implement → /feature-dev-aidd:review`.
- [x] `README.md` / `README.en.md`: обновить чеклисты и примеры запуска фичи, оставить только актуальные команды (`/feature-dev-aidd:idea-new`, `/feature-dev-aidd:plan-new`, `/feature-dev-aidd:tasks-new`, `/feature-dev-aidd:implement`, `/feature-dev-aidd:review`).
- [x] `AGENTS.md`: переписать walkthrough под новый цикл, добавить шаги `/feature-dev-aidd:idea-new → /feature-dev-aidd:plan-new → /feature-dev-aidd:tasks-new` и детальные проверки гейтов (workflow/API/DB/tests).

### Контроль использования CLI-утилит
- [x] `backlog.md` / `tests/`: закрепить решение — Python-утилиты (`scripts/branch_new.py`, `scripts/commit_msg.py`, `scripts/conventions_set.py`) входят в репозиторий, командные файлы опираются на них; описать в README и убедиться, что init-скрипт и тесты поддерживают сценарий. _(устарело, отменено в Wave 9)_

## Wave 9

### Оптимизация core workflow
- [x] `commands/idea-new.md`: оставить единственным источником установки `docs/.active_feature`, обновить инструкцию и гайды, чтобы исключить отдельный шаг `/feature-activate`.
- [x] `commands/feature-activate.md`: удалить или переместить в архив, зафиксировать решение в `README.md` и `AGENTS.md`.
- [x] `commands/branch-new.md` / `scripts/branch_new.py`: исключить обёртку над `git checkout -b`, обновить bootstrap (`init-claude-workflow.sh`) и документацию, чтобы допускалось ручное создание веток.
- [x] `commands/commit.md`, `commands/commit-validate.md`, `commands/conventions-set.md`, `commands/conventions-sync.md`: убрать из основного набора команд, поскольку они дублируют стандартные git-инструменты и не задействованы в процессе `idea → review`.
- [x] `init-claude-workflow.sh`: перестать генерировать удаляемые команды/скрипты (`feature-activate`, `branch-new`, `commit*`, `conventions*`) и их документацию.

### Чистка сопровождающего кода
- [x] `scripts/commit_msg.py`, `scripts/conventions_set.py`: удалить после декомиссии команд; обновить `config/conventions.json` и документацию, описав переход на нативные git-флоу.
- [x] `README.md`, `README.en.md`, `AGENTS.md`,: пересобрать разделы «Быстрый старт», «Слэш-команды», чеклист, убрав ссылки на исключённые команды и подчёркивая основной цикл `/feature-dev-aidd:idea-new → /feature-dev-aidd:plan-new → /feature-dev-aidd:tasks-new → /feature-dev-aidd:implement → /feature-dev-aidd:review`.
- [x] Тесты и хуки: убедиться, что `.claude/hooks/*` и `tests/` не ссылаются на удалённые команды; скорректировать smoke-сценарии (`tests/repo_tools/smoke-workflow.sh`) и демо (`AGENTS.md`, `examples/apply-demo.sh`).

## Wave 10

### Чистка лишних слэш-команд
- [x] `commands/api-spec-new.md`: убрать из шаблона, удалить привязку к /api-spec-new во всех гидах (`README.md`, `README.en.md`, `AGENTS.md`) и из чеклистов.
- [x] `commands/tests-generate.md`: удалить команду и ссылки; описать, как покрывать тестами в рамках `/feature-dev-aidd:implement` или прямого вызова агента.
- [x] `commands/test-changed.md`: исключить документацию команды, скорректировать упоминания в руководствах, разъяснив, что `.claude/hooks/format-and-test.sh` запускается автоматически.

### Сопровождающий код и настройки
- [x] `.claude/agents/api-designer.md`, `.claude/agents/qa-author.md`: перенести в раздел «advanced» или удалить после отказа от связанных команд; обновить.
- [x] `.claude/hooks/gate-tests.sh`: пересмотреть дефолтное поведение; убираем жёсткую зависимость от удалённых команд и переписываем сообщения об ошибках.
- [x] `config/gates.json`: обновить значения и документацию — описать способ включения расширенного режима и параметры `tests_required`.
- [x] `.claude/settings.json`: очистить разрешения `SlashCommand:/api-spec-new`, `/tests-generate`, `/test-changed`, убедиться, что автохуки продолжают работать без дополнительных команд.

### Документация, пресеты и тесты
- [x] `README.md`, `README.en.md`, `AGENTS.md`: сфокусировать описание флоу на `/feature-dev-aidd:idea-new → /feature-dev-aidd:plan-new → /feature-dev-aidd:tasks-new → /feature-dev-aidd:implement → /feature-dev-aidd:review`, убрать секции про необязательные артефакты.
- [x], `AGENTS.md`, `AGENTS.md`: переписать сценарии, заменив вызовы `/api-spec-new` и `/tests-generate` на прямое использование агентов или ручные шаги.
- [x] `claude-presets/feature-*.yaml`: пересмотреть wave-пресеты, убрав обязательные шаги дизайна/API/релиза либо вынеся их в отдельный пакет «advanced».
- [x] `tests/repo_tools/smoke-workflow.sh`: упростить smoke-тест — проверять только базовый цикл и исключить требования к пресетам `feature-design/feature-release`.
- [x] `docs/api/`, `docs/test/`: очистить или перенести каталоги во вспомогательный пакет, если они не задействованы после чистки.

## Wave 11

### Доочистка наследия `/test-changed`
- [x] `commands/implement.md`: переписать шаги реализации так, чтобы описывать автозапуск `.claude/hooks/format-and-test.sh`, режимы `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, без требований ручного вызова `/test-changed`.
- [x], `AGENTS.md`: добавить явное пояснение, как работает авто запуск тестов после записи и как временно отключить/расширить его без использования устаревшей команды.

## Wave 13

### CLI-дистрибуция через `uv`
- [x] Подготовить Python-пакет `claude-workflow-cli`: добавить `pyproject.toml`, каркас `src/claude_workflow_cli/` и entrypoint `claude-workflow`, повторяющий функциональность `init-claude-workflow.sh` (копирование шаблонов, пресеты, smoke).
- [x] Перенести необходимые шаблоны и конфиги в пакетные ресурсы (`templates/`, `claude-presets/`, `.claude/**`, `config/**`, `docs/*.template.md`) и настроить их выдачу через `importlib.resources`; предусмотреть проверку зависимостей и режим `--force`.
- [x] Реализовать команды CLI: `init`, `preset`, `smoke`; обеспечить совместимость с текущим bash-скриптом (вызов из Python либо thin-wrapper) и покрыть ключевую логику тестами.
- [x] Обновить документацию (`README.md`, `README.en.md`, `AGENTS.md`) — описать установку через `uv tool install claude-workflow-cli --from git+https://github.com/<org>/ai_driven_dev.git` и замену `curl | bash`; дополнить разделы о требованиях и обновлениях.
- [x] Добавить инструкцию для пользователей без `uv` (например, `pipx install git+...`) и секцию troubleshooting; проверить установку на чистой среде и зафиксировать сценарий в `tests/repo_tools/smoke-workflow.sh`.

## Wave 14

_Статус: активный, приоритет 1. Цель — предсказуемые релизы CLI/payload._

### Автоматизация релизов CLI
- [x] `.github/workflows/release.yml`: триггер на теги `v*`; шаги — `uv build`/`python -m build`, публикация wheel+sdist в GitHub Release через `softprops/action-gh-release`, загрузка payload zip и manifest checksum; складывать артефакты и в CI. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Автотегирование: job на `push` в `main`, читает версию из `pyproject.toml`, сверяет с последним релизом и создаёт аннотированный тег (через `actions/create-release` или `git tag`+`gh`), с защитой от повторов и уведомлением при сбое. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Документация (`README.md`, `README.en.md`, `AGENTS.md`): описать цепочку build → release → установка через `uv`/`pipx`, переменные/токены, troubleshooting для неудачных релизов. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] `CHANGELOG.md` / `AGENTS.md`: добавить шаблон/секцию, которую release workflow подтягивает автоматически (последний раздел или Release Drafter); зафиксировать порядок обновления changelog перед тегом. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] E2E проверка: прогнать сценарий bump версии → push → автотег → CI build → GitHub Release; задокументировать результат и обновить smoke/CI инструкции. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)

## Wave 15

### Исправление дистрибутива CLI через uv/pipx
- [x] Добавить `MANIFEST.in` (или явный список в `pyproject.toml`), чтобы в пакет попадали скрытые файлы `.claude/settings.json`, `.claude/hooks/lib.sh` и остальные dot-каталоги payload (`recursive-include src/claude_workflow_cli/data/payload.claude/*`).
- [x] Написать регресcионный тест/скрипт, который собирает wheel и проверяет наличие `.claude/**` в архиве (например, `tests/test_package_payload.py`).
- [x] Исправить обработку ошибок в `src/claude_workflow_cli/cli.py`: убрать ручное создание `CalledProcessError(cwd=...)`, использовать `subprocess.run(..., check=True)` и выводить понятное сообщение при отсутствующем шаблоне.
- [x] После фикса обновить `README.md` / `AGENTS.md`: отметить, что установка через `uv` теперь не требует ручного вмешательства, и добавить инструкцию по обновлению (`uv tool upgrade`, `pipx upgrade`).
- [x] Прогнать smoke (`tests/repo_tools/smoke-workflow.sh`) и `uv tool install` на чистой директории, зафиксировать результат в `CHANGELOG.md`.

## Wave 16

### CLI upgrade/sync command
- [x] Реализовать `claude-workflow upgrade` (или флаг `--upgrade`), который сравнивает текущие файлы проекта с шаблонами и обновляет только неизменённые файлы (не трогает пользовательские правки).
- [x] Для конфликта/локальных правок создавать резервную копию (или выводить отчёт) и пропускать обновление, чтобы разработчик смог вручную сравнить изменения.
- [x] Обновлять служебные файлы (`commands`, `hooks`, пресеты, README-шаблоны) из последней версии payload; предусмотреть опцию `--force`, если нужно переписать даже изменённые файлы.
- [x] Добавить хранение версии шаблона (например, `.claude/.template_version`) и предупреждение, если проект отстаёт от установленной версии CLI (предлагать `claude-workflow upgrade`). (obsolete: marketplace-only plugin, отказ от template version tracking)
- [x] Обновить документацию (README, AGENTS.md, CHANGELOG) с описанием нового режима, инструкцией для пользователей и предупреждениями о бэкапах.

## Wave 17

### Рефакторинг структуры payload vs. локальная среда
- [x] Перенести все шаблоны и пресеты, которые должны распространяться с библиотекой, в `src/claude_workflow_cli/payload/`, разбить их по каталогам в стиле spec-kit (`payload/.claude/{commands,agents,hooks}`, `payload/docs`, `payload/templates`, `payload/scripts`) и исключить heredoc-генерацию из `init-claude-workflow.sh`, читая артефакты напрямую.
- [x] Создать git-игнорируемый пример локальной конфигурации (`.claude-example/` + `scripts/bootstrap-local.sh`), который копирует payload в рабочий каталог для dogfooding.
- [x] Обновить `scripts/` и `templates/` на зеркалирование структуры spec-kit (в `scripts/` оставить только операционные утилиты, в `templates/` — исходники генерируемых файлов) и доработать `init-claude-workflow.sh`/CLI так, чтобы они работали с новой раскладкой.
- [x] Добавить сценарий синхронизации (`claude-workflow sync` или документированное решение), который материализует `.claude/**` из payload и обновляет его по запросу.
- [x] Скорректировать упаковку (`MANIFEST.in`, `pyproject.toml`) и тесты, проверяющие, что в дистрибутив попадают все файлы payload и игнорируются локальные примеры.
- [x] Переписать документацию (README, AGENTS.md, AGENTS.md) с описанием разделения payload/локальных настроек и инструкцией по запуску bootstrap-скрипта.

## Wave 18

### Доставка payload через релизы
- [x] `src/claude_workflow_cli/cli.py`: добавить загрузку payload из GitHub Releases (с выбором версии, кешированием и fallback на локальный бандл) для команд `sync` и `upgrade`.
- [x] `AGENTS.md`, `AGENTS.md`, `README.md`: описать новый режим удалённого обновления payload, требования к токенам и офлайн-fallback.

### Манифест и контроль целостности
- [x] `payload/manifest.json`: сгенерировать список всех артефактов (размер, checksum, тип) для использования CLI при `sync`/`upgrade`.
- [x] `src/claude_workflow_cli/cli.py`: показывать diff по манифесту перед синхронизацией, проверять контрольные суммы и логировать пропущенные файлы.

### Расширение релизного пайплайна
- [x] `.github/workflows/release.yml`: публиковать zip-архив payload рядом с wheel и прикладывать manifest checksum.
- [x] `CHANGELOG.md`, `AGENTS.md`: задокументировать новые артефакты релиза и процесс отката до конкретной версии payload.

## Wave 19

### QA-агент и его пайплайн
- [x] `.claude/agents/qa.md`: описать компетенции и чеклист QA-агента (регрессии, UX, производительность), формат отчёта (severity, scope, рекомендации) и стандартные входные данные; предусмотреть ссылки на смежных агентов и параметры из `.claude/settings.json`.
- [x] `.claude/hooks/gate-qa.sh`: разработать хук, который вызывает QA-агента, агрегирует результаты, выводит краткую сводку, помечает блокеры как `exit 1`, а не критичные замечания — как предупреждения; добавить поддержку dry-run и конфигурации через env.
- [x] `config/gates.json`: добавить новый гейт `qa`, определить условия запуска (ветки, тип задач), правила эскалации и связи с существующими gate-tests; описать параметры таймаутов и разрешённых исключений.
- [x] `.github/workflows/ci.yml`, `.github/workflows/gate-workflow.yml` (если потребуется) и `.claude/hooks/gate-workflow.sh`: встроить QA-гейт в общий пайплайн (локально + CI), предусмотреть опциональный запуск (`CLAUDE_SKIP_QA`, `--only qa`) и корректную композицию с другими gate-скриптами.
- [x] и `README.md`: зафиксировать процесс подготовки входных данных для QA-агента, примеры отчётов и интерпретацию статусов; обновить разделы usage/TL;DR с указанием, когда запускать гейт и какие артефакты прикладывать в PR.
- [x] `tests/` и/или `tests/repo_tools/smoke-workflow.sh`: добавить сценарии, проверяющие вызов QA-агента, обработку блокирующих/некритичных дефектов и корректный вывод логов; использовать фикстуры/моки, чтобы детерминировать ответы агента.
- [x] `CHANGELOG.md`: задокументировать добавление QA-агента и обновление пайплайна, описать влияние на разработчиков и инструкцию по миграции (настройка переменных, локальный запуск).

## Wave 20

### Агент ревью PRD и его интеграция в процесс
- [x] `.claude/agents/prd-reviewer.md`: сформулировать мандат агента (структурный аудит PRD, оценка рисков, проверка метрик/гипотез), перечислить входные данные (slug, `docs/prd/<ticket>.prd.md`, связанные ADR/план) и формат отчёта (summary, критичность, замечания по разделам, список открытых вопросов).
- [x] `commands/review-prd.md`: описать сценарий вызова агента ревью PRD из IDE/CLI; зафиксировать, что результат ревью добавляется в раздел `## PRD Review` внутри `docs/prd/<ticket>.prd.md` и чеклист в `docs/tasklist/<ticket>.md`.
- [x] `commands/plan-new.md` и `commands/tasks-new.md`: дополнить инструкциями по обязательной ссылке на результаты PRD-ревью (обновление статуса READY/BLOCKED, перенос критичных замечаний в план и чеклист).
- [x] `.claude/hooks/gate-workflow.sh`: расширить проверку, чтобы перед правками в `src/**` подтверждалось наличие раздела `## PRD Review` с меткой `Status: approved` и отсутствием блокирующих пунктов; предусмотреть bypass через конфиг/slug для прототипов.
- [x] `.claude/hooks/gate-prd-review.sh` (новый): реализовать изолированный хук, который запускает `review-prd` при изменении PRD и блокирует merge при наличии незакрытых blockers; вынести таймаут/уровни серьёзности в `config/gates.json`.
- [x] `config/gates.json`: добавить конфигурацию `prd_review` (ветки, требования, `allow_missing_report`, блокирующие severity, `report_path`) и интеграцию с существующим QA/Tests контуром.
- [x], `AGENTS.md`, `AGENTS.md`: обновить флоу с шагом PRD Review, описать, когда вызывать агента, как интерпретировать вывод и какие поля нужно обновить в PRD/плане; привести пример output.
- [x] `docs/prd/template.md`: добавить шаблонный раздел `## PRD Review` и чеклист статусов (`Status: pending|approved|blocked`, список action items).
- [x] `tests/`: внедрить автотесты `tests/test_gate_prd_review.py` и `tests/test_prd_review_agent.py`, эмулирующие разные статусы ревью, парсинг отчёта, конфигурацию гейта и поведение при блокерах/варнингах.
- [x] `tests/repo_tools/smoke-workflow.sh` и `README.md`: обновить энд-ту-энд сценарий, показывая этап PRD review (вызов команды, фиксация статуса, переход к планированию); зафиксировать влияние на developer experience и требования к артефактам.

## Wave 21

### Мандат агента Researcher и артефакты
- [x] `.claude/agents/researcher.md`: описать миссию агента «Researcher» — поиск существующей логики, принятых подходов и практик для интеграции новой фичи; перечислить обязательные входные данные (slug фичи, предполагаемый scope изменений, список целевых модулей/директорий, ключевые требования) и формат отчёта (обзор найденных модулей, reuse-возможности, найденные риски, список рекомендаций и open questions).
- [x] `commands/researcher.md`: задать сценарий вызова агента (когда запускать, какие артефакты приложить, куда сохранять результат), предусмотреть автоматический экспорт отчёта в `docs/research/<ticket>.md` и ссылку на него внутри `docs/tasklist/<ticket>.md` / `docs/prd/<ticket>.prd.md`.
- [x] `docs/research/template.md`: подготовить шаблон, куда агент будет помещать результаты (структурированные секции «Где встроить», «Повторное использование», «Принятые практики», «Gap-анализ», «Следующие шаги»), и документировать обязательные поля/формат для гейтов.

### Сбор контекста и инструменты для агента
- [x] `src/claude_workflow_cli/tools/researcher_context.py` (новый): реализовать сборщик контекста, который по slug/ключевым словам/путям собирает релевантные участки кода (`rg`-сниппеты, AST/импорт-графы), вытаскивает связанные MD-документы и отдаёт их агенту в виде свернутого prompt-пакета.
- [x] `claude_workflow_cli/data/payload/tools/set_active_feature.py`: расширить, чтобы при активации фичи генерировался список ключевых модулей/директорий для Researcher (по тегам в backlog/conventions), и передавать его в новый сборщик контекста.
- [x] `claude-workflow` CLI: добавить команду `research` (или флаг к `plan-new`), которая запускает сбор контекста, инициирует диалог с агентом и сохраняет отчёт; предусмотреть dry-run и возможность ограничить анализ по каталогам/языкам.

### Интеграция Researcher в флоу и гейты
- [x] `claude-presets/advanced/feature-design.yaml`, `claude-presets/advanced/feature-release.yaml`: встроить шаг Researcher до `plan-new`, описать ожидаемый output и ссылки на отчёт в последующих стадиях (план, тасклист, QA).
- [x] `.claude/hooks/gate-workflow.sh`, `.claude/hooks/gate-tests.sh`: добавить проверку, что для активной фичи существует актуальный `docs/research/<ticket>.md` со статусом `Status: reviewed`, а план/тасклист ссылается на найденные модули; предусмотреть bypass для hotfix/прототипов через `config/gates.json`.
- [x] `config/gates.json`: добавить секцию `researcher` с настройками (требование свежести отчёта, минимальный список проверенных директорий, уровни предупреждений) и связать её с новым хуком/CLI.

### Документация, обучение и контроль качества
- [x], `AGENTS.md`, `AGENTS.md`: обновить флоу — описать, какую информацию приносит Researcher, как читать отчёт и каким образом разработчик подтверждает, что рекомендации применены.
- [x] `AGENTS.md`,: добавить walkthrough с вызовом Researcher на демо-фиче, демонстрацией найденных участков кода и тем, как отчёт используется в QA/код-ревью.
- [x] `tests/test_researcher_context.py`, `tests/test_gate_researcher.py`: наметить автотесты, которые проверяют сбор контекста, корректность генерации отчёта и работу гейтов (включая edge-case: нет совпадений, конфликтующие рекомендации).
- [x] `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh`: включить Researcher в smoke-сценарий (generate context → вызвать агента → проверить наличие отчёта) и покрыть линтером структуру новых шаблонов.

## Wave 22

### Итеративный диалог analyst
- [x] `.claude/agents/analyst.md`: усилить мандат — прописать, что первые действия агента всегда сбор уточняющих вопросов в формате «Вопрос N», ожидание ответов «Ответ N» и повтор цикла, пока все блокеры не закрыты; зафиксировать, что без подтверждения READY агент завершает с `Status: BLOCKED`.
- [x] `commands/idea-new.md`: обновить сценарий, чтобы оператор видел явные инструкции отвечать в формате `Ответ N:` и чтобы генерация PRD откладывалась, пока не получены ответы на все вопросы.
- [x] `src/claude_workflow_cli/cli.py`: добавить подсказки/валидацию при запуске `/feature-dev-aidd:idea-new`, напоминающие о необходимости отвечать на вопросы и возвращающие к циклу, если ответы пропущены.

### Документация и обучение
- [x], `AGENTS.md`: расширить описание роли analyst с пошаговым Q&A-циклом, критерия READY и форматом фиксации ответов.
- [x] `AGENTS.md`, `AGENTS.md`: включить пример диалога (вопрос → ответ → уточнение) и подчеркнуть, что без закрытия вопросов фича остаётся BLOCKED.
- [x] `README.md`, `README.en.md`: обновить quick start/TL;DR, упомянув обязательные ответы на вопросы analyst перед переходом к планированию.

### Контроль качества
- [x] `tests/repo_tools/smoke-workflow.sh`, `tests/test_analyst_dialog.py`: внедрить проверку, что первый вывод агента содержит «Вопрос 1», PRD не получает статус READY до явного набора ответов и что формат ответов соблюдён.
- [x] `config/gates.json`, `.claude/hooks/gate-workflow.sh`: добавить правило, блокирующее переход к плану, пока в PRD есть незакрытые вопросы или отсутствуют ответы в требуемом формате.
- [x] `CHANGELOG.md`: описать новые требования к взаимодействию с analyst и влияние на команду (обязательные ответы, обновлённые подсказки CLI).

## Wave 23

### Перенос tasklist в контур фичи
- [x] `docs/tasklist/<ticket>.md`, `docs/tasklist/template.md`: перенести tasklist в каталог `docs/tasklist/`, сформировать ticket-ориентированную структуру (аналогично `docs/prd/<ticket>.prd.md`), добавить front-matter с `Feature:` и ссылками на PRD/plan/research.
- [x] `docs/tasklist/template.md`, `src/claude_workflow_cli/data/payload/docs/tasklist/template.md`: обновить шаблон и генерацию, чтобы `init-claude-workflow.sh` и CLI создавали `docs/tasklist/<ticket>.md` вместо корневого `tasklist.md`, учитывая payload-артефакты.
- [x] `src/claude_workflow_cli/tools/set_active_feature.py`: подготовить миграцию, которая переносит legacy `tasklist.md` в новую директорию и обновляет ссылки в `.active_feature`.

### Обновление CLI, команд и гейтов
- [x] `src/claude_workflow_cli/cli.py`, `src/claude_workflow_cli/data/payload/commands/tasks-new.md`, `commands/tasks-new.md`: научить команды работать с slug-ориентированным tasklist, синхронизировать инструкции и вывод.
- [x] `.claude/hooks/gate-workflow.sh`, `.claude/hooks/gate-tests.sh`, `.claude/hooks/gate-qa.sh`: обновить проверки чеклистов и путь к tasklist; синхронизировать payload-версии хуков.
- [x] `config/gates.json`, `claude-presets/advanced/feature-release.yaml`, `claude-presets/feature-plan.yaml`: скорректировать конфиг и пресеты, чтобы агенты и гейты ссылались на `docs/tasklist/<ticket>.md`.

### Документация, тесты и UX
- [x] `AGENTS.md`, `README.md`, `README.en.md`: обновить схемы и walkthrough, подчёркивая, что tasklist теперь хранится в `docs/tasklist/<ticket>.md`.
- [x] `tests/test_gate_workflow.py`, `tests/test_qa_agent.py`, `tests/test_gate_researcher.py`, `tests/repo_tools/smoke-workflow.sh`: адаптировать тесты и smoke-сценарий под новую структуру tasklist, покрыть миграцию и параллельные slug'и.
- [x] `CHANGELOG.md`, `AGENTS.md`, `AGENTS.md`: зафиксировать переход на feature-ориентированный tasklist и обновить примеры использования.

## Wave 24

### Управление запуском тестов по запросу reviewer
- [x] `.claude/agents/reviewer.md`: описать протокол, в котором агент reviewer помечает необходимость прогона тестов (например, статус `Tests: required`) и передаёт его в пайплайн.
- [x] `.claude/hooks/format-and-test.sh`, `.claude/hooks/gate-tests.sh`, `.claude/hooks/gate-workflow.sh`: встроить проверку маркера reviewer так, чтобы тесты запускались только по требованию агента, с fallback для ручного запуска (`STRICT_TESTS`, `TEST_SCOPE`).
- [x] `config/gates.json`, `.claude/settings.json`, `src/claude_workflow_cli/cli.py`: добавить настройки и CLI-флаги, позволяющие прокидывать запросы reviewer, включать/выключать обязательный тест-ран и сохранять обратную совместимость.
- [x] `AGENTS.md`, `tests/test_gate_tests_hook.py`, `tests/repo_tools/smoke-workflow.sh`: зафиксировать новый порядок действий, обновить чеклисты и покрыть сценарий запуска тестов по запросу reviewer/ручному override.

## Wave 25

### Итеративное отмечание прогресса
- [x] `.claude/agents/implementer.md`, `.claude/agents/qa.md`, `.claude/agents/reviewer.md`: усилить инструкции, требуя после каждого инкремента работы фиксировать, какие пункты `docs/tasklist/<ticket>.md` закрыты, и явно указывать номер/название чекбокса, который был отмечен.
- [x] `commands/implement.md`, `commands/review.md`, `commands/tasks-new.md`, `src/claude_workflow_cli/data/payload/commands/{implement.md,review.md,tasks-new.md}`: добавить шаги с обязательным подтверждением «checkbox updated» и подсказками, как обновлять `- [ ] → - [x]` в текущей ветке перед завершением ответа агента.
- [x] `docs/tasklist/template.md`, `src/claude_workflow_cli/data/payload/docs/tasklist/template.md`: вшить блок «Как отмечать прогресс», описать формат указания времени/итерации рядом с чекбоксом и требования к ссылкам на выполнение.

### Автоматические проверки и UX
- [x] `src/claude_workflow_cli/cli.py`, `src/claude_workflow_cli/progress.py` (новый): реализовать проверку, что каждый вызов `/feature-dev-aidd:implement` или `/feature-dev-aidd:qa` после изменения кода приводит к появлению новых `- [x]` в активном tasklist; при отсутствии прогресса CLI возвращает подсказку и предлагает вернуться к доработке.
- [x] `.claude/hooks/gate-workflow.sh`, `config/gates.json`: добавить правило, которое блокирует merge, если в diff задач feature нет обновлённых чекбоксов при изменениях в `src/**`; предусмотреть override для технических задач без tasklist.
- [x] `tests/test_gate_workflow.py`, `tests/test_qa_agent.py`, `tests/repo_tools/smoke-workflow.sh`: расширить тесты, проверяющие, что новый прогресс-чек применяется, и зафиксировать сценарии с несколькими итерациями и отсутствием обновления чекбоксов.

### Документация и обучение команды
- [x] `AGENTS.md`,: переписать walkthrough, подчёркивая итеративное отмечание прогресса и необходимость ссылаться на обновлённые чекбоксы в ответах агентов.
- [x] `README.md`, `README.en.md`, `CHANGELOG.md`: зафиксировать новое требование и обновить разделы quick start / release notes с описанием обязательной синхронизации tasklist.

## Wave 26

### Переход на идентификатор TICKET
- [x] `src/claude_workflow_cli/cli.py`, `src/claude_workflow_cli/progress.py`, `src/claude_workflow_cli/data/payload/tools/set_active_feature.py`: перевести CLI и хранение состояния на TICKET как основной идентификатор (`--ticket`, `docs/.active_ticket`), мигрировать legacy slug и оставить slug-хинт в качестве дополнительного контекста (`--slug-note`) для агентов.
- [x] `config/gates.json`, `.claude/hooks/format-and-test.sh`, `.claude/hooks/gate-workflow.sh`, `.claude/hooks/gate-tests.sh`, `tests/repo_tools/smoke-workflow.sh`: обновить проверки и отчёты на использование `{ticket}` вместо `{slug}`, прокидывая slug только как дополнительную подсказку в логах и отчётах.

### Команды и шаблоны
- [x] `commands/*.md`, `.claude/agents/*.md`, `src/claude_workflow_cli/data/payload/.claude/**`: переписать сигнатуры команд и инструкции агентов под обязательный `<TICKET>` с опциональным блоком `slug`, синхронизировать payload-версии.
- [x] `docs/tasklist/template.md`, `src/claude_workflow_cli/data/payload/docs/tasklist/template.md`, `docs/tasklist/*.md`: внедрить фронт-маттер `Ticket:` и `Slug hint:`, обновить генерацию tasklist/PRD и ссылки на артефакты.

### Документация и миграция
- [x] `README.md`, `README.en.md`, `AGENTS.md`,: переписать walkthrough и примеры команд под модель TICKET-first, описать роль slug-хинта как пользовательского ориентира.
- [x] `CHANGELOG.md`, `AGENTS.md`, `AGENTS.md`, `tests/test_gate_workflow.py`, `tests/test_qa_agent.py`: подготовить миграцию Wave 26 (slug → ticket-first), обновить релизные заметки и покрыть сценарии тестами.

## Wave 27

_Статус: активный, приоритет 1. Объединено с Wave 46. Цель — установка в поддиректорию `aidd/` с полным payload и официальным плагином/хуками Claude Code._
Прогресс: init/sync/smoke/tests под `aidd/` готовы; остаются задачи по документации и оформлению плагина.

### Установка в поддиректорию `aidd/` и упаковка payload (в процессе)
- [x] `AGENTS.md`: зафиксировать новую структуру установки (дефолт `./aidd/`), сценарии `--workspace-root`/`--target`, влияние на DX и совместимость; описать, что все артефакты плагина (`aidd/.claude`, `aidd/docs`, `aidd/tools`, `aidd/prompts`, `aidd/scripts`, `aidd/config`, `aidd/claude-presets`, `aidd/templates`, `aidd/reports`, `aidd/etc`) живут внутри поддиректории.
- [x] `AGENTS.md`: сравнить варианты (авто-перенос, генерация поверх `--target`, шаблонный репозиторий) и выбрать целевой подход для `aidd/`.
- [x] `src/claude_workflow_cli/cli.py` / `init.py`: добавить поддержку установки в `aidd/` по умолчанию, опцию переопределения пути, защиту от конфликтов и автоматический перенос payload при `claude-workflow init --target.` (после `uv tool install --force "git+https://github.com/GrinRus/ai_driven_dev.git#egg=claude-workflow-cli[call-graph]"`).
- [x] `src/claude_workflow_cli/resources.py` (новый): единый слой копирования payload/плагина в выбранный корень с учётом manifest, прав и дотфайлов.
- [x] `init-claude-workflow.sh`, `tests/repo_tools/smoke-workflow.sh`: синхронизировать bash-обёртку с новой структурой, покрыть пустую/существующую директорию, гарантировать идентичную логику с CLI и новой раскладкой `aidd/`. _Сделано: init + smoke работают с поддиректорией, тесты зелёные._
- [x] Обновить manifest/payload так, чтобы все каталоги (`docs/tools/prompts/scripts/config/claude-presets/templates/reports/etc`) жили под `aidd/`; обеспечить sync-скрипты/проверки на новую вложенность и гарантировать, что после `claude-workflow init --target. --commit-mode ticket-prefix --enable-ci --force` доступны команды, агенты и скрипты без ручных шагов. _Сделано: payload переложен в `aidd/`, manifest пересобран под префикс; sync-check обновлён._
- [x] Перенести системные файлы в древовидную структуру `aidd/` (исключить корневые `.claude`/`.dev` и прочие артефакты, которые разворачиваются при установке); разложить корневые шаблоны/скрипты/README, относящиеся к payload, в подпапки. _Сделано: корневые снапшоты удалены, игнор добавлен._
- [x] Покрыть установку в `aidd/` тестами/smoke: CLI init в целевой каталог, проверка доступности всех команд/агентов/скриптов и прав доступа через `claude-workflow` без ручных шагов. _pytest + smoke проходят._

- Оставшиеся открытые задачи по плагину/командам/агентам/хукам и документации перенесены в Wave 46.

## Wave 28

### Интеграция Researcher в `/feature-dev-aidd:idea-new`
- [x] `commands/idea-new.md`: встроить шаг `claude-workflow research --ticket "$1"` перед запуском саб-агента analyst, описать опции `--paths/--keywords`, обработать сценарий «новый проект» (создаём отчёт со статусом `Status: pending` и пометкой «контекст пуст, требуется первичный baseline»).
- [x] `.claude/agents/analyst.md`: требовать актуальный `docs/research/<ticket>.md`, использовать вывод Researcher как источник вопросов, фиксировать в `## Диалог analyst` ссылку на отчёт и отмечать, если исследование выявило готовые паттерны или подтвердило «нет данных».
- [x] `commands/researcher.md`, `docs/research/template.md`: добавить блок «Отсутствие паттернов» и обязательную секцию `## Паттерны/анти-паттерны`, описать, как оформлять вывод для пустого проекта.

### CLI и сбор контекста
- [x] `src/claude_workflow_cli/cli.py`: добавить опцию `--auto` для `research` (запуск из `/feature-dev-aidd:idea-new` без дополнительных вопросов), возвращать явное уведомление, если найдено 0 матчей, и прокидывать флаг в шаблон.
- [x] `tools/researcher_context.py`: реализовать эвристики поиска актуальных паттернов (детектирование тестов, конфигураций, слоёв `src/*`, шаблонов логирования); при отсутствии совпадений генерировать блок «проект новый» и список рекомендаций на основе `config/conventions.json`.
- [x] `tools/set_active_feature.py`: после установки фичи автоматически запускать `claude-workflow research --targets-only` для подготовки путей ещё до `/feature-dev-aidd:idea-new`.

### Автоматические проверки
- [x] `src/claude_workflow_cli/tools/analyst_guard.py`: убедиться, что при Status: READY в PRD присутствует ссылка на исследование и метка статуса из `docs/research/<ticket>.md`; для статуса `Status:.pending` указывать, что research нужно довести до reviewed.
- [x] `.claude/hooks/gate-workflow.sh`, `config/gates.json`: синхронизировать новые статусы research, разрешить merge с пометкой «контекст пуст» только если зафиксирован baseline после `/feature-dev-aidd:idea-new`.

### Документация и тесты
- [x], `AGENTS.md`, `README.md`: описать обновлённый порядок `/feature-dev-aidd:idea-new → claude-workflow research → analyst`, правила для пустых репозиториев и требования к паттернам.
- [x] `tests/test_gate_researcher.py`, `tests/test_gate_workflow.py`: добавить сценарии для «project new» (нулевые совпадения) и для кейса с найденными паттернами, проверять, что гейт отрабатывает предупреждение.
- [x] `tests/repo_tools/smoke-workflow.sh`, demo‑проект: показать новую последовательность и пример отчёта Researcher с перечислением найденных паттернов.

## Wave 30

### Автосоздание PRD в `/feature-dev-aidd:idea-new`
- [x] `commands/idea-new.md`: перед запуском аналитика добавить шаг, который гарантированно создаёт `docs/prd/$1.prd.md` из `docs/prd/template.md` (если файл отсутствует), записывает `Status: draft` и ссылку на `docs/research/$1.md`; описать, что повторный запуск не перезаписывает уже заполненный PRD.
- [x] `tools/set_active_feature.py`, `src/claude_workflow_cli/feature_ids.py`: после фиксации тикета автоматически scaffold'ить PRD и директорию `docs/prd/`, чтобы хуки и гейты всегда находили файл до начала диалога; предусмотреть флаг `--skip-prd-scaffold` для редких ручных сценариев.
- [x] `docs/prd/template.md`: обновить шаблон — пометить раздел `## Диалог analyst` статусом `Status: draft`, добавить комментарий о том, что файл создан автоматически и должен быть заполнен агентом до READY.

### Гейты и проверки
- [x] `scripts/prd_review_gate.py`: заменить сообщение «нет PRD → /feature-dev-aidd:idea-new» на «PRD в статусе draft, заполните диалог/ревью»; считать `Status: draft` валидным индикатором незавершённого PRD и выдавать понятную инструкцию вместо совета повторно запускать `/feature-dev-aidd:idea-new`.
- [x] `src/claude_workflow_cli/tools/analyst_guard.py`: добавить проверку для `Status: draft` с сообщением о необходимости довести диалог до READY, а также убедиться, что наличие автошаблона не обходит требования по вопросам/ответам.
- [x] `tests/test_gate_prd_review.py`, `tests/test_analyst_guard.py`, `tests/repo_tools/smoke-workflow.sh`: покрыть сценарий автосозданного PRD (файл есть, но статус draft) и убедиться, что гейты выключают ошибку «нет PRD» и переходят к содержательной проверке.

### Документация и обучение
- [x] `README.md`, `README.en.md`, `AGENTS.md`, `AGENTS.md`,: описать, что `/feature-dev-aidd:idea-new` сразу создаёт PRD-шаблон, поэтому гейты больше не просят перезапуск; выделить обязанности агента (заполнить `## Диалог analyst`, снять статус draft).
- [x] `AGENTS.md`, `CHANGELOG.md`: зафиксировать Wave 30 как обновление UX аналитики, перечислить шаги автосоздания PRD и обновлённые сообщения гейтов.

## Wave 31

### Единый источник payload + автоматическая синхронизация
- [x] `scripts/sync-payload.sh`: добавить утилиту синхронизации между `src/claude_workflow_cli/data/payload` и корнем. Поддержать режимы `--direction=to-root` (разворачиваем payload в репозитории для dogfooding) и `--direction=from-root` (зеркалим обратно при подготовке релиза); предусмотреть инвариант, что список копируемых директорий задаётся явно (`.claude`, `docs`, `templates`, `scripts/init-claude-workflow.sh` и т.д.), и выводим diff по ключевым файлам.
- [x] `tools/check_payload_sync.py` + CI/pre-commit: написать проверку, которая сравнивает контрольные суммы payload-контента и корневых «runtime snapshot» файлов. Если обнаружены расхождения без фиксации `sync --direction=from-root`, тест/CI должен падать. Добавить запуск в `.github/workflows/ci.yml` и как pre-commit hook.
- [x] Документация и процессы: в `AGENTS.md`, `CONTRIBUTING.md`, `AGENTS.md` описать правило «редактируем только payload → синхронизуем скриптом». В release checklist добавить обязательный шаг `scripts/sync-payload.sh --direction=from-root && pytest tests/test_init_hook_paths.py` перед `uv publish`. Упомянуть, что для локальной проверки нужно использовать `scripts/bootstrap-local.sh --payload src/.../payload`, а не трогать `.claude` вручную.
- [x] Тесты: расширить `tests/test_init_hook_paths.py` и/или создать `tests/test_payload_sync.py`, который проходит по списку критичных файлов (хуки, `init-claude-workflow.sh`, шаблоны docs) и проверяет, что payload и root синхронизированы. Тест должен использовать общий helper для расчёта хэшей и работать от `src/claude_workflow_cli/data/payload`.
- [x] CI/tooling: обновить `tests/repo_tools/ci-lint.sh` и `Makefile` (если появится) так, чтобы новые проверки запускались локально командой `scripts/sync-payload.sh --direction=from-root && python tools/check_payload_sync.py`. Зафиксировать рекомендацию в `backlog.md` для последующих волн.

## Wave 32

- [x] (новый), `README.md`,: зафиксировать обязательные секции для агентов/команд (Контекст, Входы, Автоматизация, Формат ответа, Fail-fast), описать требования к строке `Checkbox updated`, ссылкам на `docs/prd|plan|tasklist`, правилам эскалации блокеров и матрицу «роль → артефакты/хуки`.
- [x] `AGENTS.md`, `AGENTS.md`, `claude-presets/advanced/prompt-governance.yaml` (новый): добавить шаблоны фронт-маттера (`name/description/tools/inputs/outputs/hooks`) и готовые заголовки, а также preset/скрипт развёртывания (`scripts/scaffold_prompt.py` или Make target) с примерами использования в CLI.

### Обновление агентов
- [x] `.claude/agents/{analyst,planner,implementer,reviewer,qa,researcher,validator,prd-reviewer}.md`: переписать на новый шаблон, явно прописать входные артефакты, чеклисты, статусы READY/BLOCKED/WARN и единый формат вывода; удалить дубли описания «Checkbox updated», заменив ссылкой на playbook.

### Обновление команд
- [x] `commands/{idea-new,plan-new,tasks-new,implement,review-prd,review,reviewer,researcher}.md`: структурировать инструкции блоками «Когда запускать», «Автоматические хуки/переменные», «Что редактируется», «Ожидаемый вывод», «Примеры CLI»; убедиться, что каждая команда ссылается на соответствующего агента и актуальные документы через `@docs/...` нотацию.

### Автоматизация и проверки
- [x] `tests/repo_tools/lint-prompts.py`, `tests/repo_tools/ci-lint.sh`, `.github/workflows/ci.yml`, `tests/test_prompt_lint.py`: добавить линтер промптов, который валидирует фронт-маттер, наличие обязательных секций, консистентность между парами агент↔команда (например, implementer/implement), и включить его в CI/pre-commit.

### Мультиязычные промпты и версионирование
- [x] `.claude/agents/**`, `commands/**`: ввести структуру `prompts/<lang>/...` (RU/EN) или дубликаты `.ru.md`/`.en.md`; в каждом фронт-маттере добавить поля `lang`, `prompt_version`, `source_version` и ссылку на базовый шаблон. Обеспечить, чтобы RU и EN варианты содержали одинаковые блоки (через lint).
- [x], `AGENTS.md` (новый): описать политику двух языков, правила синхронизации (когда менять обе версии, как обозначать отличия), формулу версионирования (`major.minor.patch`, где major — изменение структуры, minor — правки текста, patch — правки примечаний), и процедуру ревью (обновление changelog/prompts.json).
- [x] `AGENTS.md`, `CHANGELOG.md`: задокументировать запуск двуязычных промптов и версионирования, включая инструкцию «как откатиться к предыдущей версии промпта» (git tag/manifest), и добавить пример записи в release checklist (`tests/repo_tools/prompt-version bump --lang ru,en`).

### Тесты и проверка качества
- [x] `tests/repo_tools/smoke-workflow.sh`, `tests/test_gate_workflow.py`: добавить smoke-тест на gate, который редактирует только один язык и убеждается, что gate блокирует merge; предусмотреть позитивный сценарий, где обе локали обновлены и gate пропускает изменения.
- [x] `tests/repo_tools/ci-lint.sh`: включить новые тесты и эмулировать минимум один прогон `tests/repo_tools/prompt-version bump --lang ru,en` для проверки версионирования.

- [x] `tests/test_prompt_versioning.py`: добавить тесты `tests/repo_tools/prompt-version` для команд и ситуаций с частичным bump (например, только ru, только en, skip), проверить обновление `source_version`.
- [x] `tests/repo_tools/smoke-workflow.sh`, `tests/test_gate_workflow.py`: расширить сценарии gate для команд и `Lang-Parity: skip`, включить проверку, что после удаления skip гейт снова требует синхронное обновление.
- [x] `init-claude-workflow.sh`, `claude_workflow_cli` (`cli.py`, payload settings): добавить CLI-переключатель (например, `--prompt-locale en`) или конфиг, который копирует `prompts/en/**` в `.claude/` при установке; обновить документацию и smoke-тест.

## Wave 33

_Статус: активный, приоритет 3. Цель — zero-touch вызов CLI через shim/helper._

### Zero-touch запуск CLI после установки
- [x] `tools/run_cli.py` (новый), `tools/set_active_feature.py`, `.claude/hooks/gate-workflow.sh`, `.claude/hooks/format-and-test.sh`, `tests/repo_tools/smoke-workflow.sh`, `scripts/qa-agent.py`: внедрить helper `run_cli(command: list[str])`, который ищет бинарь `claude-workflow` в PATH (поддержка uv/pipx шима), умеет читать `CLAUDE_WORKFLOW_BIN`/`CLAUDE_WORKFLOW_PYTHON`, а при отсутствии печатает инструкцию «установите CLI командой …»; все скрипты должны использовать helper вместо прямого запуска python‑модулей, чтобы пользователю хватало шагов установки из README. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
  - добавляем в `.claude/hooks/lib_cli.sh` функции `require_cli` и `run_cli_or_hint`, которые:
    1. подключают `tools/run_cli.py` через `python3` и автоматически наследуют `.claude/hooks/_vendor` в пути импорта, если helper переключается в режим `python -m`;
    2. умеют печатать INSTALL_HINT и возвращать код 127, если CLI не найден (тот же текст, что в helper);
    3. предоставляют единый API для `gate-workflow.sh`, `gate-qa.sh`, `gate-tests.sh`, `format-and-test.sh` и всех будущих хуков (все вызовы CLI заменяются на `run_cli_or_hint claude-workflow <command>`).
  - `scripts/qa-agent.py` переносим в CLI как `claude-workflow qa-agent`: логика агента живёт в модуле `claude_workflow_cli.commands.qa_agent`, а скрипт в `scripts/` становится тонким шорткатом (или удаляется). `gate-qa.sh` и документация (playbook/QA) вызывают только CLI-команду, без `sys.path` и `python3 scripts/*.py`.
  - `tools/set_active_feature.py`, smoke-скрипт и тестовые helper'ы полностью отказываются от ручных манипуляций с `sys.path`, используют только `run_cli`/`CLAUDE_WORKFLOW_BIN|CLAUDE_WORKFLOW_PYTHON`. В payload добавляем те же `lib_cli.sh`/`tools/run_cli.py` (и, при необходимости, `scripts/run-cli.sh`), чтобы проекты из `claude-workflow init` сразу получали zero-touch UX.
- [x] `src/claude_workflow_cli/data/payload/scripts/*.sh`, `src/claude_workflow_cli/data/payload/tools/*.py`, `.claude/hooks/*.sh`: зеркалировать helper в payload (например, через `scripts/run-cli.sh`), чтобы артефакты, которые копирует `claude-workflow init`, автоматически вызывают CLI из установленного пакета без ручной настройки путей. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
  - payload получает те же `lib_cli.sh`/`run_cli.py`; `manifest.json`, `scripts/sync-payload.sh` и `tools/check_payload_sync.py` обновляются, чтобы helper не выпадал из релиза;
  - smoke-тест из payload и preset'ы прогоняют сценарий без dev-src, подтверждая, что init-проект сразу вызывает CLI через shim.
- [x] `README.md`, `README.en.md`, `AGENTS.md`,: обновить инструкции по установке/требованиям окружения — явно указать, что `claude-workflow` попадает в PATH после `uv tool install`/`pipx install`, удалить рекомендации импортировать модуль напрямую и добавить troubleshooting-блок «CLI не найден» с подсказками `uv tool install …`/`pipx install …`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
  - добавляем раздел «CLI не найден»: `uv tool install …`, `pipx install …`, проверка `which claude-workflow`, использование `CLAUDE_WORKFLOW_BIN`/`CLAUDE_WORKFLOW_PYTHON`;
  - подчёркиваем в workflow/playbook'ах, что все агенты и хуки запускают CLI через helper, поэтому отдельный `pip install` или ручная настройка путей больше не требуется.
- [x] `tests/test_cli_entrypoint.py` (новый), `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh`: добавить проверки, эмулирующие чистую систему (без dev-src, только бинарь `claude-workflow`), и убедиться, что helper корректно находит CLI; при отсутствии бинаря тесты должны давать понятное сообщение и ссылку на команды установки. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
  - новый тест мокаeт `shutil.which`/`subprocess.run`, проверяет порядок fallback'ов (`CLAUDE_WORKFLOW_BIN → shim claude-workflow → sys.executable -m`), очищает override‑пути и убеждается, что при отсутствии CLI helper печатает INSTALL_HINT и возвращает 127;
  - `tests/repo_tools/smoke-workflow.sh` перед вызовом helper сбрасывает override‑пути, временно скрывает `src` (например, запускается в подпапке без dev-src) и использует `run_cli` для всех команд, чтобы подтвердить zero-touch E2E;
  - `tests/repo_tools/ci-lint.sh` явно добавляет `python3 -m unittest discover -s tests -t . -p "test_cli_entrypoint.py"` (помимо общего `unittest` прогона), чтобы регрессии shim падали до merge.
## Wave 34
### Agent-first промпты и гайды
- [x], `AGENTS.md`, `backlog.md`: переписать правила с упором на «agent-first» модель (агент сам читает файлы и запускает скрипты, вопросы пользователю — крайняя мера), убрать упоминания человеческих ресурсных ограничений и добавить примеры автоматических источников данных.
- [x] `README.md`, `README.en.md`, `AGENTS.md`, `CHANGELOG.md`: задокументировать переход на «agent-first» (новый раздел в README, запись в релизных заметках, чеклист миграции существующих проектов).

### Обновление шаблонов документов
- [x] `docs/prd/template.md`, `src/claude_workflow_cli/data/payload/docs/prd/template.md`: заменить поля «Владелец/Команда/Оценка ресурсов» на разделы «Автоматизация/Системные интеграции», добавить подсказки по фиксации CLI/скриптов, которые должен запускать агент.
- [x] `docs/tasklist/template.md`, `src/claude_workflow_cli/data/payload/docs/tasklist/template.md`: переписать чеклисты так, чтобы пункты ссылались на артефакты (диффы, логи тестов, отчёты), а не на коммуникацию со стейкхолдерами; уточнить формат отметок (`путь → дата → ссылка`).
- [x] `docs/research/template.md`, `src/claude_workflow_cli/data/payload/docs/research/template.md`: убрать поля `Prepared by`/«Связанные команды», добавить секции «Как запускать окружение», «Обязательные проверки», «Точки вставки кода» с примерами CLI-команд.

### Перепаковка агентов и команд
- [x] `.claude/agents/{analyst,researcher,implementer}.md`, `prompts/en/agents/{analyst,researcher,implementer}.md`, `src/claude_workflow_cli/data/payload/{.claude,prompts/en}/agents/{analyst,researcher,implementer}.md`: переписать контекст и план действий так, чтобы агенты собирали данные из репозитория (backlog, tests, reports) и записывали результаты напрямую. Q&A с пользователем оставляем только у аналитика для заполнения PRD, когда автоматический разбор не отвечает на все вопросы. Обязательно подсветить, какие команды запускать (`rg`, `pytest`, `claude-workflow progress`), какие права/инструменты есть у агента (чтение, запись, доступные Bash-команды) и как фиксировать результаты в артефактах.
- [x] `commands/idea-new.md`, `prompts/en/commands/idea-new.md`, `src/claude_workflow_cli/data/payload/{.claude,prompts/en}/commands/idea-new.md`: синхронизировать с новой ролью аналитика (автоматическое заполнение PRD, fallback без пользователя), убрать требования ручного подтверждения `--paths/--keywords`.
- [x] `AGENTS.md`, `AGENTS.md`, `src/claude_workflow_cli/data/payload/templates/{prompt-agent.md,prompt-command.md}`: обновить подсказки — вместо «задавайте вопросы» прописать обязательные блоки по чтению артефактов, запуску утилит и фиксации артефактов в ответе.

### Синхронизация payload и тесты
- [x] `scripts/sync-payload.sh`, `tools/check_payload_sync.py`: убедиться, что новые промпты/шаблоны корректно копируются между корнем и payload, добавить smoke-проверки для agent-first разделов.
- [x] `tests/test_cli_sync.py`, `src/claude_workflow_cli/data/payload/tests/test_payload_sync.py`: расширить тесты синхронизации на новые файлы (обновлённые шаблоны и промпты), чтобы не потерять «agent-first» инструкции в дистрибутиве.
- [x] `tests/repo_tools/ci-lint.sh`, `.github/workflows/ci.yml`: подключить новые проверки (например, `rg 'Answer [0-9]'` → провал, если в промпте остались упоминания ручного Q&A), прогонять их в CI.

### Коммуникация и миграция
- [x] `AGENTS.md`, `AGENTS.md`, `AGENTS.md`: добавить раздел «Как мигрировать существующие проекты на agent-first» (шаги обновления шаблонов, прогон sync+tests, чеклист по обновлению `.claude/agents`).
- [x] `examples/` (demo проект), `init-claude-workflow.sh`, `claude-presets/**`: обновить демонстрационные артефакты и preset'ы, чтобы они разворачивали уже «agent-first» версии промптов и документов.

## Wave 35

### Команда /feature-dev-aidd:qa и UX
- [x] `commands/qa.md`, `prompts/en/commands/qa.md` (новые): оформить `/feature-dev-aidd:qa` как отдельную стадию после `/feature-dev-aidd:review`; входы — активный ticket/slug-hint, diff, QA‑раздел tasklist, логи гейтов; автоматизация — обязательный вызов агента `qa` + `gate-qa.sh`, CLI-обёртка `claude-workflow qa --gate` (паттерн остальных команд), `claude-workflow progress --source qa`; формат ответа — `Checkbox updated`, статус READY/WARN/BLOCKED + ссылка на обязательный отчёт `reports/qa/<ticket>.json`; примеры запуска (CLI/палитра).
- [x] `.claude/agents/qa.md`, `prompts/en/agents/qa.md`: обновить под новую команду и agent-first: обязательность перед релизом, фиксация `Checkbox updated`, создание/обновление `reports/qa/<ticket>.json`, ссылки на логи и tasklist.

### Встраивание в процесс
- [x] `AGENTS.md`,, `README.md`, `README.en.md`: включить обязательный шаг `/feature-dev-aidd:qa` (после `/feature-dev-aidd:review`) в walkthrough/quick-start, перечислить входы (diff, tasklist QA, логи гейтов), параметры гейта (`CLAUDE_SKIP_QA`, `--only qa`, dry-run), формат отчёта и прогресс-маркеры.
- [x] `docs/tasklist/template.md`: усилить QA-блок — что проверяется, куда писать лог/отчёт, примеры `Checkbox updated` для регрессий/UX/перф с ссылками на `reports/qa/<ticket>.json`.

### Гейты и конфигурация
- [x] `.claude/hooks/gate-qa.sh`, `config/gates.json`: переключить дефолтную команду на `claude-workflow qa --gate` (через helper `run_cli_or_hint`), требовать отчёт `reports/qa/{ticket}.json` (привязка к ticket, allow_missing_report=false), уважать `skip_branches`/`CLAUDE_SKIP_QA`, поддерживать dry-run/`--only qa`, печатать подсказку «запустите /feature-dev-aidd:qa».
- [x] `scripts/qa-agent.py`: синхронизировать опции/формат JSON с CLI (`--ticket/--slug-hint/--branch/--report/--block-on/--warn-on/--dry-run`), описать режимы `--gate` и интерактив в.

### Тесты и payload
- [x] `tests/test_gate_qa.py`, `tests/repo_tools/smoke-workflow.sh`: unit + полный дымовой сценарий: READY/WARN/BLOCKED, отсутствие отчёта (должно падать), `--only qa`, dry-run (не падает на блокерах), обновление tasklist/`Checkbox updated`; включить в CI.
- [x] `src/claude_workflow_cli/data/payload/**`: отзеркалить новую команду/агента, обновлённые гайды, гейт и smoke-сценарии; обновить `manifest.json` и проверить `tools/check_payload_sync.py`.

## Wave 36

_Статус: закрыт (за ненадобностью). Автоаналитика в `/feature-dev-aidd:idea-new` поверх zero-touch CLI._

### Усиление agent-first для `/feature-dev-aidd:idea-new` и аналитика
- [x] `init-claude-workflow.sh`, `claude_workflow_cli/cli.py`: жёсткий автозапуск `claude-workflow analyst --ticket <ticket> --auto` сразу после `research --auto`, graceful fallback с INSTALL_HINT, обновлённые smoke/tests. _(закрыто за ненадобностью)_
- [x] `.claude/agents/analyst.md`, `prompts/en/agents/analyst.md`: логирование повторных research (paths/keywords), обязательный `analyst-check` при смене статуса READY, fail-fast при отсутствии `.active_ticket`/PRD. _(закрыто за ненадобностью)_
- [x] `commands/idea-new.md`, `prompts/en/commands/idea-new.md`: синхронизация с автозапуском аналитика и правилами повторного research; обновить payload-копии и примеры. _(закрыто за ненадобностью)_
- [x] Тесты и smoke: добавить сценарий `/feature-dev-aidd:idea-new` → auto-analyst → repeat research → PRD READY; убедиться, что payload-sync/manifest покрывают новые артефакты. _(закрыто за ненадобностью)_
- [x] Документация: README/AGENTS.md — кратко зафиксировать автозапуск аналитика, логи повторного research и требование `analyst-check` после READY. _(закрыто за ненадобностью)_

## Wave 37

### Удаление внутреннего backlog из дистрибутива
- [x] `backlog.md`: оставить файл только для разработки (dev-only), исключив его из устанавливаемого payload; при необходимости перенести в `docs/dev-backlog.md` или пометить как ignore для sync.
- [x] `src/claude_workflow_cli/data/payload/manifest.json`, `tools/check_payload_sync.py`, `tests/test_payload_manifest.py`, `tests/test_package_payload.py`: удалить запись о `backlog.md`, обновить проверку состава payload и убедиться, что сборка wheel/zip не тянет файл.
- [x] `scripts/sync-payload.sh`, `src/claude_workflow_cli/data/payload/tests/test_payload_sync.py`: скорректировать списки путей, чтобы sync не требовал `backlog.md`; добавить тест, который гарантирует отсутствие dev-only файлов в payload.
- [x] Документация (`AGENTS.md`, `CHANGELOG.md`): отметить, что backlog не поставляется конечным пользователям, добавить запись в release checklist и guidance по ведению roadmap в репо без включения в payload.
- [x] Проверка и smoke: прогнать `tests/repo_tools/ci-lint.sh`, `tools/check_payload_sync.py`, smoke-сценарии сборки дистрибутива, удостовериться в корректной установке через `uv/pipx` без `backlog.md` в артефактах.

## Wave 38

-### Researcher: глубокий анализ кода и переиспользование
- [x] `.claude/agents/researcher.md`, `prompts/en/agents/researcher.md`, `src/claude_workflow_cli/data/payload/{.claude,prompts/en}/agents/researcher.md`: усилить мандат агента — обязательное чтение кода (функции/классы/тесты), поиск точек встраивания и reuse-кандидатов (shared utils, сервисы, API-клиенты), ссылки на конкретные файлы/символы, вывод в разделе «Что переиспользуем» с приоритетами.
- [x] `commands/researcher.md`, `src/claude_workflow_cli/data/payload/commands/researcher.md`, `prompts/en/commands/researcher.md`: обновить сценарий запуска с режимом глубокого разбора кода (флаги глубины, фильтр директорий/языков), требовать в отчёте разделы «Паттерны/антипаттерны», «Готовые модули к переиспользованию» и checklist применения; добавить пример вызова с `--deep`/`--reuse` и явную инструкцию строить call/import graph на стороне Claude Code.
- [x] `docs/research/template.md`, `src/claude_workflow_cli/data/payload/docs/research/template.md`: расширить шаблон секциями для переиспользования (модуль/файл → как использовать → риски), перечнем найденных паттернов и обязательными ссылками на тесты/контракты, куда агент должен писать результаты.
- [x] `src/claude_workflow_cli/tools/researcher_context.py`, `tools/researcher_context.py`, `src/claude_workflow_cli/data/payload/tools/researcher_context.py`: добавить deep-mode сборки кода (нарезка функций/классов, импорт-листы, соседние тесты, поисковая выдача похожих модулей/утилит без построения графа), агрегировать reuse-кандидатов с метрикой релевантности и отдавать агенту markdown+JSON пакет для промпта; подсветить, что построение call/import graph выполняет агент.
- [x] `src/claude_workflow_cli/cli.py`, `claude_workflow_cli/data/payload/.claude/hooks/lib_cli.sh`: прокинуть новые параметры контекст-сборки (`--deep-code`, `--reuse-only`, списки директорий/языков) в команду `research`, логировать путь к сгенерированному отчёту и подсвечивать найденные reuse-точки перед запуском агента.
- [x] `tests/test_researcher_context.py`, `tests/test_gate_researcher.py`, `tests/repo_tools/smoke-workflow.sh`: покрыть глубокий режим (поиск функций/классов, reuse-кандидаты, ссылки на тесты), негативные сценарии без совпадений и проверку, что отчёт содержит обязательные секции; убедиться, что payload-копии проходят sync/manifest проверки и что call graph делегирован агенту.
- [x], `AGENTS.md`, `AGENTS.md`, `README.md`, `README.en.md`: описать новый формат работы Researcher (deep-code + reuse), обязательные поля отчёта, примеры интерпретации и как применять рекомендации в план/тасклист; добавить guidance по запуску с фильтрами директорий/языков и явным шагом построения графа на стороне Claude Code.

### Planner: архитектурные принципы и паттерны
- [x] `.claude/agents/planner.md`, `prompts/en/agents/planner.md`, `src/claude_workflow_cli/data/payload/{.claude,prompts/en}/agents/planner.md`: усилить мандат — план обязан опираться на текущую архитектуру (слои/границы модулей), уважать KISS/YAGNI/DRY/SOLID, явно указывать применяемые паттерны (ports/adapters, service layer, CQRS/ES при необходимости) и reuse-точки от Researcher; добавить явные запреты на over-engineering и дублирование.
- [x] `commands/plan-new.md`, `src/claude_workflow_cli/data/payload/commands/plan-new.md`, `prompts/en/commands/plan-new.md`: добавить чеклист «Architecture & Patterns» (границы, зависимости, место для кода, выбранные паттерны, ссылки на reuse), требовать компактный вариант реализации (минимальный жизнеспособный план) и fallback при отсутствии подходящих паттернов.
- [x] `AGENTS.md`, `AGENTS.md`, `README.md`, `README.en.md`: описать рекомендуемый вариант реализации планов — базовый сервисный слой + адаптеры к внешним системам, reuse существующих утилит/клиентов, явное ограничение областей (domain/application/infra), ссылки на паттерны и тестовые стратегии.
- [x] `tests/test_planner_agent.py`, `tests/repo_tools/smoke-workflow.sh`: добавить проверки, что план содержит секцию про архитектурные решения и KISS/YAGNI/DRY, перечисляет reuse-точки и не предлагает избыточных компонентов; обновить smoke-сценарий с примером плана, использующего рекомендованный паттерн (service-layer + adapters).

### Координация выполнения
- [x] Researcher — контекст/CLI: внедрить флаги `--deep-code/--reuse-only/--langs/--paths/--keywords`, вывод топ reuse в stdout, экспорт символов/импортов/тестов в JSON/MD (без call graph), синхронизировать core/tools/payload.
- [x] Researcher — промпты/шаблоны: обновить агента, команду и `research-summary` (RU/EN/payload) с обязательными секциями reuse/паттерны/антипаттерны, шагом построения графа в Claude Code и чеклистом применения.
- [x] Researcher — проверки: дополнить `tests/test_researcher_context.py`, добавить `test_gate_researcher.py`, обновить smoke для deep-скана и статуса; убедиться, что sync/manifest учитывают новые артефакты.
- [x] Planner — промпты/команда: усилить мандат KISS/YAGNI/DRY/SOLID, паттерны service-layer + adapters, reuse-точки, чеклист «Architecture & Patterns», запрет over-engineering; обновить RU/EN/payload.
- [x] Planner — тесты/доки: добавить `tests/test_planner_agent.py`, обновить smoke, задокументировать рекомендованную структуру (domain/app/infra) и применение паттернов в `AGENTS.md`/cookbook/README.
- [x] Payload/релизы: прогнать sync (`scripts/sync-payload.sh`, `tools/check_payload_sync.py`), обновить manifest/tests, удостовериться в корректной сборке CLI/zip без dev-only файлов.

## Wave 39

### Researcher: построение call/import graph
- [x] `src/claude_workflow_cli/tools/researcher_context.py`, `tools/researcher_context.py`, `src/claude_workflow_cli/data/payload/tools/researcher_context.py`: опциональное построение графа вызовов/импортов. Флаги CLI `--call-graph`/`--graph-engine {auto,none,ts}`, сбор ребёр `caller → callee` (file:line, symbol) и импорт-графа; fallback на текущую эвристику, WARN при отсутствии движка.
- [x] `src/claude_workflow_cli/cli.py`: прокинуть флаги call graph в команду `research`, логировать выбранный движок и выводить количество узлов/ребер в stdout; добавить поля `call_graph`/`import_graph` в JSON.
- [x] Опциональный движок tree-sitter: авто-режим только для Java/Kotlin (kt/kts/java); остальные языки анализируются без графа. Fallback при отсутствии зависимости; graceful degrade в офлайне и явное ограничение языков.
- [x] Тесты: `tests/test_researcher_context.py` + фикстур на call graph (kt/java), `tests/test_researcher_call_graph.py` — проверка рёбер, fallback без tree-sitter, негативные кейсы; e2e `tests/test_researcher_call_graph_e2e.py` на реальных `.java/.kt`; обновлён smoke, чтобы проверять наличие `call_graph` в JSON.
- [x] Шаблоны/промпты: обновить `.claude/agents/researcher.md`, `prompts/en/agents/researcher.md`, `docs/research/template.md` (и payload-копии) с разделом «Граф вызовов/импортов»: как строить, что включать (узлы/рёбра, источник engine, ограничение на Java/Kotlin), как интерпретировать риски и reuse.
- [x] Документация:, `AGENTS.md`, `README.md`, `README.en.md`, `AGENTS.md` — описать опцию call graph (когда использовать, параметры CLI, ограничения на языки), примеры вывода и влияние на гейты/планирование.
- [x] Payload/manifest: синхронизировать новые файлы/изменения (tools, шаблоны, промпты, docs), обновить `manifest.json`, `tools/check_payload_sync.py`, smoke в payload.
- [x] Зависимости: добавить optional extra `call-graph` в `pyproject.toml` с `tree-sitter`/`tree-sitter-language-pack`, описать установку через `uv tool install "git+...#egg=claude-workflow-cli[call-graph]"`/`pip install...[call-graph]`, предусмотреть e2e тест под extra.
- [x] Оптимизация графа: добавить фильтры/лимиты (`--graph-filter <regex>`, `--graph-limit <N>`), auto-focus по ticket/keywords и разделение `call_graph_full`/`call_graph` (focus). Обновить CLI, сборщик, промпты/доки, payload и тесты (юнит + e2e) с учётом монорепы, чтобы контекст не раздувался.
  - [x] В контексте сохранять две версии: full (отдельный файл) и focus (фильтрованный по ticket/keywords и лимиту); в `*-context.json` класть только focus.
  - [x] Фильтр/лимит по умолчанию (например, 300 рёбер) с авто-regex `(<ticket>|<keywords>)`; `--graph-filter/--graph-limit/--force-call-graph` для override.
  - [x] Улучшить идентификаторы рёбер: добавлять package/class (FQN) в `caller`/`callee` для Java/Kotlin, чтобы Claude Code мог однозначно интерпретировать graph.
  - [x] Промпты researcher/шаблон отчёта: указать, что используется focus-граф; full брать только при необходимости; описать флаги filter/limit и типовые пресеты для монорепы.
  - [x] Тесты: юнит на фильтрацию/лимит, e2e c tree-sitter + фильтр (проверить, что focus урезан, full сохранён), smoke — что context не превышает лимит и предупреждение выводится при тримминге.

## Wave 40

_Статус: активный, приоритет 3. Цель — после успешного отчёта автоматически формировать задачи для `/feature-dev-aidd:implement` и агента implementer._

### Handoff после отчётов (CLI/агенты)
- [x] `claude_workflow_cli/cli.py`: команда `tasks-derive` (или `handoff`) — читает `reports/qa/{ticket}.json`/`reports/research/{ticket}-context.json`, превращает findings в кандидаты `- [ ]` для `docs/tasklist/<ticket>.md`, поддерживает `--source qa|research`, `--dry-run`, `--append` и выводит дифф/сводку затронутых секций.
- [x] `.claude/agents/qa.md`, `prompts/en/agents/qa.md`: добавить секцию «Actionable tasks for implementer» с маппингом finding → чекбокс (scope, severity, ссылка на отчёт), требовать запуск `tasks-derive --source qa` после READY/WARN и фиксацию `Checkbox updated: …`.
- [x] `.claude/agents/researcher.md`, `commands/researcher.md`, RU/EN payload: включить мандат формировать список доработок (reuse/risks) для implementer и подсказку на автозапуск `tasks-derive --source research` после успешного отчёта.
- [x] `.claude/agents/implementer.md`: описать, что входом служат задачи, сгенерированные из отчётов; требовать ссылку на источник (`reports/qa/...` или research) и обновление `Checkbox updated` по этим пунктам.

### Хуки и гейты
- [x] `.claude/hooks/gate-qa.sh`: опциональный шаг (config `qa.handoff: true`) — после успешного запуска вызывать `tasks-derive --source qa --append`, выводить, какие чекбоксы добавлены; поддержать `CLAUDE_SKIP_QA_HANDOFF`.
- [x] `.claude/hooks/gate-workflow.sh`, `config/gates.json`: расширить `tasklist_progress.sources` новым `handoff`, добавить проверку, что после handoff появились новые `- [x]` либо свежие `- [ ]` с ссылкой на отчёт.
- [x] `claude_workflow_cli/tools` + bash helper: общий хелпер для вызова `tasks-derive` с подсказкой установки (`run_cli_or_hint`), подключить в хуки/скрипты.

### Тесты, payload, документация
- [x] Тесты: `tests/test_tasks_derive.py` — генерация чекбоксов из QA/Review/Research отчётов (ok/warn/block), idempotent append, dry-run; e2e в `tests/repo_tools/smoke-workflow.sh` (готовый отчёт → handoff → implement).
- [x] Payload-sync: обновить `src/claude_workflow_cli/data/payload/**`, `manifest.json`, `tools/check_payload_sync.py`, убедиться, что `tasks-derive` и обновлённые промпты/хуки включены.
- [x] Документация: `README.md`, `README.en.md`, `AGENTS.md`, `docs/tasklist/template.md` — добавить шаг handoff после отчётов, пример вызова `tasks-derive`, формат маппинга finding → чекбокс и роль implementer в закрытии этих пунктов.

## Wave 41

- [x] Implementer — в промпте/гайдах добавить требование фиксировать изменённые файлы в git: перечислять затронутые пути и выполнять `git add` на каждый модуль перед итоговым ответом/итерацией (связь с `Checkbox updated: …`). Обновить RU/EN + payload.
- [x] `.claude/agents/implementer.md`, `prompts/en/agents/implementer.md`, payload: дополнить мандат требованием никогда не включать внутренние служебные файлы из самого ai_driven_dev (payload/шаблоны/хуки/вендорные скрипты) в коммит целевого проекта; перед ответом агент проверяет `git status` и явно подтверждает отсутствие таких путей.
- [x] `.claude/hooks/gate-workflow.sh`, `.claude/hooks/lib_cli.sh`, `config/conventions.json`: добавить проверку/блокировку стейджа/диффа с внутренними служебными файлами ai_driven_dev, выводить подсказку удалить/игнорировать, синхронизировать payload/manifest и автотесты.
- [x] `src/claude_workflow_cli/cli.py`, `init-claude-workflow.sh`, `README.md`: вшить защиту от включения служебных файлов ai_driven_dev в дефолтную установку (`uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git` → `claude-workflow init --target. --commit-mode ticket-prefix --enable-ci`), обновить smoke/CLI тесты, чтобы после init `git status` не содержал этих путей. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)

## Wave 42

- [x] QA агент и команда `/feature-dev-aidd:qa`: обязать запускать все необходимые тесты (по конфигу/диффу), фиксировать результаты/логи и метки READY/WARN/BLOCKED в `docs/tasklist/<ticket>.md` c ссылкой на отчёт `reports/qa/<ticket>.json`, чтобы имплементер мог подобрать следующие задачи.
- [x] Формат отчёта QA: добавить поля `tests_executed` (команда → статус → лог/URL) и `tests_summary` (pass/fail), чтобы `tasks-derive` мог создавать чекбоксы «QA tests».
- [x] `scripts/qa-agent.py`: эвристика «тесты не запускались/нет логов» → WARN/BLOCKED, чтобы гейт не пропускал пустой QA; учитывать новые поля отчёта.
- [x] `.claude/hooks/gate-qa.sh`, `config/gates.json`, `src/claude_workflow_cli/cli.py`: enforce автозапуск тестов в QA-стадии (reuse `.claude/hooks/format-and-test.sh` или отдельный блок `qa.tests`), писать команды/логи в отчёт, проверять наличие записей в tasklist после проверки, включить подсказку и автоматический handoff (`tasks-derive --source qa --append`) в вывод CLI/гейта.
- [x] `.claude/agents/qa.md`, `prompts/en/agents/qa.md`, payload: обновить мандат/формат ответа — перечислять прогнанные тесты (команда → результат → лог), фиксировать READY/WARN/BLOCKED и новые чекбоксы/ссылки на `reports/qa/<ticket>.json` в tasklist; sync RU/EN, добавить автотесты.
- [x] CLI/гейты: `claude_workflow_cli/cli.py`, `.claude/hooks/gate-qa.sh`, `config/gates.json` — добавить поддержку `progress --source handoff`, блокировку QA, если handoff/tasklist не обновлены, и флаги override (`CLAUDE_SKIP_QA_HANDOFF`, `CLAUDE_QA_ALLOW_NO_TESTS`) с понятными подсказками.
- [x] Тесты/доки: дополнить `tests/test_gate_qa.py`, `tests/test_qa_agent.py`, `tests/test_tasks_derive.py`, `tests/repo_tools/smoke-workflow.sh` сценариями «QA запускает тесты, пишет логи, handoff обновляет tasklist, progress проходит/проваливается без `[x]`»; обновить /`README`/`AGENTS.md` с примерами команд, формата отчёта и минимальным чеклистом логов.

## Wave 43

- [x] CLI `analyst` (обёртка для агента, auto-mode по дефолту) _(закрыто за ненадобностью)_
  - [x] `src/claude_workflow_cli/cli.py`: добавить subcommand `analyst` (поля: `--ticket/--feature`, `--slug-hint`, `--target`, `--auto`, `--note`, проброс в аналитический агент или скрипт); graceful ошибка с INSTALL_HINT при отсутствии payload/скрипта.
  - [x] `prompts/en/commands/idea-new.md`, `commands/idea-new.md`: синхронизировать инструкции (автозапуск analyst после research, пример CLI).
  - [x] Документация: README/README.en/workflow/docs/agents-playbook — обновить разделы quick-start/commands, убрать устаревшие предупреждения; отметить auto-mode и связь с `analyst-check`.
  - [x] Тесты/смоук: добавить сценарий `claude-workflow analyst --ticket demo --auto` (использует demo payload) в `tests/repo_tools/smoke-workflow.sh` и/или unit на парсер; убедиться, что `invalid choice: 'analyst'` больше не воспроизводится.

- [x] CLI `tasks-new` (создание tasklist из шаблона/пресета, упоминания устранить) _(закрыто за ненадобностью)_
  - [x] `src/claude_workflow_cli/cli.py`: добавить subcommand `tasks-new` (опции: `--ticket/--feature`, `--slug-hint`, `--target`, `--force`, `--template/docs/tasklist/template.md`, опционально `--preset feature-plan/impl`), генерировать `docs/tasklist/<ticket>.md` с заполнением placeholders; при конфликте — бэкап/skip и понятное сообщение.
  - [x] Обновить `commands/tasks-new.md`, `prompts/en/commands/tasks-new.md` под фактический CLI (аргументы, побочные эффекты, примеры), синхронизировать payload-копии/manifest.
  - [x] Документация: README/README.en/workflow/docs/agents-playbook — заменить упоминания ручного копирования tasklist на вызов `tasks-new`, добавить troubleshooting (если файл уже есть/отредактирован).
  - [x] Тесты/смоук: e2e сценарий `claude-workflow tasks-new --ticket demo` → файл создан из шаблона, повторный запуск с `--force`/без — ожидаемое поведение; unit на парсер/конфликты; проверить, что `invalid choice: 'tasks-new'` устранён.

## Wave 44

_Статус: активный, приоритет 2. Цель — устойчивые идентификаторы фичи/тикета и гейты, не падающие из-за длинных/многострочных названий._

### Идентификаторы и CLI
- [x] `src/claude_workflow_cli/feature_ids.py`, `src/claude_workflow_cli/cli.py`: добавить `safe_identifier/slug` (обрезка до безопасной длины, одна строка, замена пробелов/переводов строк на `-`, короткий хэш при усечении); применять при `write_identifiers`, `resolve_identifiers`, init/idea-new flow, чтобы `.active_ticket/.active_feature` всегда были валидными для путей.
- [x] Сохранять исходный запрос пользователя (raw ticket/slug) рядом с оптимизированным: писать raw в отдельный файл/поле (`.active_ticket_raw` или metadata) для агентов/LLM, а во все путевые подстановки использовать только сжатый `safe_slug`; в логах/ответах подсвечивать маппинг raw → compressed.
- [x] `.claude/hooks/format-and-test.sh` и гейты (`gate-qa/tests/workflow`): нормализовать `{ticket}/{slug}` перед подстановкой в пути (`reports/reviewer/...`, `reports/qa/...`), добавлять fallback-хэш и понятный WARN, если исходный идентификатор слишком длинный/многострочный; перехватывать OSError при работе с путями и выводить инструкцию, как поправить ticket.
- [x] CLI/скрипты: добавить флаг/команду `--sanitize-identifiers` или авто-фиксацию при запуске хуков, которая переписывает существующие `.active_ticket/.active_feature` в безопасный вариант и выводит маппинг `original → safe`.
- [x] Зафиксировать единые правила sanitize (лимиты длины, допустимые символы, алгоритм хэша, поведение при коллизиях) и применять их для ticket/slug во всех точках (tasklist/PRD/reports/smoke), чтобы вывод/логи показывали raw, а файловые пути — safe.
- [x] Обновить промпты/CLI help для команд/агентов (`idea-new`, `implementer`, и т.п.), чтобы LLM читала raw идентификатор из metadata и подставляла safe в пути/команды; описать это в payload-копиях.
- [x] Добавить миграцию: скрипт или авто-rename старых артефактов (`reports/reviewer/<long>.json` и др.) в safe-пути; предусмотреть идемпотентность и подсказку пользователю.

### Документация и инструкции
- [x] `commands/idea-new.md`, `prompts/en/commands/idea-new.md`, `README.md`/`AGENTS.md`: явно требовать короткий ticket/slug (1 строка, до 80 символов, латиница/цифры/`-`), описать auto-sanitize и что длинные описания должны идти в PRD/idea, а не в идентификатор.
- [x] Troubleshooting: добавить раздел «File name too long / OSError в reviewerGate» с шагами (sanitize, переустановить slug, удалить проблемный отчёт), обновить payload-копии.
- [x] Уточнить формат хранения raw (путь/JSON-метаданные), кто его читает (агенты/CLI), и как обновляется при переактивации фичи.
- [x] UX/валидаторы: при вводе тикета предупреждать о многострочности/UTF/длине, показывать превью safe-slug до записи, чтобы избежать сюрпризов.
- [x] Обратимость: описать rollback на сырой ticket/slug (CLI `set-feature --ticket RAW --keep-safe` или вручную) и сохранять историю переименований в `reports/identifier_migrations.json` для сопоставления артефактов/отчётов.

### Тесты и смоук
- [x] `tests/test_feature_ids.py`, `tests/test_format_and_test_hook.py` (или новый): кейсы с длинным/многострочным тикетом → safe slug + хэш, отсутствие OSError, корректный путь к `reports/reviewer/...`.
- [x] `tests/repo_tools/smoke-workflow.sh`: сценарий с намеренно длинным описанием тикета → auto-sanitize, успешный запуск хуков/тестов; убедиться, что логи содержат подсказку и что отчёты создаются по safe-имени.
- [x] Тесты на идемпотентность sanitize и на корректный вывод маппинга raw → safe в логах/контексте агентов; e2e миграцию существующего проблемного тикета/репортов.

## Wave 46

_Статус: активный, приоритет 1. Перенос из Wave 27 — плагин AIDD, нормализация команд/агентов, официальные хуки и обновление документации._

### Официальные команды/агенты и плагин AIDD
- [x] Нормализовать `/idea /feature-dev-aidd:researcher /plan /review-prd /tasks /feature-dev-aidd:implement /feature-dev-aidd:review /feature-dev-aidd:qa` в плагинном каталоге `.claude-plugin/commands/` с единым фронтматтером (`description/argument-hint/allowed-tools/model/disable-model-invocation`, позиционные `$1/$2`, ссылки `@docs/...`), убрать кастомные поля, обновить quick-reference, prompt-lint и `manifest.json`/sync-проверки под новые пути.
- [x] Переписать `.claude/agents/*.md` и EN-копии в формат плагина (`description/capabilities`, блоки «Роль/Когда вызывать/Как работать с файлами/Правила», статусы READY/BLOCKED/WARN, ссылки на артефакты validator/qa/prd-reviewer), синхронизировать версии RU/EN и линтеры.
- [x] Собрать плагин `feature-dev-aidd` (`.claude-plugin/plugin.json`, `commands/`, `agents/`, `hooks/hooks.json`, при необходимости `.mcp.json`), включить его в payload/manifest, обновить init/sync/upgrade и тесты/CI, чтобы плагин разворачивался вместе с `aidd/`.
- [x] Привести фронтматтер команд/агентов к требованиям Claude Code (обязательные `description/argument-hint/name/tools/model/permissionMode`, позиционные `$1/$ARGUMENTS`, минимальные `allowed-tools`), зашить проверки в prompt-lint и quick-reference с короткими шаблонами.
- [x] Обновить README/README.en/quick-reference под плагин `feature-dev-aidd`: таблица команд с аргументами и @docs артефактами, упоминание `.claude-plugin`, обновить sync-даты.

### Хуки и гейты (официальные события)
- [x] Спроектировать плагинные hook events (PreToolUse/PostToolUse/UserPromptSubmit/Stop/SubagentStop) через `hooks.json`: workflow-gate (PRD/plan/tasklist), tests/format, anti-vibe prompt-gate, QA, post-write `tasks-derive`/`progress`, учесть `config/gates.json` и dry-run.
- [x] Переписать bash-хуки под новый конфиг (убрать лишние заглушки дополнительных гейтов), подключить общий helper и новые события; синхронизировать payload/manifest и sync-проверки.
- [x] Обновить unit/smoke проверки хуков (`tests/test_gate_workflow.py`, `tests/test_gate_tests_hook.py`, `tests/test_gate_qa.py`, `tests/repo_tools/smoke-workflow.sh`) под плагинные пути и сценарии PostToolUse/PostWrite.

### Marketplace и запуск плагина из корня
- [x] Добавить корневой `.claude-plugin/marketplace.json` c `source: "./aidd"` и плагином `feature-dev-aidd`.
- [x] Обновить настройки автоподключения плагина (root `.claude/settings.json` с `extraKnownMarketplaces` и `enabledPlugins`), чтобы при запуске из корня плагин подключался автоматически.
- [x] Переписать `aidd/.claude-plugin/hooks/hooks.json` на `${CLAUDE_PLUGIN_ROOT}/…` для всех команд, чтобы хуки работали при установке в подпапку.
- [x] Проверить/уточнить пути в `aidd/.claude-plugin/plugin.json` (commands/agents/hooks с `./`), учесть размещение файлов в корне плагина.
- [x] Обновить init/sync/upgrade: генерация marketplace и настроек при установке в `aidd/`, включить в payload manifest.
- [x] Тесты: e2e init → marketplace+enabledPlugins; lint/manifest на marketplace; smoke с CWD=корень и плагином в `aidd/`, проверки `${CLAUDE_PLUGIN_ROOT}` в хуках.
- [x] Дока: README/workflow/agents-playbook — раздел про запуск из корня с плагином в `aidd/`, шаги доверия/установки marketplace.

### Структура payload AIDD под схему плагина
- [x] Перенести плагинные команды/агенты/хуки из `aidd/.claude-plugin/{commands,agents,hooks}` в корень плагина `aidd/{commands,agents,hooks}`, поправить `plugin.json` на пути `./commands/`, `./agents/`, `./hooks/hooks.json`.
- [x] Обновить `aidd/.claude-plugin/hooks/hooks.json`: использовать `${CLAUDE_PLUGIN_ROOT}` для ссылок на bash-хуки/скрипты, убрать привязку к путям workspace.
- [x] Развести плагинные файлы и runtime `.claude`: в `.claude` оставить настройки/хуки проекта, в плагине — только команды/агенты/плагинные хуки; убрать дубликаты.
- [x] После перевода валидаторов/гейтов/линтов на `aidd/{commands,agents}` удалить дубли команд/агентов из `aidd/.claude/` (IDE runtime) и очистить проверки, которые их требуют.
- [x] Обновить init/sync/manifest под новую структуру (копирование новых путей, hash в manifest.json).
- [x] Тесты/smoke/prompt-lint: учесть новые пути команд/агентов/хуков и переменную `${CLAUDE_PLUGIN_ROOT}`; добавить smoke-кейс установки и работы хуков при CWD=корень.
- [x] Документация: README/workflow/agents-playbook — описать новую структуру плагина в `aidd/` и различие между `.claude` (runtime) и `commands/agents/hooks` (плагин).

### Документация и CLAUDE.md
- [x] Обновить гайды (`aidd/workflow.md`,, текущая статья) с примерами `$1/$ARGUMENTS`, `argument-hint`, `@docs/...`, схемой hook events и установкой плагина в поддиректорию `aidd/`.
- [x] Добавить ссылки на `AGENTS.md` и `config/conventions.md` в `aidd/CLAUDE.md`, вписав в существующий текст без перетирания содержимого.
- [x] Пересобрать quick-start/quick-reference (RU/EN) под плагинную раскладку и новые пути, синхронизировать с README/workflow и manifest/payload тестами.
- [x] Включить в prompt/agents playbook краткие шаблоны команды и агента (по официальной доке: фронтматтер, positional args, allowed-tools), дать ссылки на slash-commands/subagents и community-примеры для копипасты.

### Тестирование и фиксация Wave 46
- [x] После обновления хуков/смоука прогнать `python -m pytest tests/test_gate_workflow.py tests/test_gate_tests_hook.py tests/test_gate_qa.py` и `tests/repo_tools/smoke-workflow.sh`; зафиксировать результаты.
- [x] При изменениях в payload/хуках обновить `src/claude_workflow_cli/data/payload/manifest.json` (payload sync) и отметить чекбокс Wave 46.
- [x] Привести все пути артефактов к `aidd/docs/**` вместо `./docs/**`: обновить хуки, агенты, команды и шаблоны, чтобы они читали/писали в подпапку плагина.
- [x] Гарантировать наличие шаблонов: добавить в payload/manifest `aidd/docs/research/template.md` (и другие используемые шаблоны) либо fallback-генерацию минимальной заготовки при отсутствии файла.
- [x] Исправить ссылки на скрипты в хуках: использовать `${CLAUDE_PLUGIN_ROOT}/scripts/...` (например, `prd_review_gate.py`) и убедиться, что `aidd/scripts/**` копируются при init/sync.
- [x] Добавить префлайт автосоздание артефактов (PRD/Research) перед вызовом агентов/хуков: если нет `aidd/docs/research/<ticket>.md` или `aidd/docs/prd/<ticket>.prd.md`, создать из шаблона или пустой заготовки; покрыть тестом/smoke.

## Wave 47

### Разделение настроек проекта и плагина (Claude Code)
- [x] Перенести скрипты из `aidd/.claude/hooks/*.sh` и gradle-helper из `aidd/.claude/gradle/` в плагинные каталоги (`aidd/hooks` или `aidd/scripts`), обновить ссылки на них через `${CLAUDE_PLUGIN_ROOT}/hooks` и удалить `.claude` из корня плагина.
- [x] Обновить `aidd/.claude-plugin/plugin.json` и `aidd/hooks/hooks.json` под новые пути, исключить обращения к путям workspace, оставить только `${CLAUDE_PLUGIN_ROOT}` для плагинных хуков.
- [x] Скорректировать `aidd/init-claude-workflow.sh`: не копировать `.claude` изнутри плагина, копировать проектные `.claude/**` из payload root, сохранять генерацию marketplace в `/.claude-plugin/` и ссылку на подпапку `aidd/`.
- [x] Привести тесты/tools, которые проверяют наличие хуков/gradle helper, к новой раскладке (путь в плагине вместо `.claude`), дополнить smoke-кейс запуском хуков при CWD=корень репо.
- [x] Документация (`README*`, `AGENTS.md`, `aidd/CLAUDE.md`): явное разделение project `.claude/` vs plugin `.claude-plugin/`, примеры подключения marketplace из подпапки `aidd/`, новые пути хуков.

### Аудит и чистка дистрибутива
- [x] Провести ревизию payload/distro: какие файлы должны ставиться пользователю (hooks, tools, prompts, scripts), какие остаются dev-only; зафиксировать критерии (назначение, зависимость в командах/хуках/CI) и вывод в отдельной заметке.
- [x] Добавить автоматическую проверку состава дистрибутива: allowlist/denylist для `aidd/tools`, `scripts`, `commands/agents/hooks`, защитный тест или `scripts/check-payload-contents.sh`, который валит CI при появлении лишних/неиспользуемых файлов.
- [x] Обновить manifest генератор и `tools/check_payload_sync.py`/tests так, чтобы они опирались на новый список обязательных артефактов и подсвечивали осиротевшие файлы.
- [x] Payload audit: использовать `python3 tools/payload_audit.py` (без CLI/make), запускать после `sync --direction=from-root` и перед релизом; включить в release pipeline.
- [x] Обновить документацию (README/README.en/AGENTS.md) и release checklist с правилами: что считается runtime-артефактом, что dev-only, как проводить аудит перед тэгом и где оставлять решение по удалённым файлам.
- [x] Оставить единый `aidd/init-claude-workflow.sh` в payload, убрать корневой дубликат и перевести smoke/tests/docs на путь из payload.

## Wave 48

_Статус: новый, приоритет 3. Цель — аудит и упорядочивание корня репозитория (dev-only артефакты, дубли документации)._

- [x] Провести инвентаризацию корневых каталогов (`AGENTS.md`, `docs/`, `scripts/`, `tools/`, `CLAUDE.md`), составить таблицу dev-only vs дистрибутив и отметить, что реально нужно пользователю.
- [x] Убрать/переместить dev-only материалы (design/feature-presets, backlog и пр.) в `AGENTS.md` (а backlog — в корень); обновить ссылки из README/CONTRIBUTING, чтобы не было битых путей после чистки.
- [x] Обновить gitignore/manifest/payload sync так, чтобы корневые dev-only файлы не попадали в релизы и установки; добавить чек в `tools/check_payload_sync.py` или новый `scripts/check-root-audit.sh`.
- [x] Документация: README/README.en/CONTRIBUTING — раздел «Состав репозитория» с явным перечислением, что остаётся в корне, что ставится пользователю, куда смотреть dev-доки.
- [x] Repo-only tooling: вынести `sync-payload.sh`, `lint-prompts.py`, `prompt-version`, `check_payload_sync.py`, `payload_audit.py` из payload, обновить docs/tests/manifest и дефолтный sync.
- [x] Repo-only tooling: убрать `aidd/tests/repo_tools/ci-lint.sh` из payload, перенести его проверки в корневой `tests/repo_tools/ci-lint.sh`, обновить упоминания в доках/промптах, manifest и проверки payload.
- [x] Удалить корневой `init-claude-workflow.sh`, обновить примеры установки и `examples/apply-demo.sh` на запуск из payload.

## Wave 49

_Статус: новый, приоритет 1. Цель — починить базовый флоу `/feature-dev-aidd:idea-new` и пути плагина Claude Code, чтобы гейты работали без ложных блокировок._

### Пути и документация
- [x] `src/claude_workflow_cli/data/payload/aidd/CLAUDE.md`: убрать двойные ссылки `aidd/aidd/**`, оставить корректные пути `aidd/docs/**`, уточнить упоминания хуков на `${CLAUDE_PLUGIN_ROOT}`.
- [x] `src/claude_workflow_cli/data/payload/aidd/agents/implementer.md`, `.../agents/reviewer.md`: исправить путь к автохуку на `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` (или `${CLAUDE_PLUGIN_ROOT}`), убрать дубли путей workspace.
- [x] `src/claude_workflow_cli/data/payload/aidd/commands/idea-new.md` и EN-версия: зафиксировать порядок `/feature-dev-aidd:idea-new → analyst → /feature-dev-aidd:researcher при необходимости`, оставить research как опциональный шаг с примерами `--paths/--keywords`.
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/hooks.json`: заменить ссылки на хуки только на `${CLAUDE_PLUGIN_ROOT}/.claude/hooks/...` без fallback на пути workspace, в соответствии с документацией Claude Code.

### Хуки и гейты
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/hooks.json`: добавить блок `PostToolUse` с `format-and-test.sh` и `lint-deps.sh`, убедиться, что `PreToolUse`/`Stop`/`SubagentStop` ссылаются на `${CLAUDE_PLUGIN_ROOT}/.claude/hooks/*.sh`.
- [x] `src/claude_workflow_cli/data/payload/aidd/.claude/hooks/gate-workflow.sh`: скорректировать автодетект корня (`./aidd` при запуске из родителя), уточнить чтение `Status:` только в секции диалога analyst, добавить понятное сообщение, если PRD остаётся draft при готовом PRD review.
- [x] `src/claude_workflow_cli/data/payload/aidd/.claude/hooks/_vendor/claude_workflow_cli/tools/analyst_guard.py`: автоподстановка `--target aidd` при отсутствии `docs/`, исключить ложные BLOCK из-за повторных `Status:` в других разделах, писать в вывод, откуда взят статус.

### Тесты и смоук
- [x] `tests/test_gate_tests_hook.py` (и новые тесты): проверить наличие `PostToolUse` команд и корректные пути (`gate-tests.sh`, `format-and-test.sh`, `lint-deps.sh`), сценарий idea-new без research → analyst требует research → после reports/research READY гейт пропускает план/код.
- [x] `tests/repo_tools/smoke-workflow.sh`: добавить кейс запуска из корня без `docs/` (используется `aidd/docs`), убедиться, что хуки не падают по отсутствующим путям и что `format-and-test`/`lint-deps` срабатывают после записи.

## Wave 50

_Статус: новый, приоритет 1. Цель — сделать `/feature-dev-aidd:idea-new` единым сценарием: аналитик + при необходимости авто-research + список вопросов пользователю, без рассинхронов и неправильных путей._

### Перенастройка /feature-dev-aidd:idea-new и аналитика
- [x] Переписать `/feature-dev-aidd:idea-new`: единый сценарий с авто-запуском аналитика, авто-research при тонком контексте (`--auto-research/--no-research`), пути `.active_*`/PRD/research печатаются в выводе, READY только после ответов.
- [x] Обновить агент `analyst`: не ставит READY без ответов, инициирует research при нехватке данных, заполняет блок вопросов к пользователю и ссылки на research/PRD, логирует прочитанные артефакты/slug.
- [x] Скорректировать `analyst_guard`/gate сообщения: fallback на `aidd/docs` с WARN, BLOCKED/PENDING допустимы после идеи, план/код требуют READY + reviewed research; подсказки про `--target aidd`.

### Пути и источники тикета
- [x] Убедиться, что все команды/агенты/gates используют `.active_ticket/.active_feature` из `docs/` или `aidd/docs/` (fallback), как в обновлённом `set_active_feature.py`; добавить проверки и WARN, если cwd не совпадает. *(регрессы: хуки/CLI/tests читают `docs/.active_*` под aidd; добавлен тест с legacy `./docs` + пустым CLAUDE_PLUGIN_ROOT)*.
- [x] При необходимости обновить `config/gates.json` (фоллбек на `aidd/docs/.active_*`), чтобы исключить рассинхроны при запуске из корня без `docs/`. *(протестировано через хуки с legacy `./docs`, CLAUDE_PLUGIN_ROOT="" → используются только `aidd/docs` активные маркеры)*.

### Тесты и smoke
- [x] Добавить тесты: (а) запуск `/feature-dev-aidd:idea-new` в корне без `docs/` (используется `aidd/docs`, `.active_*` пишутся корректно); (б) тонкий контекст → авто research → PRD остаётся BLOCKED с вопросами; (в) достаточно контекста → без research, READY после ответов. _(покрыто регрессами `gate-workflow`: aidd fallback + reviewed research блокировки + rich-context без auto-research)._
- [x] Обновить `tests/repo_tools/smoke-workflow.sh`: сценарий `/feature-dev-aidd:idea-new` с авто-analyst+auto-research, подтверждение корневого запуска без `docs/`, готовность после ответов/исправлений.

### Документация/промпты
- [x] Обновить `commands/idea-new.md` (RU/EN) и промпты агента analyst под новый порядок: единый сценарий, research опционален, вопросы к пользователю обязательны перед READY.
- [x] Добавить troubleshooting: “PRD draft/analyst blocked” → проверить путь `.active_*`, наличие research, использовать `--target aidd`.

## Wave 51

_Статус: новый, приоритет 1. Цель — отказаться от опционального `--target`: всегда ставим/используем payload в `aidd/`, пути фиксированы во всех инструментах, хуках и документации._

### Фикс багов
- [x] `aidd/hooks/hooks.json` + все гейты: требовать `CLAUDE_PLUGIN_ROOT`, вычислять корень из `cwd`/`aidd`, выдавать явное сообщение вместо блокировки записи.
- [x] `aidd/.claude/hooks/gate-workflow.sh`, `aidd/.claude/hooks/lib.sh`: убрать смешение `docs/` и `aidd/docs/`, запретить создание артефактов в обоих местах, логировать WARN при чужом `cwd`, единообразно резолвить `ROOT_DIR=<workspace>/aidd`.
- [x] `aidd/docs/tasklist/*.md` + прогресс: выровнять путь/формат чекбоксов с gate (без дублей дат), добавить тест, что `progress` видит задачи и не пишет мусор при обновлении.
- [x] Тесты/смоук: сценарий записи файла при пустом `CLAUDE_PLUGIN_ROOT` и запуске из корня — хуки не падают, блокируют только по делу; добавить кейс с дублирующими `docs/`/`aidd/docs/`.
- [x] Агенты/команды: заменить ссылки на хуки/скрипты (`format-and-test.sh`, `gate-qa.sh`, `set_active_feature.py`) на `${CLAUDE_PLUGIN_ROOT}/...`, убрать `./aidd` и workspace-пути из bash-инструкций; обновить описание запуска (примеры в md); регенерировать manifest после правок и прогнать markdownlint/pytest (по желанию).
- [x] Пути `.active_*` и отчётов: унифицировать резолвинг root через `${CLAUDE_PLUGIN_ROOT}` (`scripts/prd-review-agent.py`, `scripts/qa-agent.py`, payload-версии и `tools/set_active_feature.py`/`feature_ids.py`), убрать советы `--target.` в командах (`review-prd.md`, `qa.md`, `researcher.md`), гарантировать запись только в `aidd/docs`/`aidd/reports` даже при наличии `./docs`; обновить manifest/тесты/smoke.
- [x] Скрипты/хуки: заменить жёсткие `./aidd/...` в bash/python скриптах на `${CLAUDE_PLUGIN_ROOT}/...`, добавить fallback внутри скриптов на этот префикс; обновить manifest и прогнать lint/pytest.
- [x] Резолвер корня для скриптов: вынести/синхронизировать `detect_project_root` (кандидаты `${CLAUDE_PLUGIN_ROOT}` → `cwd/aidd` → `cwd`), использовать в `scripts/prd-review-agent.py`, `scripts/qa-agent.py`, `scripts/prd_review_gate.py` и payload-копиях; добавить быстрый тест на порядок кандидатов.
- [x] Сообщения PRD-гейта: обновить тексты/примеры путей на `aidd/docs/prd/<ticket>.prd.md`, при необходимости логировать фактический `root`, чтобы избежать путаницы с workspace `./docs`.
- [x] Синхронизация payload: пересобрать manifest после правок скриптов/команд, прогнать проверки состава payload (`tools/check_payload_sync.py`/`tests/test_package_payload.py`) и убедиться, что новые пути зафиксированы.
- [x] PRD review отчёты и сообщения: в `prd-review-agent.py` (оба инстанса) при отсутствии `--report` писать в `<root>/reports/prd/<ticket>.json` (root = `${CLAUDE_PLUGIN_ROOT}`), логировать полный путь; обновить команду/агента `/review-prd` на `${CLAUDE_PLUGIN_ROOT}/reports/prd/...` и примеры CLI с `--target aidd`.
- [x] Reports в промптах/доках: пройти `agents/*.md` и `commands/*.md` (RU/EN) на ссылки `reports/...`/`docs/...` без префикса, заменить на `aidd/reports/...` или `${CLAUDE_PLUGIN_ROOT}/reports/...`; добавить примечание про `--target aidd` в инструкциях. *(сделано для RU-файлов payload; README/EN остаются)*
- [x] Тесты на root и отчёты: добавить регрессии на запуск `claude-workflow research`/`review-prd` из корня воркспейса → отчёты создаются/читаются из `aidd/reports/...`; гейты/агенты видят отчёты там; сообщения CLI содержат полный путь. *(добавлен тест для PRD default path; тест на research из корня ещё не покрыт)*
- [x] Документация/трешутинг: README/workflow/команды — явное упоминание, что все артефакты лежат под `./aidd/...`; добавить совет “Если `Read(reports/...)` не находит файл — смотрите `aidd/reports/...`, используйте `${CLAUDE_PLUGIN_ROOT}`/`--target aidd`”. *(EN/README/workflow обновлены подсказками)*
- [x] Research workspace-relative (только для research): сделать дефолт — резолвить `defaults.paths` относительно рабочего корня (где запущен Claude Code); если root=`aidd`, использовать родителя `aidd/`. Для обратной совместимости оставить флаг `--paths-relative aidd`/маркер в `config/conventions.json` для старого поведения. Остальные команды не менять. Нормализовать paths с учётом workspace и искать call-graph там.
- [x] Research logging/warnings: выводить в CLI, какой root использован (workspace vs aidd), предупреждать включить workspace-relative, если под `aidd/` нет поддерживаемых файлов, но в родителе есть код.
- [x] Research tests: кейсы с проектом `<tmp>/workspace/aidd` и кодом в `<tmp>/workspace/src/...`; запуск `claude-workflow research --target aidd --auto --call-graph` без `--paths` находит файлы/строит call_graph; b/c без флага paths резолвятся от `aidd/`; `--paths../foo` остаётся рабочим.
- [x] Research docs: обновить `/feature-dev-aidd:researcher` и README/workflow (RU/EN) с описанием workspace-relative режима/флага, примерами и трешутингом “граф пуст — включите workspace-relative или передайте абсолютные/../ пути”.

### Жёсткая фиксация таргета `aidd/` в CLI и bootstrap
- [x] `src/claude_workflow_cli/resources.py`, `src/claude_workflow_cli/cli.py`: трактовать `--target` как workspace (по умолчанию `.`) и всегда создавать/искать `<workspace>/aidd`; убрать авто-fallback на родителя/`./.claude`, понятные ошибки при запуске вне `aidd/`, обновить `build_parser` help и все команды (`init/preset/research/analyst-check/...`) на единый контракт.
- [x] `src/claude_workflow_cli/data/payload/aidd/init-claude-workflow.sh` + корневой `init-claude-workflow.sh`: работать строго внутри `aidd/`, убрать зеркалирование `.claude/.claude-plugin` в workspace root, оставить явные сообщения про `CLAUDE_TEMPLATE_DIR` и пути результата; обновить манифест payload.
- [x] Тесты CLI/init: новые проверки «init без `aidd/` → ошибка», «init в workspace → создаёт `aidd/`», покрыть `_resolve_roots/_require_workflow_root` и подсказки по таргету; обновить `tests/test_init_*`, `tests/test_cli_payload.py`, `tests/test_bootstrap_e2e.py`.

### Хуки/инструменты и конфиги с обязательным `aidd/`
- [x] `aidd/hooks/hooks.json`, `aidd/.claude/hooks/gate-workflow.sh`, `aidd/.claude/hooks/lib.sh`: убрать fallback на корневой `docs/`, зафиксировать `CLAUDE_PLUGIN_ROOT` = `<workspace>/aidd`, скорректировать `resolve_script_path/ensure_template` на единственный префикс `aidd/`, добавить WARN при чужом CWD.
- [x] Инструменты/скрипты: `aidd/tools/set_active_feature.py`, `aidd/tests/repo_tools/smoke-workflow.sh`, `aidd/tools/run_cli.py` — дефолт `--target aidd`, жёсткая проверка, WARN/exit при попытке писать в корень; подправить `aidd/config/gates.json` (feature_ticket_source/slug_hint_source → `aidd/docs/.active_*` если запуск из корня).
- [x] Агенты/команды/промпты: пройти упоминания путей и подсказок `--target aidd` (idea-new/researcher/qa/analyst) на предмет любых ссылок на корневой `docs/`, синхронизировать RU/EN и quick-reference.

### Дока и DX
- [x] Обновить `README.md`, `README.en.md`, `AGENTS.md`, `AGENTS.md`, `aidd/`: убрать советы про произвольный `--target`, показать единственную установку `claude-workflow init --target.` → `./aidd`, troubleshooting «CLI не найден/не видит.claude» с ссылкой на фиксированный путь.
- [x] Добавить миграционную заметку: как перевести старые установки с корневым `.claude`/`docs` в `aidd/` (удалить dev-снапшоты, запустить init, перенести активные `.active_*` и артефакты), прописать в release notes и в AGENTS.md (готово после выполнения).

### Тесты/смоук/CI
- [x] Обновить `aidd/tests/repo_tools/smoke-workflow.sh`: убрать сценарий «корень без docs → fallback aidd», добавить проверку на ошибку при неправильном таргете и успешный happy-path только через `aidd/`; синхронизировать вызовы `set_active_feature.py` с новым `--target`.
- [x] Покрыть хуки: `tests/test_gate_workflow.py`, `tests/test_gate_tests_hook.py`, `tests/test_gate_qa.py` — убедиться, что пути резолвятся из `aidd/`, нет попыток читать `./docs`, PostToolUse/PreToolUse команды не используют workspace env.
- [x] Обновить payload/manifest после правок; добавить regression-тест на `resolve_project_root` и отсутствие fallback в `tests/test_resources.py` (или новый тест).


## Wave 53

_Статус: новый, приоритет 1. Цель — убрать `ModuleNotFoundError` у QA-агента и жёстко связать его запуск с установкой CLI через uv/pipx без ручных проверок._

- [x] CLI `claude-workflow qa`: заменить хардкод `python3` на запуск QA-агента через тот же интерпретатор, что и CLI (`sys.executable` + уважение `CLAUDE_WORKFLOW_PYTHON`), чтобы uv/pipx-инсталляции гарантированно видели пакет. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] `scripts/qa-agent.py`: перед импортами добавить fallback в `sys.path` для `.claude/hooks/_vendor` (и `CLAUDE_WORKFLOW_DEV_SRC`), вычислять путь от `${CLAUDE_PLUGIN_ROOT}`/`$PWD`, чтобы агент работал даже при «чистом» системном Python. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Тесты: добавить регрессию, эмулирующую uv/pipx (пакет не установлен в системный `python3`), и проверить, что `claude-workflow qa --emit-json` проходит без `ModuleNotFoundError`; обновить smoke-сценарий/fixtures на прогон QA без доп. установок. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Документация: README/qa-playbook/quick-start — уточнить, что после `uv tool install...` + `claude-workflow init --target aidd --force` QA-агент готов без ручного `pip install`; добавить troubleshoot «CLI не найден»/«ModuleNotFoundError» с новой логикой. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Payload/manifest: после изменений в QA-агенте и путях обновить payload манифест и синк-тесты (`tools/check_payload_sync.py`/`tests/test_package_payload.py`), убедиться, что `_vendor` остаётся в дистрибутиве. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)

## Wave 54

_Статус: новый, приоритет 1. Цель — убрать ложные срабатывания PRD-ревьюера на дженерики._

- [x] `scripts/prd-review-agent.py`, `src/claude_workflow_cli/data/payload/aidd/scripts/prd-review-agent.py`: сузить `PLACEHOLDER_PATTERN`/`collect_placeholders`, чтобы типы с дженериками (`SignatureDefaultResponseDto<T>`, `<K, V>` и т.п.) не считались плейсхолдерами; оставить детекцию реальных заглушек из шаблона PRD (`<...>`, `TODO`, `TBD`).
- [x] Тесты PRD-ревьюера: добавить кейс с настоящим плейсхолдером (ожидается finding) и кейс с дженериком (findings отсутствуют).

## Wave 55

_Статус: новый, приоритет 1. Цель — привести README и основные гайды к актуальному флоу CLI/`aidd/` и убрать лишние повторы._

- [x] `README.md` / `README.en.md`: обновить TL;DR и быстрый старт под cli `claude-workflow` (init/preset/sync/upgrade/smoke), добавить компактную справку по командам (analyst-check/research/reviewer-tests/tasks-derive/qa/progress), явно подчеркнуть layout `aidd/` и синхронизировать Last sync.
- [x] `src/claude_workflow_cli/data/payload/aidd/workflow.md`: исправить дубли `aidd/aidd` в путях, переформатировать таблицу этапов/шаги под единый `aidd/` корень и текущее прохождение гейтов/hand-off.
- [x] `src/claude_workflow_cli/data/payload/aidd/conventions.md`: привести ссылки на артефакты к `aidd/docs/**`, сократить дубли и обновить тезисы про базовые гейты/тесты.

## Wave 56

_Статус: новый, приоритет 1. Цель — контекст‑GC через хуки Claude Code (Working Set + контекст‑файрвол) без ручных правок settings.json._

### Конфиг и артефакты контекст‑GC
- [x] `src/claude_workflow_cli/data/payload/aidd/config/context_gc.json`: добавить дефолтный конфиг (лимиты transcript, рабочий набор, guard'ы Bash/Read), описать переключатели `enabled`, `hard_behavior`, `ask_instead_of_deny`.
- [x] `aidd/reports/context/`: определить структуру снапшотов (`<session_id>/working_set.md`, `precompact_meta.json`, `transcript_tail.jsonl`, `latest_working_set.md`) и гарантировать создание директорий из hook‑скриптов.

### Скрипты context‑GC (плагин)
- [x] `src/claude_workflow_cli/data/payload/aidd/scripts/context_gc/hooklib.py`: общий helper для чтения stdin JSON, поиска `aidd`‑root, загрузки/merge конфига, формирования ответов hook API (SessionStart/UserPromptSubmit/PreToolUse).
- [x] `src/claude_workflow_cli/data/payload/aidd/scripts/context_gc/working_set_builder.py`: сбор Working Set из `.active_ticket/.active_feature`, PRD/research/tasklist, git status; лимиты на размер/кол-во задач/обрезку code blocks.
- [x] `src/claude_workflow_cli/data/payload/aidd/scripts/context_gc/precompact_snapshot.py`: снимать Working Set + метаданные + tail transcript до compact, писать в `aidd/reports/context`.
- [x] `src/claude_workflow_cli/data/payload/aidd/scripts/context_gc/sessionstart_inject.py`: вставлять Working Set через `additionalContext` при `SessionStart`.
- [x] `src/claude_workflow_cli/data/payload/aidd/scripts/context_gc/userprompt_guard.py`: soft‑warn/hard‑block по размеру transcript (настройки из `context_gc.json`).
- [x] `src/claude_workflow_cli/data/payload/aidd/scripts/context_gc/pretooluse_guard.py`: guard для Bash (wrap → log + tail) и Read (ask/deny для больших файлов), учитывать regex allow/skip.

### Подключение hooks
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/hooks.json`: добавить `PreCompact` и `SessionStart` (context snapshots + inject), `UserPromptSubmit` (context guard рядом с gate-workflow), `PreToolUse` (Bash|Read) без конфликта с существующим `Write|Edit`.
- [x] Обновить описания в `src/claude_workflow_cli/data/payload/aidd/CLAUDE.md` или `.../AGENTS.md`: что такое Working Set, где лежат отчёты, как менять лимиты/отключать guard'ы.

### Упаковка, синк и тесты
- [x] `src/claude_workflow_cli/data/payload/manifest.json`: включить новые файлы `scripts/context_gc/**` и `config/context_gc.json`; прогнать `python3 tools/check_payload_sync.py`.
- [x] Тесты: добавить unit‑кейсы на `working_set_builder` (лимиты, сбор задач, git status), `userprompt_guard` (soft/hard thresholds) и `pretooluse_guard` (updatedInput/deny/ask).
- [x] Smoke‑сценарий: зафиксировать ручную проверку `/compact` → снапшот → новый SessionStart с Working Set, и проверку wrapper'а для `docker logs`/`Read` больших файлов.

### Контекст‑лимиты по токенам (128k)
- [x] `src/claude_workflow_cli/data/payload/aidd/config/context_gc.json`: добавить `context_limits` (mode=tokens, max_context_tokens=128000, buffer/reserve, warn/block проценты), увеличить `working_set.max_chars` до 10–12k, `max_tasks`/`max_open_questions`, `read_guard.max_bytes`, `bash_output_guard.tail_lines`; оставить bytes‑лимиты как fallback.
- [x] `src/claude_workflow_cli/data/payload/aidd/scripts/context_gc/hooklib.py`: расширить `DEFAULT_CONFIG` под `context_limits` и новые дефолты.
- [x] `src/claude_workflow_cli/data/payload/aidd/scripts/context_gc/userprompt_guard.py`: перейти на токены из последней main‑chain записи transcript (input + cache tokens), применить warn/block по `context_limits`, оставить bytes‑fallback.
- [x] `tests/test_context_gc.py`: добавить тесты на token‑mode (warn/block), включая парсинг JSONL из transcript и fallback на bytes.
- [x] `src/claude_workflow_cli/data/payload/aidd/CLAUDE.md`: описать token‑mode, buffer/reserve и поведение fallback на bytes.
- [x] `src/claude_workflow_cli/data/payload/manifest.json`: обновить size/sha для изменённых файлов и прогнать `python3 tools/check_payload_sync.py`.

## Wave 57

_Статус: новый, приоритет 1. Цель — привести промпты агентов/команд к playbook и устранить рассинхрон статусов, инструментов и форматов._

### Статусы и формат ответа
- [x] Единая модель статусов PRD/планов: привести к `READY/BLOCKED/PENDING` и синхронизировать тексты/проверки в `src/claude_workflow_cli/data/payload/aidd/agents/planner.md`, `src/claude_workflow_cli/data/payload/aidd/agents/validator.md`, `src/claude_workflow_cli/data/payload/aidd/commands/plan-new.md`, `src/claude_workflow_cli/data/payload/aidd/commands/idea-new.md`, `src/claude_workflow_cli/data/payload/aidd/agents/analyst.md`, `src/claude_workflow_cli/data/payload/aidd/`.
- [x] Убрать двусмысленные статусы `READY?BLOCKED`/`BLOCKED?READY` и заменить на явные состояния с правилами перехода (`BLOCKED`/`PENDING` с вопросами → `READY` после ответов) в `src/claude_workflow_cli/data/payload/aidd/commands/idea-new.md` и `src/claude_workflow_cli/data/payload/aidd/agents/analyst.md`.
- [x] Привести формат ответа `Checkbox updated` к единому требованию «первая строка» в `src/claude_workflow_cli/data/payload/aidd/commands/review.md` и сверить остальные команды/агенты на соответствие playbook.

### Инструменты и разрешения
- [x] Выровнять `allowed-tools` команд с реальными требованиями агентов (или наоборот урезать инструкции агента под доступные инструменты): `/feature-dev-aidd:implement`, `/feature-dev-aidd:qa`, `/feature-dev-aidd:review`, `/feature-dev-aidd:idea-new`, `/feature-dev-aidd:researcher` — файлы `src/claude_workflow_cli/data/payload/aidd/commands/*.md` и соответствующие `src/claude_workflow_cli/data/payload/aidd/agents/*.md`.
- [x] Исправить фронт‑маттер analyst: убрать дубли `prompt_version`/`source_version`, удалить несуществующий инструмент `Bash(claude-workflow researcher:*)` и при необходимости добавить корректный `Bash(claude-workflow research:*)` в `src/claude_workflow_cli/data/payload/aidd/agents/analyst.md`.

### Плейсхолдеры, пути и синтаксис команд
- [x] Во всех командах предусмотреть свободный ввод помимо тикета: обновить `argument-hint`, описания в `Контекст`/`Пошаговый план`, использовать `$ARGUMENTS`/`$2` для заметок/подсказок и зафиксировать правила парсинга (без влияния на обязательный `<TICKET>`).
- [x] Заменить HTML‑эскейпы `&lt;ticket&gt;` на `<ticket>` в агентских промптах и привести плейсхолдеры к одному формату: `<ticket>` в агентах, `$1/$2` в командах (затрагивает `src/claude_workflow_cli/data/payload/aidd/agents/{implementer,planner,validator,researcher,prd-reviewer,qa,reviewer}.md` и команды).
- [x] Нормализовать пути отчётов и CLI‑вызовы: единый стиль `${CLAUDE_PLUGIN_ROOT}/reports/...` и `!bash -lc '...'` (например, исправить `src/claude_workflow_cli/data/payload/aidd/commands/qa.md`, `src/claude_workflow_cli/data/payload/aidd/agents/qa.md`, `src/claude_workflow_cli/data/payload/aidd/commands/review-prd.md`).

### Ответственность за tasklist
- [x] Развести ответственность между агентом и командой: либо агент обновляет tasklist и пишет `Checkbox updated:...`, либо это делает команда‑обёртка. Привести к одному подходу `src/claude_workflow_cli/data/payload/aidd/agents/researcher.md`, `src/claude_workflow_cli/data/payload/aidd/agents/prd-reviewer.md`, `src/claude_workflow_cli/data/payload/aidd/commands/review-prd.md`.

### Линтеры, тесты, версии
- [x] Расширить `tests/repo_tools/lint-prompts.py`: проверка дубликатов ключей фронт‑маттера, запрет неизвестных статусов, поиск `&lt;ticket&gt;`, контроль формата `Checkbox updated` и совпадения `allowed-tools` с инструментами агента.
- [x] Обновить тесты `tests/test_prompt_lint.py` и/или `tests/test_prompt_versioning.py` под новые правила; добавить фикстуры на рассинхрон инструментов и дубликаты ключей.
- [x] После правок промптов: увеличить `prompt_version` в затронутых файлах, обновить `src/claude_workflow_cli/data/payload/aidd/AGENTS.md`, `CHANGELOG.md`, `src/claude_workflow_cli/data/payload/manifest.json` и прогнать `python3 tools/check_payload_sync.py`.

## Wave 58

_Статус: новый, приоритет 1. Цель — оптимизировать hook-пайплайн Claude Code (гейты/QA/контекст) и убрать дубли/шум._

### Чистка и корректность гейтов
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/hooks.json`: убрать дублирование PRD-гейта (либо исключить `gate-prd-review.sh`, либо удалить PRD-проверку из `gate-workflow.sh`) и зафиксировать выбранный источник.
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/gate-workflow.sh`: корректно работать при событиях без `file_path` — определять изменения через `git diff`/`git status`, пропускать только при реально «нулевых» изменениях.
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/hooks.json`: пересмотреть события, где запускается `gate-workflow.sh` (UserPromptSubmit/Stop/SubagentStop), оставить только эффективные точки или добавить явные matcher'ы.
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/lib.sh`: расширить `hook_payload_file_path` (fallback на `path`/`filename`/`file` и пустые payload), чтобы гейты устойчиво работали на разных событиях.

### QA и тестовые гейты
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/gate-qa.sh`: убрать дублирование `--gate` и добавить `qa.debounce_minutes` в `config/gates.json`, чтобы не гонять QA на каждом Write/Edit.
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/gate-tests.sh` + `src/claude_workflow_cli/data/payload/aidd/config/gates.json`: вынести языковые правила (пути/расширения/шаблоны тестов) в конфиг и добавить дефолты для non‑JVM проектов.

### Снижение нагрузки и переработка триггеров
- [x] Ввести маркер стадии `aidd/docs/.active_stage` (idea/research/plan/tasklist/implement/review/qa) и утилиту для обновления (расширить `tools/set_active_feature.py` или добавить `tools/set_active_stage.py`); команды `/feature-dev-aidd:idea-new`, `/feature-dev-aidd:plan-new`, `/feature-dev-aidd:tasks-new`, `/feature-dev-aidd:implement`, `/feature-dev-aidd:review`, `/feature-dev-aidd:qa` должны обновлять стадию и позволять откат на любой шаг.
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/hooks.json`: убрать тяжёлые гейты с PreToolUse для обычных Write/Edit, перенести их на `Stop`/`SubagentStop` (запуск только после завершения итерации).
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/format-and-test.sh` + `src/claude_workflow_cli/data/payload/aidd/hooks/hooks.json`: запуск форматирования/тестов только на этапе implement (читаем `aidd/docs/.active_stage`), исключить автозапуск на каждом действии.
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/gate-tests.sh`: запускать только на стадии implement (по `aidd/docs/.active_stage`) и только на `Stop/SubagentStop`, описать override через env.
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/gate-qa.sh`: запускать только на стадии qa (по `aidd/docs/.active_stage`) и только на `Stop/SubagentStop`, описать override через env.
- [x] Полный матчинг стадий и гейтов: зафиксировать матрицу «stage → allowed gates» (idea/research/plan/tasklist/implement/review/qa) и встроить проверку в `gate-workflow.sh`/`hooks.json`.
- [x] `src/claude_workflow_cli/data/payload/aidd/hooks/hooks.json` + `src/claude_workflow_cli/data/payload/aidd/scripts/context_gc/pretooluse_guard.py`: снизить нагрузку на Read/Bash (оставить только лёгкие проверки, либо добавить rate‑limit/skip‑rules в `config/context_gc.json`).

### Полная ревизия хуков
- [x] Провести инвентаризацию всех hook‑событий и команд (PreToolUse/PostToolUse/UserPromptSubmit/Stop/SubagentStop/SessionStart/PreCompact) и зафиксировать, какие реально нужны; сформировать таблицу «нужно/условно/лишнее» и обновить `hooks.json` по итогам.

### Safety hooks
- [x] `src/claude_workflow_cli/data/payload/aidd/scripts/context_gc/pretooluse_guard.py` + `src/claude_workflow_cli/data/payload/aidd/config/context_gc.json`: добавить guard на опасные bash-команды (rm -rf, reset --hard, force push) с режимами ask/deny.

### Тесты и документация
- [x] Обновить тесты/смоук: `tests/test_gate_workflow.py`, `tests/test_gate_tests_hook.py`, `tests/test_gate_qa.py`, `src/claude_workflow_cli/data/payload/aidd/tests/repo_tools/smoke-workflow.sh` под новую логику событий/дебаунса.
- [x] Документация: `src/claude_workflow_cli/data/payload/aidd/workflow.md`, `src/claude_workflow_cli/data/payload/aidd/` — обновить описание точки запуска гейтов и новых guard'ов.
- [x] `src/claude_workflow_cli/data/payload/manifest.json`: обновить контрольные суммы после правок; прогнать `python3 tools/check_payload_sync.py`.

## Wave 59

_Статус: новый, приоритет 1. Цель — зафиксировать SDLC‑контракт, устранить рассинхроны порядка стадий/статусов и переработать промпты под thin‑commands + rich‑agents._

### SDLC контракт и статусы
- [x] Инвентаризировать текущие preconditions/postconditions команд и агентов (команда/агент → входы → выходы → статус → гейты) по файлам `src/claude_workflow_cli/data/payload/aidd/{commands,agents}/*.md`, `src/claude_workflow_cli/data/payload/aidd/hooks/gate-workflow.sh`, `src/claude_workflow_cli/data/payload/aidd/config/gates.json`.
- [x] Зафиксировать канонический порядок стадий (вариант B) с разделением ревью на `/review-plan` → `/review-prd`: `idea → research → plan → review-plan → review-prd → tasks → implement → review → qa`, описать в `src/claude_workflow_cli/data/payload/aidd/docs/sdlc-flow.md` (таблица/диаграмма + ссылки на артефакты).
- [x] Добавить отдельный этап `review-plan`: новый агент/команда (`plan-reviewer` + `/review-plan`), критерии готовности плана и точки отказа до PRD review.
- [x] Создать `src/claude_workflow_cli/data/payload/aidd/docs/status-machine.md`: статусы PRD/Research/Plan/Review/QA, кто выставляет, обязательные артефакты и условия переходов.
- [x] Синхронизировать порядок стадий и ссылки на статусы во всех документах: `README.md`, `README.en.md`, `src/claude_workflow_cli/data/payload/aidd/workflow.md`, `AGENTS.md`, `src/claude_workflow_cli/data/payload/aidd/`, `src/claude_workflow_cli/data/payload/aidd/AGENTS.md`, `src/claude_workflow_cli/data/payload/aidd/` (ссылки на `sdlc-flow.md` и `status-machine.md`).
- [x] Обновить контракт гейтов под новый flow и `review-plan`: `src/claude_workflow_cli/data/payload/aidd/hooks/gate-workflow.sh`, `src/claude_workflow_cli/data/payload/aidd/config/gates.json`, `src/claude_workflow_cli/data/payload/aidd/scripts/prd_review_gate.py`; скорректировать smoke/тесты под новый порядок стадий.
- [x] Ввести `AGENTS.md` в корень репозитория как основной entrypoint; убрать `CLAUDE.md` из целевых артефактов и ссылок в документации/промптах.

### Промпты: thin commands, rich agents
- [x] Сделать команды «тонкими» (оркестрация + контракт) без дублирования алгоритма: `src/claude_workflow_cli/data/payload/aidd/commands/{idea-new,researcher,plan-new,review-plan,review-prd,tasks-new,implement,review,qa}.md` (RU/EN).
- [x] Перенести алгоритм и stop‑conditions в агентов: `src/claude_workflow_cli/data/payload/aidd/agents/{analyst,researcher,planner,plan-reviewer,prd-reviewer,validator,implementer,reviewer,qa}.md` (RU/EN), добавить блоки MUST READ/MUST NOT и границы плана.
- [x] Стандартизировать вопросы пользователю (Blocker|Clarification → зачем → варианты → default) в `analyst`, `validator` (и при необходимости `planner`); обновить `src/claude_workflow_cli/data/payload/aidd/`.
- [x] Нормализовать output‑контракт: единый формат `Checkbox updated` + `Status` + `Artifacts updated` + `Next actions` во всех командах/агентах.
- [x] Рационализировать allowed‑tools (единый способ поиска: Grep или `rg` через Bash) и сузить allowlist для review/qa.

### Handoff‑артефакты и исполняемость
- [x] Research TL;DR: добавить `Context Pack (TL;DR)` и Definition of reviewed в `src/claude_workflow_cli/data/payload/aidd/docs/research/template.md` и синхронизировать `src/claude_workflow_cli/data/payload/aidd/agents/researcher.md`.
- [x] Plan «исполняемый»: добавить обязательные секции (Files/modules touched, test strategy per iteration, feature flags/migrations, observability) в `src/claude_workflow_cli/data/payload/aidd/agents/planner.md`, `src/claude_workflow_cli/data/payload/aidd/agents/validator.md`, `src/claude_workflow_cli/data/payload/aidd/claude-presets/feature-plan.yaml`.
- [x] Tasklist фокус: добавить `Next 3 checkboxes` и `Handoff inbox` в `src/claude_workflow_cli/data/payload/aidd/docs/tasklist/template.md` и `src/claude_workflow_cli/data/payload/aidd/docs/tasklist/template.md`; обновить `/feature-dev-aidd:tasks-new`.
- [x] Traceability: связать PRD acceptance criteria с QA‑проверками в `src/claude_workflow_cli/data/payload/aidd/agents/qa.md`, `src/claude_workflow_cli/data/payload/aidd/`, при необходимости — в `src/claude_workflow_cli/data/payload/aidd/docs/prd/template.md`.

### Governance и проверки
- [x] Расширить `tests/repo_tools/lint-prompts.py`: контроль ссылок на `status-machine.md`/`sdlc-flow.md`, проверка шаблона вопросов в ключевых агентах; обновить `tests/test_prompt_lint.py`.
- [x] Обновить smoke/regression под новый flow: `src/claude_workflow_cli/data/payload/aidd/tests/repo_tools/smoke-workflow.sh`, `tests/test_gate_workflow.py`, `tests/test_prompt_versioning.py`.
- [x] После правок: bump `prompt_version` (RU/EN), обновить `src/claude_workflow_cli/data/payload/aidd/AGENTS.md`, `CHANGELOG.md`, `src/claude_workflow_cli/data/payload/manifest.json`, прогнать `python3 tools/check_payload_sync.py`, синхронизировать root через `scripts/sync-payload.sh --direction=to-root`.
- [x] PRD review: автоматом создавать `reports/prd/` при формировании отчётов и в гейтах (убрать требование ручного `mkdir`).

### Разделение аналитики и research + раздельные гейты
- [x] `/feature-dev-aidd:idea-new` (RU/EN): убрать автозапуск `claude-workflow research`; оставить лёгкий сбор контекста (rg/доки) и явный next step `/feature-dev-aidd:researcher <ticket>`.
- [x] `analyst` (RU/EN): запретить запуск research CLI; добавить блок `## Research Hints` (paths/keywords/notes) в `prd.template.md`, который использует researcher; `analyst-check` запускать только после ответов.
- [x] `/feature-dev-aidd:researcher` (RU/EN): сделать запуск `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph` обязательным; подтягивать `## Research Hints` из PRD; гарантировать создание `docs/research/<ticket>.md` и `Status: reviewed|pending`.
- [x] Разделить гейты: `analyst_guard.py` проверяет только диалог/вопросы/Status (без проверки research); ввести отдельный `claude-workflow research-check` и вызывать его в `/feature-dev-aidd:plan-new`, а research‑gate в `gate-workflow.sh` оставить для code‑changes.
- [x] Обновить статус‑машину: разрешить `PRD READY` без reviewed research, но обязать research‑check перед `/feature-dev-aidd:plan-new`; зафиксировать правило в `status-machine.md` и enforcement через `research-check`, а не analyst‑gate.
- [x] Документация процесса: синхронизировать `AGENTS.md`, `AGENTS.md`, (и payload‑версии) с новым порядком idea → research → plan и раздельными гейтами.
- [x] Smoke/тесты: обновить `src/claude_workflow_cli/data/payload/aidd/tests/repo_tools/smoke-workflow.sh` и/или `tests/test_gate_workflow.py` под разделённые этапы и гейты.
- [x] Версионирование промптов и релизные заметки: bump `prompt_version` в изменённых командах/агентах (RU/EN), обновить `src/claude_workflow_cli/data/payload/aidd/AGENTS.md`, `CHANGELOG.md`, `src/claude_workflow_cli/data/payload/manifest.json`, затем `scripts/sync-payload.sh --direction=to-root` и `python3 tools/check_payload_sync.py`.

## Wave 60

_Статус: новый, приоритет 1. Цель — anchors‑first + pack‑first MVP (только research‑context), затем расширения по данным и боли._

### Phase 0: Alignment & Baseline
- [x] Зафиксировать canonical/sync политику в `AGENTS.md` (или новый `AGENTS.md`): что является источником правды и какие команды sync использовать.
- [x] Проверить `tools/check_payload_sync.py`/`tools/payload_audit_rules.json` на новые артефакты (`aidd/docs/anchors/`, `AGENTS.md`, `aidd/docs/index/`) и обновить при необходимости.
- [x] Добавить раздел “Performance KPIs” в (минимум: Stop/checkbox, формат‑тесты/checkbox, частота чтения reports, средний stdout логов).
- [x] DoD: политика canonical/sync и минимальные KPI задокументированы.

### MVP (Phase 1): Anchors‑first + Pack MVP (research‑context only)
- [x] Источник правды: `aidd/**` как canonical; обновить `aidd/AGENTS.md` под MUST KNOW FIRST + anchors‑first/snippet‑first + pack‑first, добавить ссылку на working set; синхронизировать payload `scripts/sync-payload.sh --direction=from-root`.
- [x] Stage‑anchors: добавить `aidd/docs/anchors/{idea,research,plan,review-plan,review-prd,tasklist,implement,review,qa}.md`, затем sync в `src/claude_workflow_cli/data/payload/aidd/docs/anchors/`.
- [x] AIDD‑anchors в шаблонах: `aidd/docs/{prd,plan,research,tasklist}/template.md` (core + PRD/Plan/Research/Tasklist anchors), затем sync в payload‑копии.
- [x] Backfill anchors: `tests/repo_tools/upgrade_aidd_docs.py` — пройти по `aidd/docs/{prd,plan,tasklist,research}/**` и добавить отсутствующие `## AIDD:*` секции без перезаписи содержимого.
- [x] Тесты для апгрейда: `tests/test_upgrade_aidd_docs.py` (минимум 1–2 фикстуры).
- [x] Контракт отчётов (MVP): `AGENTS.md` (+ payload копия) — naming `reports/<type>/<ticket>-<kind>.pack.json`, правило pack‑first, budgets для `reports/research/*-context.pack.json`, deterministic output (byte‑identical), whitelist/blacklist полей.
- [x] Инвентаризация отчётов: таблица top‑3 hotspots с `chars/lines/keys` в `AGENTS.md`.
- [x] Pack generator (MVP): `src/claude_workflow_cli/tools/reports_pack.py` для `reports/research/<ticket>-context.json` → sidecar `reports/research/<ticket>-context.pack.json` (stable order, top‑N, stable IDs).
- [x] Single loader API: `src/claude_workflow_cli/reports/loader.py` (например, `load_report()`/`get_report_paths()`), обновить `src/claude_workflow_cli/cli.py` (`tasks-derive --source research`) на pack‑first + fallback в JSON.
- [x] Тесты: `tests/test_reports_pack.py` (golden + детерминизм), `tests/test_tasks_derive.py` (pack‑first), обновить `src/claude_workflow_cli/data/payload/manifest.json` и прогнать `python3 tools/check_payload_sync.py`.
- [x] Обновить все агенты и команды под anchors‑first/snippet‑first/read‑once: `aidd/{agents,commands}/*.md` + payload‑копии.
- [x] Мини‑аудит: убедиться, что `qa`/`researcher` не копии `prd-reviewer` (фикс отдельным чекбоксом в промптах при необходимости).
- [x] Линт: расширить `tests/repo_tools/lint-prompts.py` на проверку anchors в шаблонах и наличие stage‑anchors; обновить `tests/test_prompt_lint.py`.
- [x] Документация: обновить `AGENTS.md` (разделы playbook), `README.md`, `README.en.md`, `src/claude_workflow_cli/data/payload/aidd/workflow.md` под anchors‑first + working set.
- [x] DoD: контракт `AGENTS.md` зафиксирован, pack создаётся для research‑context и используется в `tasks-derive`, golden‑тесты детерминизма проходят, root→payload sync выполнен.

### Phase 1.5: Working set (Context GC)
- [x] Обновить `src/claude_workflow_cli/context_gc/working_set_builder.py`: включать `AIDD:CONTEXT_PACK`, лимиты по строкам/символам, ссылку на stage‑anchor текущей стадии.
- [x] Зафиксировать канонический путь `aidd/reports/context/latest_working_set.md` и описание в `AGENTS.md`.
- [x] (Опционально) Smoke: проверить, что working set строится и содержит `AIDD:CONTEXT_PACK`.
- [x] DoD: working set стабильно содержит `AIDD:CONTEXT_PACK` и используется как первый источник контекста.

### Phase 1.6: Test‑profile defaults + summary logs
- [x] Обновить `aidd/hooks/hooks.json` (+ payload): `AIDD_TEST_PROFILE_DEFAULT=fast` на `SubagentStop`, `AIDD_TEST_PROFILE_DEFAULT=targeted` на `Stop`.
- [x] Обновить `aidd/hooks/format-and-test.sh` (+ payload): приоритет `AIDD_TEST_PROFILE` > `aidd/.cache/test-policy.env` > `AIDD_TEST_PROFILE_DEFAULT`.
- [x] Summary‑режим: полный лог в `aidd/.cache/logs/format-and-test.<timestamp>.log`, stdout — профиль/задачи/итог + tail при fail; env `AIDD_TEST_LOG`, `AIDD_TEST_LOG_TAIL_LINES`.
- [x] Регрессии: `tests/test_format_and_test.py`, `tests/repo_tools/smoke-workflow.sh` + payload‑копии, `AGENTS.md`.
- [x] DoD: дефолты профилей по событиям действуют, stdout короткий, полный лог сохраняется.

### Phase 2: Расширение pack + events + index
- [x] Расширить pack на QA/PRD/Review: обновить `src/claude_workflow_cli/tools/{qa_agent.py,prd_review.py}` для sidecar pack и обновить схемы в `AGENTS.md`.
- [x] Columnar‑секции: findings (QA/PRD/Review), matches/reuse/call_graph/import_graph (research) с `cols/rows` и reference‑таблицами в `AGENTS.md`.
- [x] Pack‑first чтение вне tasks‑derive: обновить `aidd/{agents,commands}/*.md`,; sync `scripts/sync-payload.sh --direction=from-root`.
- [x] JSONL events + `/feature-dev-aidd:status`: схема `aidd/reports/events/<ticket>.jsonl`, append‑запись в CLI/хуках, команда `/feature-dev-aidd:status` в `aidd/commands/status.md` + CLI‑handler чтения index + events.
- [x] Ticket index/hub как derived‑source: генерация `aidd/docs/index/<ticket>.yaml` (schema `aidd.ticket.v1`) из tasklist/anchors/reports/events; CLI helper в `src/claude_workflow_cli/cli.py` или `src/claude_workflow_cli/tools/index_sync.py`.
- [x] Линт/гейты: расширить `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py` и добавить `tests/test_index_schema.py` для schema index.
- [x] DoD: pack‑sidecar есть для QA/PRD/Review, `/feature-dev-aidd:status` показывает индекс + последние events, линтер ловит отсутствие anchors/index, docs синхронизированы.

### Phase 3: Advanced (по факту боли)
- [x] RFC6902 patch updates: `tests/repo_tools/apply_json_patch.py`, `reports/<type>/<ticket>.patch.json`, флаг `--emit-patch` в `qa_agent.py`/`prd_review.py` — включать только при доказанном pain (diff/size).
- [x] TOON optional: конвертер `full.json -> pack.toon` под `AIDD_PACK_FORMAT=toon`, ограничения в `AGENTS.md`.
- [x] Доп. оптимизации: `--pack-only`, компрессия больших полей по whitelist/blacklist, расширение budgets.
- [x] DoD: опции gated флагами, есть e2e пример/тесты и документированные ограничения.

## Wave 60.1

_Статус: новый, приоритет 2. Residuals only: остались только точечные хвосты после Wave 60._

### Residuals only
- [x] Stable IDs для findings (QA/PRD): определить ключи, обновить генераторы отчётов и patch‑friendly diff.
- [x] Enforcement budgets: добавить проверку превышения лимитов в CI/тестах (и подсказку как снизить объём).
- [x] Auto‑sync index: генерировать `aidd/docs/index/<ticket>.yaml` автоматически при `claude-workflow set-active-feature` и при `/feature-dev-aidd:status` без ручного `index-sync`.

## Wave 62

_Статус: новый, приоритет 1. Цель — добавить единую оркестрацию флоу через `/flow` (команда‑композиция с human‑in‑the‑loop)._

### Спецификация поведения /flow
- [x] Зафиксировать decision‑tree `/flow`: источники `ticket/slug` (аргументы → `.active_*`), маппинг `stage → next command`, режимы `spec|full|next`, лимит на число шагов за запуск, правила остановки при `PENDING/BLOCKED` и обязательные READY‑артефакты; оформить в `src/claude_workflow_cli/data/payload/aidd/workflow.md`.
- [x] Обновить контракт команд в `src/claude_workflow_cli/data/payload/aidd/`: добавить `/flow` в матрицу (входы/выходы), описать политику `SlashCommand` и handoff‑правила.

### Промпты /flow (payload)
- [x] Создать RU‑команду `src/claude_workflow_cli/data/payload/aidd/commands/flow.md` по шаблону playbook: `argument-hint`, `allowed-tools` (Read/Glob/`Bash(rg:*)`/`Bash(cat:*)`/`SlashCommand`), алгоритм выбора следующей стадии и секция блокировки с вопросами.
- [x] Создать EN‑версию `src/claude_workflow_cli/data/payload/aidd/prompts/en/commands/flow.md` с синхронным `prompt_version` и `source_version`.

### Интеграция и реестр команд
- [x] Подключить `/flow` в `src/claude_workflow_cli/data/payload/aidd/.claude-plugin/plugin.json`.
- [x] Обновить краткий гайд команд в `src/claude_workflow_cli/data/payload/aidd/workflow.md` (пример запуска `/flow`, режимы и handoff).

### Optional: checkpoint‑handoff
- [x] Опционально: добавить маркер `aidd/docs/.flow_checkpoint` при блокировке (для auto‑resume) и описать правило в `src/claude_workflow_cli/data/payload/aidd/AGENTS.md`.

### Governance и синхронизация
- [x] Обновить `src/claude_workflow_cli/data/payload/aidd/AGENTS.md`, `CHANGELOG.md`, `src/claude_workflow_cli/data/payload/manifest.json` после добавления команды.
- [x] Прогнать `python3 tests/repo_tools/lint-prompts.py --root src/claude_workflow_cli/data/payload/aidd` и `python3 tools/check_payload_sync.py`, затем синхронизировать payload → root: `scripts/sync-payload.sh --direction=to-root`.

## Wave 63

_Статус: новый, приоритет 1. Цель — CLI‑first: перенести всю кастомную автоматизацию из payload в `claude-workflow`, удалить скрипты/обвязки из payload без обратной совместимости._

### Инвентаризация и карта миграции
- [x] Собрать реестр всех кастомных скриптов/обвязок в payload: `src/claude_workflow_cli/data/payload/aidd/tools/*.py`, `src/claude_workflow_cli/data/payload/aidd/scripts/**`, `src/claude_workflow_cli/data/payload/aidd/hooks/_vendor/claude_workflow_cli/**`, плюс все упоминания в hooks/commands/agents/docs; оформить таблицу «старый путь → новая CLI‑команда → потребители» в.

### CLI‑команды: перенос логики из payload
- [x] Перенести `aidd/tools/set_active_feature.py` в `claude-workflow set-active-feature` (модуль в `src/claude_workflow_cli/`, CLI‑подкоманда в `src/claude_workflow_cli/cli.py`).
- [x] Перенести `aidd/tools/set_active_stage.py` в `claude-workflow set-active-stage`.
- [x] Перенести legacy-миграции в CLI-слой без отдельных migrate-команд.
- [x] Перенести `aidd/scripts/prd-review-agent.py` в `claude-workflow review-spec` (или `claude-workflow prd-review`) с сохранением JSON‑отчёта и текстового summary.
- [x] Перенести `aidd/scripts/{plan_review_gate.py,prd_review_gate.py}` в `claude-workflow plan-review-gate` / `claude-workflow prd-review-gate` (используются хуками).
- [x] Перенести `aidd/scripts/qa-agent.py` в `claude-workflow qa` (единый генератор отчёта, exit‑codes и фильтры).
- [x] Перенести `aidd/tools/researcher_context.py` в `claude-workflow researcher-context` или интегрировать в `claude-workflow research` (один источник истины).
- [x] Перенести `aidd/scripts/context_gc/*` в `claude-workflow context-gc` (режимы `precompact`, `sessionstart`, `pretooluse`, `userprompt`).
- [x] Удалить `aidd/tools/run_cli.py`: все вызовы должны идти через установленный `claude-workflow` (с понятной ошибкой при отсутствии бинаря).

### Обновление хуков/команд/агентов под CLI‑first
- [x] Обновить хуки: заменить `python3.../scripts/*.py` и `python3.../tools/*.py` на `claude-workflow <subcommand>` в `src/claude_workflow_cli/data/payload/aidd/hooks/{gate-workflow.sh,gate-prd-review.sh,gate-qa.sh,gate-tests.sh,lint-deps.sh}` и `src/claude_workflow_cli/data/payload/aidd/hooks/hooks.json`.
- [x] Обновить slash‑команды и агентские промпты (RU/EN): заменить упоминания `tools/*`/`scripts/*` на `claude-workflow` во всех `src/claude_workflow_cli/data/payload/aidd/{commands,agents}/**`.
- [x] Обновить `.claude/settings.json`: удалить разрешения на `aidd/tools/*` и `aidd/scripts/*`, оставить `Bash(claude-workflow:*)` и нужные стандартные утилиты.

### Очистка payload (без обратной совместимости)
- [x] Удалить из payload все кастомные скрипты/обвязки: `src/claude_workflow_cli/data/payload/aidd/tools/`, `src/claude_workflow_cli/data/payload/aidd/scripts/`, `src/claude_workflow_cli/data/payload/aidd/hooks/_vendor/claude_workflow_cli/**`.
- [x] Обновить `src/claude_workflow_cli/data/payload/aidd/init-claude-workflow.sh` (не копировать удалённые файлы) и `src/claude_workflow_cli/data/payload/manifest.json`.

### Тесты и CI
- [x] Обновить smoke: `src/claude_workflow_cli/data/payload/aidd/tests/repo_tools/smoke-workflow.sh` (или заменить на вызов `claude-workflow smoke`) без обращения к `tools/*.py`/`scripts/*.py`.
- [x] Переписать unit‑тесты на CLI‑first: `tests/test_init_aidd.py`, `tests/test_gate_workflow.py`, `tests/test_gate_qa.py`, `tests/test_prd_review_gate.py`, `tests/test_prompt_versioning.py` (если зависит от скриптов).
- [x] Добавить тесты наличия новых CLI‑подкоманд и отсутствия legacy‑файлов в payload.

### Документация и релиз
- [x] Обновить `README.md`, `README.en.md`, `src/claude_workflow_cli/data/payload/aidd/workflow.md`, `src/claude_workflow_cli/data/payload/aidd/`, `src/claude_workflow_cli/data/payload/aidd/` — заменить ссылки на `tools/*.py`/`scripts/*.py` на `claude-workflow`.
- [x] Обновить `src/claude_workflow_cli/data/payload/aidd/AGENTS.md` и `CHANGELOG.md` (breaking change: legacy scripts removed).
- [x] Финал: `python3 tools/check_payload_sync.py`, `scripts/sync-payload.sh --direction=to-root`, полный прогон `tests/repo_tools/ci-lint.sh`.

## Wave 64

_Статус: новый, приоритет 1. Цель — унификация путей и root-resolution в хуках/скриптах._

### Унификация путей и root-resolution
- [x] Ввести единый helper `hook_project_root` в `src/claude_workflow_cli/data/payload/aidd/hooks/lib.sh` с приоритетом: `CLAUDE_PLUGIN_ROOT` → `git -C "$PWD" rev-parse --show-toplevel` → поиск вверх `aidd/docs`; возвращать абсолютный путь (realpath) и пустое значение при провале. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Привести все hook‑скрипты к одному резолверу и абсолютным путям (без `cd`): `src/claude_workflow_cli/data/payload/aidd/hooks/{gate-workflow.sh,gate-prd-review.sh,gate-tests.sh,gate-qa.sh,lint-deps.sh}`; все git‑команды только через `git -C "$ROOT_DIR"...`; если root не найден — мягкий exit без блокировки. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Унифицировать резолвинг путей в runtime‑скриптах и tools: добавить `--root` и единый helper `get_root()` в `src/claude_workflow_cli/data/payload/aidd/scripts/{qa-agent.py,prd-review-agent.py,plan_review_gate.py,prd_review_gate.py}` и `src/claude_workflow_cli/data/payload/aidd/tools/{set_active_stage.py,set_active_feature.py,run_cli.py}`; исключить относительные `./aidd` пути. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Обновить документацию об источнике root и запуске CLI: `src/claude_workflow_cli/data/payload/aidd/workflow.md`, `src/claude_workflow_cli/data/payload/aidd/`, `src/claude_workflow_cli/data/payload/aidd/` (правило: хуки и CLI работают от workspace root). (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Добавить тесты на резолвинг root: эмуляция `CLAUDE_PLUGIN_ROOT` (cache path), запуск hook из чужого cwd; отдельный кейс non‑git — ожидается мягкий exit. Файлы: `tests/test_gate_workflow.py`, `tests/helpers.py`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] После унификации: обновить `src/claude_workflow_cli/data/payload/manifest.json`, прогнать `python3 tools/check_payload_sync.py`, синхронизировать root через `scripts/sync-payload.sh --direction=to-root`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)

## Wave 65

_Статус: новый, приоритет 1. Цель — поддержка dual‑deploy: Claude Code plugin + OpenCode (opencode.ai) с единым ядром `aidd/**`._

### Основания: init, root‑детекция, automation (blocking)
- [x] `claude-workflow init --type {claude-code-plugin|open-code|both}` + help/usage. **Deps:** нет. **AC:** default = `claude-code-plugin`; `--type open-code` не создаёт `.claude*`; `--type both` создаёт оба overlay; `--dry-run` отражает выбранный тип. Файлы: `src/claude_workflow_cli/cli.py`, `src/claude_workflow_cli/data/payload/aidd/init-claude-workflow.sh`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Разделить генерацию overlay в init‑скрипте (Claude Code vs OpenCode). **Deps:** флаг `--type`. **AC:** `opencode.json` и `.opencode/**` появляются в workspace root; `.claude/` и `.claude-plugin/` не создаются при `--type open-code`; логирование явно указывает выбранный тип. Файл: `src/claude_workflow_cli/data/payload/aidd/init-claude-workflow.sh`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Обновить root‑детекцию CLI под OpenCode. **Deps:** init‑флаги. **AC:** команды, использующие `_require_workflow_root`, работают при наличии только `opencode.json`/`.opencode/**`; `WORKSPACE_ROOT_DIRS` учитывает `.opencode` и `opencode.json` (или спец‑обработку файла); ошибки упоминают оба типа установки; `sync`/`upgrade` не переносят `opencode.json` внутрь `aidd/`; `tools/check_payload_sync.py` считает `opencode.json` workspace‑root артефактом. Файлы: `src/claude_workflow_cli/cli.py`, `tools/check_payload_sync.py`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Обновить `claude-workflow sync/upgrade` под OpenCode. **Deps:** root‑детекция. **AC:** `sync` по умолчанию подтягивает `.opencode/` и `opencode.json` при open‑code установке (или доступен `--include opencode`), `upgrade` корректно раскладывает workspace‑root артефакты, `--dry-run` отражает opencode‑файлы. Файл: `src/claude_workflow_cli/cli.py`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Зафиксировать источник `automation` для OpenCode и внедрить fallback. **Deps:** init‑изменения. **AC:** `format-and-test.sh` работает без `.claude/settings.json`; приоритет источников задокументирован (например, `CLAUDE_SETTINGS_PATH`/`.claude/settings.json` → `aidd/config/automation.json`); выбранный источник создаётся при `--type open-code` или доступен по умолчанию. Файлы: `src/claude_workflow_cli/data/payload/aidd/hooks/format-and-test.sh`, `src/claude_workflow_cli/data/payload/opencode.json` (+ выбранный конфиг). (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)

### OpenCode overlay (payload)
- [x] Добавить `opencode.json` в payload root. **Deps:** init‑разделение overlay. **AC:** `$schema: https://opencode.ai/config.json`, `instructions: ["aidd/AGENTS.md"]`, заданы `permission`/`tools`, опционально `model`/`default_agent`; permission позволяет вызывать `claude-workflow` и `aidd/hooks/*.sh` без лишних подтверждений; способ регистрации plugin/commands/agents подтверждён (если требуется — перечислить пути в `opencode.json`, иначе зафиксировать автоподхват в документации); файл валиден относительно schema (тест/линт); файл включён в manifest. Файл: `src/claude_workflow_cli/data/payload/opencode.json`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] `.opencode/command/*.md` thin‑wrappers на `@aidd/commands/<name>.md`. **Deps:** opencode.json. **AC:** покрыты команды `idea-new`, `researcher`, `plan-new`, `review-spec`, `tasks-new`, `implement`, `review`, `qa`, `status`; frontmatter содержит `description`, `agent`, `model`; без дублирования контента. Файлы: `src/claude_workflow_cli/data/payload/.opencode/command/*.md`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] `.opencode/agent/*.md` thin‑wrappers на `@aidd/agents/<name>.md`. **Deps:** opencode.json. **AC:** покрыты агенты `analyst`, `researcher`, `planner`, `validator`, `plan-reviewer`, `prd-reviewer`, `implementer`, `reviewer`, `qa`; frontmatter содержит `description`, `mode: subagent`, `model`, `tools`/`permission`. Файлы: `src/claude_workflow_cli/data/payload/.opencode/agent/*.md`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)

### OpenCode plugin: гейты и авто‑проверки
- [x] Реализовать `.opencode/plugin/aidd-workflow.ts`. **Deps:** root‑детекция (Wave 64) + automation‑решение. **AC:** `tool.execute.before` блокирует изменения `src/**` вне стадий `implement|review|qa` (только когда инструмент явно трогает путь под `src/`); при отсутствии root — warn и пропуск; `session.idle`/`tool.execute.after` вызывает `aidd/hooks/{gate-workflow,gate-tests,gate-qa,format-and-test,lint-deps}.sh` последовательно; передаётся `CLAUDE_PLUGIN_ROOT`; non‑code изменения не блокируются. Файл: `src/claude_workflow_cli/data/payload/.opencode/plugin/aidd-workflow.ts`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Формализовать exit‑codes/сообщения для OpenCode plugin. **Deps:** базовая реализация plugin. **AC:** soft/hard‑блокировки соответствуют хукам (`exit 2` блокирует, `exit 0` пропускает, прочие — warn без блокировки); сообщения совпадают по стилю с hook‑скриптами и содержат причину/следующее действие; константы вынесены в начале файла. Файл: `src/claude_workflow_cli/data/payload/.opencode/plugin/aidd-workflow.ts`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Добавить context‑gc hooks в OpenCode plugin. **Deps:** базовая реализация plugin. **AC:** аналоги `SessionStart`, `PreCompact`, `PreToolUse`, `UserPromptSubmit` вызывают `claude-workflow context-gc {sessionstart,precompact,pretooluse,userprompt}`; если часть событий недоступна в OpenCode — явно документировать ограничения. Файлы: `src/claude_workflow_cli/data/payload/.opencode/plugin/aidd-workflow.ts`, `AGENTS.md`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)

### Packaging/sync/audit
- [x] Обновить payload‑манифест/allowlist/синк. **Deps:** новые файлы overlay. **AC:** `manifest.json` содержит `opencode.json` и `.opencode/**`; `tools/payload_audit_rules.json` разрешает новые пути; `scripts/sync-payload.sh` синхронизирует `opencode.json` и `.opencode/` по умолчанию (и/или `--include opencode`); `tools/check_payload_sync.py` проверяет новые корневые пути. Файлы: `src/claude_workflow_cli/data/payload/manifest.json`, `tools/payload_audit_rules.json`, `scripts/sync-payload.sh`, `tools/check_payload_sync.py`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Обновить packaging для dotfiles. **Deps:** обновлённый payload. **AC:** wheel и payload‑архив содержат `opencode.json` и `.opencode/**`; `pyproject.toml`/`MANIFEST.in` покрывают новые dot‑директории. Файлы: `pyproject.toml`, `MANIFEST.in`, `tests/test_package_payload.py`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)

### Tests
- [x] Тесты `init --type open-code` и `--type both`. **Deps:** init + overlay. **AC:** создаются `opencode.json`, `.opencode/{command,agent,plugin}`; `.claude/` и `.claude-plugin/` отсутствуют при `open-code`; CLI‑команды работают при open‑code‑only установке; `sync/upgrade` корректно обрабатывают workspace‑root `opencode.json`. Файлы: `tests/test_init_aidd.py` (или новый `tests/test_init_open_code.py`), `tests/test_cli_sync.py`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Обновить `tests/test_package_payload.py`. **Deps:** packaging update. **AC:** проверки ожидают `opencode.json` и `.opencode/**` в wheel/payload‑zip. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Добавить проверку `opencode.json` и wrapper‑файлов. **Deps:** opencode overlay. **AC:** `opencode.json` валиден по schema (или минимальный контракт проверен тестом); wrapper‑файлы ссылаются на `@aidd/commands/*` и `@aidd/agents/*` без дублирования контента. Файлы: `tests/test_package_payload.py` (или отдельный тест). (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)
- [x] Добавить smoke‑сценарий OpenCode. **Deps:** overlay + plugin. **AC:** сценарий `init --type open-code` создаёт `opencode.json`/`.opencode`, не создаёт `.claude*`, проверяет базовые гейты/хуки (dry‑run или с фиктивным payload) и корректные exit‑codes. Файлы: `tests/repo_tools/smoke-workflow.sh` (или новый smoke‑скрипт), `src/claude_workflow_cli/data/payload/smoke-workflow.sh` (если применимо). (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)

### Документация
- [x] README + dev‑гайды под dual‑deploy. **Deps:** init/overlay/automation. **AC:** `README.md`/`README.en.md` показывают `--type` и layout (`.claude*` vs `.opencode*`); `AGENTS.md` и `AGENTS.md` описывают OpenCode‑режим, plugin‑гейты, источник automation и зависимость от установленного `claude-workflow` для хуков; отсутствуют ссылки на несуществующие payload‑доки. Файлы: `README.md`, `README.en.md`, `AGENTS.md`, `AGENTS.md`. (obsolete: marketplace-only plugin, runtime в `commands/agents/hooks/tools`, без `claude-workflow` CLI/payload)

## Wave 66

_Статус: новый, приоритет 1. Цель — ускорить /feature-dev-aidd:implement и уменьшить частоту тяжёлых тестов через профили, бюджет и дедуп._

### Промпты /feature-dev-aidd:implement и implementer
- [x] Обновить RU `/feature-dev-aidd:implement` (`aidd/commands/implement.md`, `src/claude_workflow_cli/data/payload/aidd/commands/implement.md`): обновить описание на “малые итерации + управляемые проверки”, `argument-hint` с `test=...`, `tests=...`, `tasks=...`; добавить Test policy (FAST/TARGETED/FULL/NONE + decision-matrix), default=fast; описать контракт `aidd/.cache/test-policy.env` (AIDD_TEST_PROFILE/FILTERS/TASKS), правило приоритета: если `test-policy.env` создан — запускаем профиль, иначе применяем reviewer gate; явный шаг `set_active_feature`; ожидаемый вывод с `Test profile`/`Tests run` и запретом ручного дубля `format-and-test.sh`; повысить `prompt_version`/`source_version`.
- [x] Обновить RU `implementer` (`aidd/agents/implementer.md`, `src/claude_workflow_cli/data/payload/aidd/agents/implementer.md`): лимит итерации (1 чекбокс/2 связанных), test budget (не повторять без diff), decision matrix; обязать писать `aidd/.cache/test-policy.env` и создавать `aidd/.cache`; добавить примеры Gradle `--tests` + `AIDD_TEST_TASKS`, выводить `Iteration scope`/`Test profile`/`Tests run`/`Why`, переписать шаг 4 на «проверки по профилю», обновить версии.

### Автотесты и профили
- [x] Добавить в `src/claude_workflow_cli/data/payload/aidd/hooks/format-and-test.sh` чтение `aidd/.cache/test-policy.env` и поддержку профилей `fast|targeted|full|none` (env `AIDD_TEST_PROFILE`, `AIDD_TEST_FILTERS`, `AIDD_TEST_TASKS`, `AIDD_TEST_FORCE`) с маппингом на `FORMAT_ONLY`, `TEST_SCOPE`, `TEST_CHANGED_ONLY` и задачи раннера; default = fast; если `test-policy.env` задан — профиль имеет приоритет и тесты запускаются без reviewer gate, иначе действует reviewer gate; manual scope/filters имеют приоритет.
- [x] Реализовать dedupe/budget в `src/claude_workflow_cli/data/payload/aidd/hooks/format-and-test.sh`: fingerprint diff+профиля+таргетов, кеш в `aidd/.cache/format-and-test.last.json`, пропускать повторный запуск при неизменном diff, повторять только после фейла или изменения.
- [x] Обновить `.claude/settings.json` и `src/claude_workflow_cli/data/payload/.claude/settings.json`: добавить `fastTasks`, `fullTasks` (по умолчанию = `defaultTasks`), `targetedTask`, рекомендованный `moduleMatrix` под Gradle‑монорепо (module → `:module:testClasses`), оставить `defaultTasks/fallbackTasks` для FULL, синхронизировать параметры с docs.
- [x] Обновить `.gitignore` и/или `init-claude-workflow.sh`: убедиться, что `aidd/.cache/` игнорируется в целевом workspace (добавить явное правило при bootstrap).

### Документация и шаблоны
- [x] Обновить: новая политика тестов, лимит итерации, `test-policy.env`, примеры Gradle `--tests`, правила повторного прогона.
- [x] Обновить `AGENTS.md`: новые env/config ключи (`AIDD_TEST_PROFILE`, `AIDD_TEST_FILTERS`, `AIDD_TEST_TASKS`, `AIDD_TEST_FORCE`, `fastTasks/fullTasks/targetedTask`), `aidd/.cache/test-policy.env` примеры, dedupe/budget.
- [x] Обновить `src/claude_workflow_cli/data/payload/aidd/docs/tasklist/template.md`: фиксировать `Test profile` и команды тестов в чеклисте реализации.
- [x] Добавить запись в `AGENTS.md`, `CHANGELOG.md` и (при необходимости) `README.md`/`README.en.md` о новой политике тестов/итераций.

### Тесты и синхронизация
- [x] Создать новые тест-кейсы (в `tests/test_format_and_test.py` и/или отдельном модуле) на `AIDD_TEST_PROFILE` (fast/targeted/full/none), чтение `test-policy.env`, `AIDD_TEST_FILTERS/TASKS`, dedupe‑скип, `AIDD_TEST_FORCE`, default fast, новый конфиг профилей.
- [x] Обновить smoke-сценарии: `tests/repo_tools/smoke-workflow.sh` и `src/claude_workflow_cli/data/payload/smoke-workflow.sh` — добавить проверки нового `Test profile`/policy и отсутствия повторного прогона при dedupe.
- [x] Финал: `tests/repo_tools/prompt-version` (bump RU), `tests/repo_tools/lint-prompts.py --root <root>`, `python3 tools/check_payload_sync.py`, `scripts/sync-payload.sh --direction=to-root`.

## Wave 67

_Статус: новый, приоритет 1. Цель — упростить payload (без пресетов и EN‑промптов), нормализовать шаблоны и пересмотреть необходимость крупных гайдов._

### Инвентаризация и политика payload
- [x] Зафиксировать карту установки (uv tool install → `claude_workflow_cli/data/payload/**` → `claude-workflow init`): обновить `AGENTS.md` и таблицу “core vs dev-only”, без упоминания пресетов и EN‑промптов.
- [x] Удалить `claude-presets/**` из payload, `init-claude-workflow.sh`, `manifest.json`, `tools/payload_audit_rules.json`, `scripts/sync-payload.sh`; убрать `claude-workflow preset` и `--preset/--feature` из CLI/доков; обновить тесты и README.
- [x] Удалить `prompts/en/**`: убрать `--prompt-locale` из CLI и init‑скрипта, удалить паритет‑проверки из `gate-workflow.sh`, пересмотреть `tests/repo_tools/lint-prompts.py`, обновить `AGENTS.md` и, удалить упоминания из README/тестов.
- [x] Аудит необходимости `aidd/AGENTS.md` и `aidd/workflow.md`: либо сохранить как core user‑guides, либо перенести в `AGENTS.md` и удалить из payload/manifest/tests.

### Нормализация шаблонов (templates)
- [x] Перенести шаблоны артефактов в соответствующие подпапки: `docs/prd/template.md` → `docs/prd/template.md`, `docs/adr/template.md` → `docs/adr/template.md`, `docs/tasklist/template.md` → `docs/tasklist/template.md`, `docs/research/template.md` → `docs/research/template.md`; обновить ссылки в `AGENTS.md`, `agents/commands`, `init-claude-workflow.sh`, README и тестах.
- [x] Убрать дублирование tasklist‑шаблона: перейти на единый источник (предпочтительно `docs/tasklist/template.md`), обновить `init-claude-workflow.sh` (`render_tasklist_template`) и удалить `docs/tasklist/template.md` после миграции.
- [x] Определить финальное место для `AGENTS.md` и `AGENTS.md` (например, `agents/templates/` и `commands/templates/` или `AGENTS.md`), перенести и обновить `scripts/scaffold_prompt.py`, README.

### Docs: runtime vs dev-only
- [x] Разделить maintainer‑инструкции: вынести repo-only шаги из `aidd/AGENTS.md`, `aidd/AGENTS.md`, `aidd/` в `AGENTS.md`; в payload оставить user‑facing версии без ссылок на `scripts/*` и `tools/*` из корня.
- [x] Если `aidd/AGENTS.md` и `aidd/workflow.md` остаются в payload: заменить repo-only команды на CLI аналоги или пометки “repo-only”; убедиться, что payload‑доки не ссылаются на отсутствующие файлы.
- [x] Обязательно обновить `README.md` и `README.en.md` под удаление пресетов/EN‑промптов и новые пути шаблонов/доков.

### Перенос playbook/гайдов в dev-only (кроме conventions.md)
- [x] Определить dev-only местоположение и консолидировать версии: `aidd/`, `aidd/AGENTS.md`, `aidd/`, `aidd/AGENTS.md`, `aidd/`, `aidd/AGENTS.md`, `aidd/AGENTS.md` → `AGENTS.md` (свести дубли, сохранить историю).
- [x] Удалить payload-копии и заменить/удалить ссылки в payload: `aidd/AGENTS.md`, `aidd/docs/tasklist/template.md`, `aidd/agents/AGENTS.md`, `aidd/commands/AGENTS.md`, а также любые упоминания в `aidd/docs/*`, чтобы payload не ссылался на dev-only файлы.
- [x] Обновить публичные гайды: убрать ссылки на переносимые документы из `README.md` и `README.en.md`, скорректировать таблицу `aidd/docs/` и описания quick-start.
- [x] Обновить инвентаризацию/пакетирование: `src/claude_workflow_cli/data/payload/manifest.json`, `tools/payload_audit_rules.json`, `tools/check_payload_sync.py`, `scripts/sync-payload.sh`, `AGENTS.md`.
- [x] Обновить тесты пакета: `tests/test_package_payload.py`, `tests/test_bootstrap_e2e.py` (и при необходимости регрессию на отсутствие dev-only ссылок).

### Инсталляция/пакетирование/тесты
- [x] Обновить `src/claude_workflow_cli/data/payload/manifest.json`, `tools/payload_audit_rules.json`, `tools/check_payload_sync.py`, `scripts/sync-payload.sh` под новые пути шаблонов/доков.
- [x] Обновить тесты (`tests/test_package_payload.py`, `tests/test_bootstrap_e2e.py`, `tests/test_gate_workflow.py` при необходимости) под новые пути и удалённые каталоги; добавить регрессию на отсутствие repo-only ссылок в payload docs.

## Wave 68

_Статус: новый, приоритет 1. Цель — EP09‑MVP (anchors/attention) + снижение частоты тяжёлых тестов без потери качества._

### Промпты и контекстная дисциплина (EP09‑MVP)
- [x] Обновить `aidd/AGENTS.md` и `src/claude_workflow_cli/data/payload/aidd/AGENTS.md`: заменить “что читать прежде всего” на `MUST KNOW FIRST` + read‑once policy; добавить правило “если есть `*.pack.json` → читать pack, иначе anchors‑first”; добавить ссылку на working set (`aidd/reports/context/latest_working_set.md`), и указать, что `sdlc-flow` и `status-machine` читаются только при первом входе/изменениях.
- [x] Создать stage‑anchor `aidd/docs/anchors/implement.md` и `src/claude_workflow_cli/data/payload/aidd/docs/anchors/implement.md`: цели, MUST update, MUST NOT, что читать первым, Stop etiquette, дефолты профиля тестов.
- [x] Обновить `aidd/agents/implementer.md` и `src/claude_workflow_cli/data/payload/aidd/agents/implementer.md`: добавить секцию “Context hygiene” (anchors‑first, snippet‑first через `rg` + `sed`, read‑once policy), “Stop etiquette” (1 чекбокс или 2 связанных до Stop), обязать обновлять `AIDD:CONTEXT_PACK` в tasklist (если секции нет — добавить по шаблону).
- [x] Обновить `aidd/commands/implement.md` и `src/claude_workflow_cli/data/payload/aidd/commands/implement.md`: первым источником контекста считать working set + `AIDD:CONTEXT_PACK` в tasklist; запретить полные Read без необходимости; подчеркнуть, что `format-and-test.sh` запускается автоматически; ссылаться на stage‑anchor `docs/anchors/implement.md`.

### Tasklist template: AIDD:CONTEXT_PACK
- [x] Добавить секцию `## AIDD:CONTEXT_PACK (<= 20 lines, <= 1200 chars)` в `aidd/docs/tasklist/template.md` и `src/claude_workflow_cli/data/payload/aidd/docs/tasklist/template.md` с правилами заполнения (фокус, активные файлы, инварианты, ссылки на план).
- [x] Обновить `/feature-dev-aidd:tasks-new` (или implementer‑fallback), чтобы при отсутствии `AIDD:CONTEXT_PACK` секция добавлялась в существующий tasklist.

### Context GC: рабочий набор
- [x] Зафиксировать канонический путь working set и использовать его в `aidd/AGENTS.md`, `src/claude_workflow_cli/context_gc/working_set_builder.py`,.
- [x] Расширить `src/claude_workflow_cli/context_gc/working_set_builder.py`: извлекать `AIDD:CONTEXT_PACK` из tasklist и включать в working set; опционально ограничить длину блока отдельным лимитом.

### Хуки и профили тестов по событию
- [x] Обновить `aidd/hooks/hooks.json` и `src/claude_workflow_cli/data/payload/aidd/hooks/hooks.json`: передавать `AIDD_TEST_PROFILE_DEFAULT=fast` на `SubagentStop` и `AIDD_TEST_PROFILE_DEFAULT=targeted` на `Stop`; если hooks.json не поддерживает env per‑event, добавить fallback (обёртка команды или логика в `format-and-test.sh` по событию).
- [x] Обновить `aidd/hooks/format-and-test.sh` и `src/claude_workflow_cli/data/payload/aidd/hooks/format-and-test.sh`: приоритет профиля `AIDD_TEST_PROFILE` > `aidd/.cache/test-policy.env` > `AIDD_TEST_PROFILE_DEFAULT` > `fast`.

### Сжатие вывода тестов
- [x] Добавить summary‑режим в `aidd/hooks/format-and-test.sh` и `src/claude_workflow_cli/data/payload/aidd/hooks/format-and-test.sh`: полный лог писать в `aidd/.cache/logs/format-and-test.<timestamp>.log`, в stdout выводить профиль, задачи, итог и tail при fail; добавить `AIDD_TEST_LOG` и `AIDD_TEST_LOG_TAIL_LINES`.

### Тесты, smoke и документация
- [x] Обновить `tests/test_format_and_test.py` и smoke‑сценарии (`tests/repo_tools/smoke-workflow.sh`, `src/claude_workflow_cli/data/payload/smoke-workflow.sh`) под дефолты Stop/SubagentStop и summary‑логи.
- [x] Обновить `AGENTS.md` и: anchors‑first/pack‑first, `AIDD:CONTEXT_PACK`, новые дефолты профиля и формат логов.
- [x] Финал: `python3 tools/check_payload_sync.py`, `scripts/sync-payload.sh --direction=to-root`.

## Wave 69

_Статус: новый, приоритет 2. Цель — ticket manifest + cadence policy + schema/logs + security guard._

### EPIC A — Ticket manifest + anchors expansion
- [x] Добавить `aidd/docs/tickets/` и шаблон `aidd/docs/tickets/template.yaml` (schema v1: ticket/slug/stage/status/owners/artifacts/tests/reports).
- [x] Автогенерация manifest при `/feature-dev-aidd:idea-new` и `claude-workflow set-active-feature` (`src/claude_workflow_cli/cli.py`, `src/claude_workflow_cli/feature_ids.py`); добавить тесты.
- [x] Линт schema + smoke: `tests/test_ticket_manifest.py`, обновить `tests/repo_tools/lint-prompts.py`/`tests/test_prompt_lint.py` для наличия manifest.
- [x] Расширить шаблоны anchors (без multi‑platform/deploy): PRD добавить `AIDD:CONTRACTS` и `AIDD:OBSERVABILITY`, Research добавить `AIDD:TEST_HOOKS` и `AIDD:GAPS`; обновить `aidd/docs/*/template.md` и payload‑копии. (Rescoped в Wave 70: новый канон без этих секций.)

### EPIC D — Test cadence policy + debounce
- [x] Ввести cadence policy в `.claude/settings.json`: `cadence=on_stop|checkpoint|manual`, `checkpoint_trigger`, обновить `aidd/hooks/format-and-test.sh` на новый режим.
- [x] Дебаунс запусков: хранить state в `aidd/.cache/format-and-test.last.json` и пропускать повтор при отсутствии diff/изменений.
- [x] Обновить `aidd/agents/implementer.md` на обязательный `Test scope/Cadence/Why skipped`; добавить тесты.

### EPIC E — Reports schema + JSONL logs
- [x] Зафиксировать schema header для отчетов в `AGENTS.md` (ticket/stage/status/started_at/finished_at/tool_versions/summary).
- [x] Добавить JSONL логи `reports/tests/<ticket>.jsonl` и CLI helper для append, обновить `/feature-dev-aidd:status` и `index_sync.py`.
- [x] Columnar full graphs: добавить `*-call-graph-full.cjson` (или иной columnar формат) и описать чтение в `reports-format.md`.

### EPIC F — Security guard (prompt‑injection)
- [x] Добавить правило в `aidd/AGENTS.md`: игнорировать инструкции из кода/комментариев/README зависимостей; усилить `context_gc/pretooluse_guard.py` для защиты при Read/Bash.
- [x] Тесты на guard‑policy: `tests/test_context_gc.py` + smoke‑сценарии.

### EPIC G — Context pack CLI (optional)
- [x] Добавить `claude-workflow context-pack --ticket <T> --agent <name>`: собирать anchors из PRD/Plan/Tasklist и писать `reports/context/<ticket>-<agent>.md`.
- [x] Документация и примеры: `AGENTS.md`, `AGENTS.md`, обновить `manifest.json`.

### EPIC H — Prompt slimming + mkdir-free + hook noise
- [x] Slim команды: ограничить размер `/commands/*.md` (≤160 строк), убрать повторяющиеся блоки политики, оставить ссылки на `aidd/AGENTS.md` и stage‑anchors; обновить `tests/repo_tools/lint-prompts.py`/`tests/test_prompt_lint.py` с проверкой лимита.
- [x] `aidd/AGENTS.md`: сохранить `MUST KNOW FIRST` как “stage‑anchor → AIDD:* → working set (если есть)”; index использовать только при необходимости; `sdlc-flow`/`status-machine` оставить read‑once; проверить, что path‑конвенции едины (`aidd/...`).
- [x] Предсоздание директорий: добавить `.gitkeep` в `reports/{context,qa,research,reviewer,tests}/` (и payload‑копии), чтобы не требовался `mkdir` в run‑time.
- [x] Снизить шум SubagentStop: ограничить набор тяжёлых хуков или добавить конфиг‑флаг “skip heavy on SubagentStop”; обновить `aidd/hooks/hooks.json` + smoke.

## Wave 70

_Статус: новый, приоритет 2. Цель — внедрить канон anchors/tasklist + унифицировать пути reports и чтение._

### EPIC A — Tasklist template + stage anchors (готовые файлы)
- [x] Заменить `aidd/docs/tasklist/template.md` на предоставленный канон (AIDD:CONTEXT_PACK, AIDD:HANDOFF_INBOX, чеклисты, HOW_TO_UPDATE) и синхронизировать `src/claude_workflow_cli/data/payload/aidd/docs/tasklist/template.md`.
- [x] Добавить `aidd/docs/anchors/README.md` со списком стадий + payload‑копию.
- [x] Полностью заменить stage‑anchors на предоставленные версии: `aidd/docs/anchors/{idea,research,plan,review-plan,review-prd,tasklist,implement,review,qa}.md` + payload‑копии (ссылки на `AIDD:RESEARCH_HINTS`, `AIDD:NEXT_3`, `AIDD:HANDOFF_INBOX`, `aidd/reports/**`, `AIDD:ACCEPTANCE`).
- [x] Обновить шаблоны PRD/Plan/Research/ADR под новый канон якорей: `AIDD:RESEARCH_HINTS`, `AIDD:ACCEPTANCE`, `AIDD:ROLL_OUT`, `AIDD:OPEN_QUESTIONS`, `AIDD:RISKS` (удалить `AIDD:CONTRACTS`, `AIDD:OBSERVABILITY`, `AIDD:ACCEPTANCE_CRITERIA`, `AIDD:GAPS`, `AIDD:RISKS_TOP5`); синхронизировать payload‑копии.

### EPIC B — Patch‑plan для AGENTS/агентов/команд
- [x] Обновить `aidd/AGENTS.md` и payload: working set `aidd/reports/context/latest_working_set.md`, `AIDD:NEXT_3`, `Reports: aidd/reports/**`, snippet‑regex под `AIDD:RESEARCH_HINTS`, упоминание `AIDD:HANDOFF_INBOX`, ссылки на `AIDD:ACCEPTANCE`.
- [x] Применить замены по агентам/командам: `Next 3 → AIDD:NEXT_3`, `## Research Hints → ## AIDD:RESEARCH_HINTS`, `AIDD:INBOX_DERIVED → AIDD:HANDOFF_INBOX`, `AIDD:ACCEPTANCE_CRITERIA → AIDD:ACCEPTANCE`, обновить пути reports/working set, добавить stage‑anchor ссылки; без back‑compat (полная замена якорей).
- [x] Добавить `Bash(sed:*)` в tools агентов (`analyst`, `researcher`, `plan-reviewer`, `prd-reviewer`, `qa`, `reviewer`, `planner`, `validator`) и синхронизировать payload‑копии.

### EPIC C — Reports paths: канон `aidd/reports/**`
- [x] Привести ссылки в `aidd/commands/*.md`, `aidd/agents/*.md`, `aidd/docs/anchors/*.md`, `aidd/docs/*template.md`, `AGENTS.md`, `README*.md`, `backlog.md`, smoke‑скриптах и payload‑копиях к `aidd/reports/**`.
- [x] Обновить runtime‑дефолты под `aidd/reports/**`: CLI (tests log, research outputs, context‑pack), hooks/gates, `config/gates.json`, `reports_pack.py`, `index_sync.py`.
- [x] Обновить примеры CLI/доков и тесты, которые ещё ждут `reports/**` (включая `aidd/commands/review-spec.md`, `aidd/commands/qa.md`, smoke, payload).

### EPIC D — Lint/tests/sync
- [x] Обновить `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `tests/repo_tools/upgrade_aidd_docs.py` под якоря `AIDD:HANDOFF_INBOX`, `AIDD:RESEARCH_HINTS`, `AIDD:ACCEPTANCE`, `AIDD:RISKS` (убрать `AIDD:INBOX_DERIVED`, `AIDD:ACCEPTANCE_CRITERIA`, `AIDD:CONTRACTS`, `AIDD:OBSERVABILITY`, `AIDD:GAPS`, `AIDD:RISKS_TOP5`).
- [x] Обновить smoke‑фикстуры и тесты под новый tasklist/anchors (включая payload smoke).
- [x] Финал: `python3 tools/check_payload_sync.py`, `scripts/sync-payload.sh --direction=to-root`.

## Wave 71

_Статус: новый, приоритет 1. Цель — гарантировать обновление tasklist после QA и code review (handoff‑задачи и traceability)._

### QA handoff: авто‑обновление tasklist
- [x] Добавить автогенерацию handoff‑задач после `/feature-dev-aidd:qa`: команда `/feature-dev-aidd:qa` и агент **qa** вызывают `claude-workflow tasks-derive --source qa --append --ticket <ticket>` после сохранения отчёта. **Deps:** нет. **AC:** tasklist получает блок в `AIDD:HANDOFF_INBOX` с ссылкой на `aidd/reports/qa/<ticket>.json`; добавлены нужные tools (`Bash(claude-workflow tasks-derive:*)`) в `/feature-dev-aidd:qa` и `qa` agent. Файлы: `src/claude_workflow_cli/data/payload/aidd/commands/qa.md`, `src/claude_workflow_cli/data/payload/aidd/agents/qa.md`.
- [x] Сделать QA handoff идемпотентным для повторных запусков. **Deps:** авто‑handoff. **AC:** повторный `/feature-dev-aidd:qa` не дублирует задачи; `tasks-derive --source qa` обновляет/дополняет существующие пункты по стабильному `id` из отчёта (или по детерминированной подписи) и сохраняет историю без повторов. Файлы: `src/claude_workflow_cli/cli.py`, `src/claude_workflow_cli/tools/qa_agent.py` (если нужно добавить/экспортировать id), `src/claude_workflow_cli/data/payload/aidd/AGENTS.md`.
- [x] Обновить `gate-qa.sh` для handoff‑контроля. **Deps:** автогенерация handoff. **AC:** при успешном QA (`--gate`) скрипт пытается `tasks-derive` (если разрешено) и предупреждает/блокирует при отсутствии записи в tasklist (конфиг/override‑флаг); поведение управляется `config/gates.json` (`qa.handoff=true` по умолчанию или явный override). Файлы: `src/claude_workflow_cli/data/payload/aidd/hooks/gate-qa.sh`, `src/claude_workflow_cli/data/payload/aidd/config/gates.json`.

### Review handoff: отчёт и задачи
- [x] Определить формат отчёта ревью и CLI‑хелпер. **Deps:** нет. **AC:** есть файл отчёта с findings (например, `aidd/reports/reviewer/<ticket>.json` с `findings[]` + `tests` marker), или отдельный `aidd/reports/review/<ticket>.json`; CLI создаёт/обновляет отчёт и не ломает существующий reviewer marker. Файлы: `src/claude_workflow_cli/data/payload/aidd/AGENTS.md`, `src/claude_workflow_cli/cli.py` (новая команда), `src/claude_workflow_cli/data/payload/aidd/config/gates.json` (если меняется путь).
- [x] Расширить `tasks-derive` на `--source review`. **Deps:** формат отчёта ревью. **AC:** из отчёта ревью формируются задачи в `AIDD:HANDOFF_INBOX` с `source: aidd/reports/reviewer/<ticket>.json` (или `.../review/...`), поддержаны `--append` и pack‑варианты. Файлы: `src/claude_workflow_cli/cli.py`.
- [x] Обновить `/feature-dev-aidd:review` и reviewer agent. **Deps:** tasks-derive review. **AC:** после ревью создаётся отчёт, запускается `tasks-derive --source review --append`; tasklist содержит review‑задачи; добавлены tools для CLI‑команд. Файлы: `src/claude_workflow_cli/data/payload/aidd/commands/review.md`, `src/claude_workflow_cli/data/payload/aidd/agents/reviewer.md`.
- [x] Сделать review handoff идемпотентным для повторных запусков. **Deps:** review report + tasks-derive review. **AC:** повторный `/feature-dev-aidd:review` не дублирует задачи; задачи маппятся по стабильному `id` и обновляются при изменении текста/рекомендаций; сохраняется история (например, через `Updated:`/`Last seen` в отчёте). Файлы: `src/claude_workflow_cli/cli.py`, `src/claude_workflow_cli/data/payload/aidd/AGENTS.md`.
- [x] Усилить gate‑workflow на review handoff. **Deps:** review report + tasks-derive. **AC:** если отчёт ревью существует и tasklist не содержит ссылку на report/source, `gate-workflow` блокирует с явной подсказкой команды. Файл: `src/claude_workflow_cli/data/payload/aidd/hooks/gate-workflow.sh`.

### Handoff‑интеграция и секции tasklist
- [x] Привести `tasks-derive` к канону `AIDD:HANDOFF_INBOX`. **Deps:** Wave 70 (канон tasklist). **AC:** `_HANDOFF_SECTION_HINTS` включает `## AIDD:HANDOFF_INBOX`, вставка происходит в этот блок для QA/Review/Research. Файл: `src/claude_workflow_cli/cli.py`.
- [x] Добавить проверку “handoff‑ссылок” для QA/Review. **Deps:** авто‑handoff. **AC:** проверка ищет `aidd/reports/qa/<ticket>.json` и reviewer report в tasklist; учитывает `AIDD:HANDOFF_INBOX`. Файл: `src/claude_workflow_cli/data/payload/aidd/hooks/gate-workflow.sh`.
- [x] Добавить контракт повторных запусков (QA/Review). **Deps:** идемпотентность handoff. **AC:** `tasks-derive` работает в режиме merge: новые задачи добавляются, существующие (по id) обновляются без дубликатов; документировать правило в `aidd/docs/anchors/{qa,review}.md`. Файлы: `src/claude_workflow_cli/cli.py`, `src/claude_workflow_cli/data/payload/aidd/docs/anchors/{qa,review}.md`.

### Tests и docs
- [x] Тесты на QA handoff. **Deps:** автогенерация QA handoff. **AC:** `tasks-derive --source qa` пишет в `AIDD:HANDOFF_INBOX`; `gate-qa`/`gate-workflow` реагируют на отсутствие записи; добавлены unit‑тесты и smoke‑сценарий. Файлы: `tests/test_tasks_derive.py` (или новый), `tests/repo_tools/smoke-workflow.sh`.
- [x] Тесты на review handoff. **Deps:** review report + tasks-derive review. **AC:** отчёт ревью → задачи в handoff; `gate-workflow` блокирует при отсутствии записей. Файлы: `tests/test_tasks_derive.py`, `tests/test_gate_workflow.py`.
- [x] Тесты на повторные запуски QA/Review. **Deps:** идемпотентность handoff. **AC:** двойной `tasks-derive` не добавляет дубликатов, обновляет существующие задачи по id; smoke‑сценарий проверяет повторный `/feature-dev-aidd:qa` и `/feature-dev-aidd:review`. Файлы: `tests/test_tasks_derive.py`, `tests/repo_tools/smoke-workflow.sh`.
- [x] Документация. **Deps:** все выше. **AC:** anchors `aidd/docs/anchors/qa.md` и `aidd/docs/anchors/review.md`, а также `/feature-dev-aidd:qa` и `/feature-dev-aidd:review` описывают auto‑handoff и формат источников; `reports-format.md` отражает review report. Файлы: `src/claude_workflow_cli/data/payload/aidd/docs/anchors/{qa,review}.md`, `src/claude_workflow_cli/data/payload/aidd/AGENTS.md`, `README.md`.

## Wave 72

_Статус: новый, приоритет 2. Цель — вынести интервью в верхний уровень (AskUserQuestionTool) и вести отдельный spec‑артефакт, оставив tasklist операционным. Шаг spec‑interview — опциональный (до/после tasklist)._

### EPIC A — Spec interview (top-level interview, optional)
- [x] Добавить stage `spec-interview` в `aidd/docs/sdlc-flow.md` и `aidd/docs/status-machine.md` как опциональный шаг (до/после tasklist), без требования `spec READY` перед implement.
- [x] Добавить anchor `aidd/docs/anchors/spec-interview.md` (MUST READ/UPDATE/NOT, порядок интервью, критерии READY).
- [x] Добавить шаблон `aidd/docs/spec/template.spec.yaml` (schema `aidd.spec.v1`, UI/UX, API, tradeoffs, risks, tests, rollout, observability).
- [x] Добавить команду `/feature-dev-aidd:spec-interview`: интервью через AskUserQuestionTool на верхнем уровне, запись лога `aidd/reports/spec/<ticket>.interview.jsonl`, запуск `spec-interview-writer`.
- [x] Добавить агента `aidd/agents/spec-interview-writer.md` (без AskUserQuestionTool): собирает spec, обновляет tasklist `AIDD:SPEC_PACK` + `AIDD:TEST_STRATEGY`.

### EPIC B — Tasklist как операционный чеклист
- [x] Обновить `aidd/docs/tasklist/template.md`: убрать in-tasklist SPEC/INTERVIEW, оставить `AIDD:SPEC_PACK` + `AIDD:TEST_STRATEGY` + ссылку на spec.
- [x] Обновить `/feature-dev-aidd:tasks-new`: scaffold tasklist, подтягивать spec (если есть), `/feature-dev-aidd:spec-interview` — опционален.
- [x] Обновить `aidd/docs/anchors/tasklist.md` и `aidd/docs/anchors/implement.md` под новый spec‑flow.
- [x] Обновить `aidd/agents/implementer.md` и `/feature-dev-aidd:implement`: убрать fail‑fast по spec, упоминания о вопросах — только в spec‑interview.

### EPIC C — Gates, checks, smoke, tests
- [x] Обновить `claude-workflow tasklist-check`: проверка `AIDD:SPEC_PACK`/`AIDD:TEST_STRATEGY` + `AIDD:NEXT_3` (без требования spec).
- [x] Обновить `gate-workflow` и сообщения: убрать обязательность spec, подсказка → `/feature-dev-aidd:tasks-new` (spec‑interview опционален).
- [x] Обновить `tests/repo_tools/smoke-workflow.sh` под spec‑file и новые секции tasklist.
- [x] Обновить тесты/хелперы под spec‑flow (tasklist_ready_text, prompt lint anchors, gate tests).

### EPIC D — Plugin & payload sync
- [x] Зарегистрировать `/feature-dev-aidd:spec-interview` и `spec-interview-writer` в `.claude-plugin/plugin.json`, добавить permissions в `.claude/settings.json`.
- [x] Удалить `tasklist-refiner` из payload и manifest (не используется в новом флоу).
- [x] Синхронизировать payload, обновить `src/claude_workflow_cli/data/payload/manifest.json`.

## Wave 73

_Статус: новый, приоритет 1. Цель — закрепить контракт уровней plan/spec/tasklist и синхронизировать review/qa с execution‑контрактом._

### EPIC A — Plan macro contract + iteration IDs
- [x] Обновить `aidd/docs/anchors/plan.md` и `aidd/docs/plan/template.md`: зафиксировать macro‑уровень (без чекбоксов/CLI‑команд), итерации как milestones с `iteration_id`, обновить формат `## Plan Review` без чекбоксов. **AC:** плановый шаблон и anchor запрещают execution‑детали, итерации имеют `iteration_id`. Файлы: `aidd/docs/anchors/plan.md`, `aidd/docs/plan/template.md`, `src/claude_workflow_cli/data/payload/aidd/docs/anchors/plan.md`, `src/claude_workflow_cli/data/payload/aidd/docs/plan/template.md`.
- [x] Обновить `planner`/`validator`/`plan-reviewer`: заменить “шаги” на milestones, требовать `iteration_id`, добавить проверки “plan слишком детализирован” (чекбоксы/CLI/микрошаги). **AC:** `planner` выдаёт I1..In с Goal/Boundaries/Outputs/DoD/Test categories/Risks; `validator` блокирует tasklist‑подобные планы. Файлы: `aidd/agents/planner.md`, `aidd/agents/validator.md`, `aidd/agents/plan-reviewer.md`, `src/claude_workflow_cli/data/payload/aidd/agents/planner.md`, `src/claude_workflow_cli/data/payload/aidd/agents/validator.md`, `src/claude_workflow_cli/data/payload/aidd/agents/plan-reviewer.md`.

### EPIC B — Tasklist iteration mapping & executability
- [x] Обновить tasklist‑шаблон/anchor/рефайнер/команду: добавить обязательный `iteration_id` в `AIDD:ITERATIONS_FULL` и `AIDD:NEXT_3`, требовать покрытия всех итераций из плана. **AC:** в tasklist у каждой итерации есть `iteration_id`, `AIDD:NEXT_3` содержит `iteration_id` и совпадает с планом. Файлы: `aidd/docs/tasklist/template.md`, `aidd/docs/anchors/tasklist.md`, `aidd/agents/tasklist-refiner.md`, `aidd/commands/tasks-new.md`, `src/claude_workflow_cli/data/payload/aidd/docs/tasklist/template.md`, `src/claude_workflow_cli/data/payload/aidd/docs/anchors/tasklist.md`, `src/claude_workflow_cli/data/payload/aidd/agents/tasklist-refiner.md`, `src/claude_workflow_cli/data/payload/aidd/commands/tasks-new.md`.
- [x] Расширить `tasklist-check`: валидировать `iteration_id` в `AIDD:ITERATIONS_FULL`/`AIDD:NEXT_3` и покрытие `AIDD:ITERATIONS` из плана. **AC:** check падает при отсутствии `iteration_id` или несовпадении с планом. Файлы: `src/claude_workflow_cli/tools/tasklist_check.py`, `aidd/scripts/tasklist-check.py`, тесты `tests/test_tasklist_check.py` (или новый).

### EPIC C — Test strategy vs test execution
- [x] Добавить `AIDD:TEST_EXECUTION` в tasklist и обновить инструкции: `AIDD:TEST_STRATEGY` = “что тестируем” (macro), `AIDD:TEST_EXECUTION` = “как запускать”. **AC:** tasklist содержит обе секции; команды/filters живут только в `AIDD:TEST_EXECUTION`. Файлы: `aidd/docs/tasklist/template.md`, `aidd/docs/anchors/tasklist.md`, `aidd/agents/tasklist-refiner.md`, `aidd/commands/tasks-new.md`, `aidd/docs/anchors/implement.md`, payload‑копии.
- [x] Обновить `tasklist-check` и lint: требовать `AIDD:TEST_EXECUTION` + базовые поля (profile/tasks/filters/when/reason). **AC:** lint и check валидируют новую секцию. Файлы: `src/claude_workflow_cli/tools/tasklist_check.py`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`.

### EPIC D — Spec interview coverage + spec-required policy
- [x] Привязать `/feature-dev-aidd:spec-interview` к итерациям плана: вопросы формируются по `iteration_id` и маппятся на секции spec. **AC:** интервью‑лог и spec содержат явные ссылки на `iteration_id`/решения. Файлы: `aidd/commands/spec-interview.md`, `aidd/docs/anchors/spec-interview.md`, payload‑копии.
- [x] Расширить spec‑шаблон полем `iteration_decisions` (или эквивалент) и обновить `spec-interview-writer` для заполнения + правила READY. **AC:** spec READY только при закрытых decision points для ближайших итераций. Файлы: `aidd/docs/spec/template.spec.yaml`, `aidd/agents/spec-interview-writer.md`, payload‑копии.
- [x] Зафиксировать политику обязательности spec (UI/API/DATA/E2E → mandatory) в tasklist‑anchor/refiner/`/feature-dev-aidd:tasks-new`. **AC:** при trigger‑условиях и отсутствии spec — `Status: BLOCKED` + `/feature-dev-aidd:spec-interview`. Файлы: `aidd/docs/anchors/tasklist.md`, `aidd/agents/tasklist-refiner.md`, `aidd/commands/tasks-new.md`, payload‑копии.

### EPIC E — Tasklist execution detail + traceability
- [x] Усилить шаблон `AIDD:NEXT_3`/`AIDD:ITERATIONS_FULL`: добавить `Steps (3–10)`, `Acceptance mapping`, `Risks & mitigations`. **AC:** NEXT_3 полностью исполним без “додумываний”. Файлы: `aidd/docs/tasklist/template.md`, `aidd/agents/tasklist-refiner.md`, payload‑копии.
- [x] Добавить `AIDD:QA_TRACEABILITY` (AC → check → result → evidence) и обновить QA anchor/agent. **AC:** QA пишет traceability в tasklist и указывает evidence. Файлы: `aidd/docs/tasklist/template.md`, `aidd/docs/anchors/qa.md`, `aidd/agents/qa.md`, payload‑копии.

### EPIC F — Review/QA contract checks + orchestration
- [x] Обновить anchors review/qa: MUST READ spec (если есть), проверять “tasklist executable” (NEXT_3/ITERATIONS_FULL/TEST_EXECUTION), обновлять `AIDD:CONTEXT_PACK → Blockers summary`. **AC:** review/qa блокируют неисполняемый tasklist и фиксируют blockers summary. Файлы: `aidd/docs/anchors/review.md`, `aidd/docs/anchors/qa.md`, payload‑копии.
- [x] Убрать orchestration‑инструменты из агентов `reviewer`/`qa` и усилить схему findings (`scope=iteration_id`, `blocking`). **AC:** агенты только анализируют и обновляют tasklist; команды продолжают писать отчёты/derive/progress. Файлы: `aidd/agents/reviewer.md`, `aidd/agents/qa.md`, `aidd/commands/review.md`, `aidd/commands/qa.md`, payload‑копии.

### EPIC G — Payload sync + checks
- [x] Финальный sync: `scripts/sync-payload.sh --direction=to-root`, `python3 tools/check_payload_sync.py`, обновить тесты/линтеры при необходимости. **AC:** payload и корневые промпты синхронизированы, lint/tests проходят. Файлы: `scripts/sync-payload.sh`, `tools/check_payload_sync.py`, тесты по месту.

### EPIC H — Answers capture (chat → artifacts → validators)
### EPIC H — Answers capture (chat → artifacts → validators)
- [x] Ввести единый формат `AIDD:ANSWERS` и обновить шаблоны/anchors: описать, что ответы из чата фиксируются в артефактах через `AIDD:ANSWERS` (единый формат `Answer N:...`/`Answer N: TBD`) и указать место фиксации в PRD/Plan. **AC:** в PRD/Plan шаблонах и anchors есть явный блок `AIDD:ANSWERS` с одинаковым форматом. Файлы: `aidd/docs/prd/template.md`, `aidd/docs/plan/template.md`, `aidd/docs/anchors/idea.md`, `aidd/docs/anchors/plan.md`, payload‑копии.
- [x] Обновить `/feature-dev-aidd:idea-new` + `analyst`: поддержать `ANSWERS:` в пользовательском вводе, записывать ответы в `## Диалог analyst` и/или `AIDD:ANSWERS`, обновлять `Status: READY` и `Updated`, запускать `analyst-check`. **AC:** ответы из чата попадают в PRD, `analyst-check` проходит при полном покрытии Q/A, иначе статус PENDING/BLOCKED. Файлы: `aidd/commands/idea-new.md`, `aidd/agents/analyst.md`, payload‑копии.
- [x] Обновить `analyst-check` для чтения `AIDD:ANSWERS` как источника истины (если он присутствует) и устранить дублирование/рассинхронизацию с `## Диалог analyst`. **AC:** при наличии `AIDD:ANSWERS` валидатор считает ответы закрытыми, блокирует только реальные пропуски. Файлы: `src/claude_workflow_cli/tools/analyst_guard.py`, тесты.
- [x] Обновить `/feature-dev-aidd:plan-new` + `planner`/`validator`: поддержать `ANSWERS:` и закрывать вопросы в плане (перенос в `AIDD:DECISIONS` или пометка resolved), валидатор не должен пропускать блокеры без ответов. **AC:** ответы фиксируются в `docs/plan/<ticket>.md`, открытые вопросы не остаются в READY‑плане. Файлы: `aidd/commands/plan-new.md`, `aidd/agents/planner.md`, `aidd/agents/validator.md`, payload‑копии.

## Wave 74

_Статус: новый, приоритет 1. Цель — перейти на marketplace‑only дистрибуцию и заменить `claude-workflow` на локальные python‑скрипты, сохранив тесты и целостность._

### EPIC A — Marketplace‑only структура плагина
- [x] Перевести plugin root на корень репозитория: перенести `aidd/{commands,agents,hooks,config}` в `{commands,agents,hooks,config}`, перенести `aidd/.claude-plugin/plugin.json` в `.claude-plugin/plugin.json`. **AC:** команды/агенты/хуки читаются из корня плагина; старый путь не используется.
- [x] Обновить `.claude-plugin/marketplace.json` под `source: "./"` и корректную версию/описание. **AC:** `/plugin marketplace add owner/repo` + `/plugin install <plugin>@<marketplace>` работают с этим репо.
- [x] Вынести workspace‑шаблоны в `templates/aidd/` (копии `aidd/docs`, `aidd/reports`, `aidd/config`, `conventions.md`, `AGENTS.md`). **AC:** шаблоны не лежат в plugin root, а используются только для init.

### EPIC B — Python runtime вместо `claude-workflow`
- [x] Перенести логику runtime из `src/claude_workflow_cli/*` в `tools/` и `hooks/context_gc/` (research, progress, qa, prd/plan review, tasks-derive, reviewer-tests, status/index, context-gc, set-active-*). **AC:** функциональность доступна из python‑модулей без CLI‑инициализатора.
- [x] Добавить **временные** обёртки `scripts/aidd_*.py` для миграции от `claude-workflow`. **AC:** хуки/команды/агенты временно вызывают `python3 scripts/aidd_*.py...`, без `claude-workflow`.
- [x] Обновить все ссылки на `claude-workflow` в `commands/`, `agents/`, `hooks/`, `docs/` и `config/` на новые python‑обёртки. **AC:** `rg claude-workflow` не находит обращений в runtime‑путях плагина.
- [x] Обновить зависимости в `pyproject.toml` под новый runtime‑пакет (включая optional extras для call‑graph). **AC:** проект запускается без `claude-workflow` и сохраняет feature‑паритет.

### EPIC C — Init команды для `aidd`
- [x] Добавить `/feature-dev-aidd:aidd-init` и runtime‑инициализацию, которая разворачивает `./aidd` из `templates/aidd` без перезаписи пользовательских файлов. **AC:** повторный запуск идемпотентен, `reports/*` содержит `.gitkeep`.
- [x] Обновить хуки/доки на новый init‑путь. **AC:** инструкции в README и workflow указывают `/feature-dev-aidd:aidd-init` как обязательный шаг после установки плагина.

### EPIC D — Tests и контроль целостности
- [x] Обновить тесты и smoke‑сценарии под запуск `${CLAUDE_PLUGIN_ROOT}/tools/*.sh` и `/feature-dev-aidd:aidd-init`. **AC:** существующие тесты остаются; добавлены проверки init и вызовов runtime.
- [x] Удалить/заархивировать CLI‑payload и sync‑скрипты, если они больше не используются (`src/claude_workflow_cli/data/payload`, `scripts/sync-payload.sh`, `tools/check_payload_sync.py`). **AC:** тесты/доки не зависят от payload‑механизма.
- [x] Перевести unit‑тесты, завязанные на `tools/cli`, на модульные entrypoints/runtime helpers (research/reviewer/resources). **AC:** тесты проходят без `tools/cli.py`.

### EPIC E — Документация marketplace‑only
- [x] Переписать `README.md`/`README.en.md`/`AGENTS.md` под поток `/plugin marketplace add` → `/plugin install` → `/feature-dev-aidd:aidd-init`. **AC:** нет упоминаний `claude-workflow init/sync/upgrade`.
- [x] Обновить `AGENTS.md`: зафиксировать marketplace‑only и отказ от CLI‑установки. **AC:** ADR синхронизирована с новой моделью.

### EPIC F — Запуск runtime без обёрток
- [x] Определить канонический формат запуска runtime без `scripts/` и без `src/`: `${CLAUDE_PLUGIN_ROOT}/tools/<command>.sh...` и зафиксировать его в документации. **AC:** единый шаблон запуска описан; в коде используются только новые вызовы.
- [x] Перенести init‑логику из `scripts/aidd_init.py` в runtime, обновить `/feature-dev-aidd:aidd-init` на `${CLAUDE_PLUGIN_ROOT}/tools/init.sh`. **AC:** `/feature-dev-aidd:aidd-init` работает без `scripts/aidd_init.py`; повторный запуск идемпотентен.
- [x] Обновить `commands/`, `agents/`, `hooks/` и `hooks/hooks.json` (включая `aidd/hooks/hooks.json`) на вызовы `${CLAUDE_PLUGIN_ROOT}/tools/*.sh` и `${CLAUDE_PLUGIN_ROOT}/hooks/*.sh`; синхронизировать `allowed-tools` в командах/агентах. **AC:** `rg "scripts/aidd_"` не находит обращений в runtime‑путях.
- [x] Удалить обёртки и bootstrap + убрать src‑layout: `scripts/aidd_*.py`, `scripts/_aidd_bootstrap.py`, `src/`. **AC:** файлы отсутствуют, сборка не зависит от них.
- [x] Обновить smoke/tests/docs под новый путь запуска и плоский layout (включая `tests/repo_tools/smoke-workflow.sh`, тесты CLI, README/дев‑доки). **AC:** `tests/repo_tools/ci-lint.sh` и `tests/repo_tools/smoke-workflow.sh` проходят, упоминаний `scripts/aidd_*.py` нет.

### EPIC G — Python‑entrypoint hook‑скрипты (вызов как `.sh`)
- [x] Зафиксировать стандарт: hook‑скрипты остаются в `hooks/*.sh`, но реализованы на Python с shebang (`#!/usr/bin/env python3`) и вызываются как `${CLAUDE_PLUGIN_ROOT}/hooks/*.sh`. **AC:** стандарт описан в `AGENTS.md`/`AGENTS.md`, пример обновлён в `hooks/format-and-test.sh`.
- [x] Добавить общий `hooks/hooklib.py`: root‑резолвинг, payload parsing, stage/ticket/slug, чтение `config/*.json`, event‑log, JSON‑ответы для hook API, git‑wrapper. **AC:** hook‑скрипты используют только `CLAUDE_PLUGIN_ROOT` (без fallback); при отсутствии — явная ошибка и понятный exit code.
- [x] Переписать `hooks/context-gc-*.sh` как Python‑entrypoints (precompact/sessionstart/pretooluse/userprompt/stop) и перенести логику в `hooks/context_gc/`. **AC:** `hooks/hooks.json` вызывает только `hooks/context-gc*.sh`; `tests/test_context_gc.py` и smoke проходят.
- [x] Переписать `hooks/gate-workflow.sh` в Python‑entrypoint: analyst‑check, plan/prd review, research checks, tasklist‑progress, reviewer marker, handoff. **AC:** `rg "bash" hooks/gate-workflow.sh` не находит bash‑логики; `tests/test_gate_workflow.py`/`tests/test_gate_researcher.py` проходят.
- [x] Смягчить stage‑gate: блокировать только при явно заданной стадии вне `implement|review|qa`. **AC:** отсутствие `.active_stage` не блокирует gate‑workflow.
- [x] Переписать `hooks/gate-tests.sh` в Python‑entrypoint: gates config, test rules, reviewer marker, research‑targets checks. **AC:** `tests/test_gate_tests_hook.py` проходит; выходы и exit‑коды совпадают с текущими.
- [x] Переписать `hooks/gate-qa.sh` в Python‑entrypoint: QA‑агент (логика из `tools/qa_agent.py`), отчёт, handoff, debounce. **AC:** `tests/test_gate_qa.py` проходит; формат `aidd/reports/qa/*.json` совместим.
- [x] Переписать `hooks/gate-prd-review.sh` в Python‑entrypoint (или удалить при отсутствии точки вызова). **AC:** нет висячих hook‑скриптов; `tests/test_gate_prd_review.py` синхронизирован.
- [x] Переписать `hooks/format-and-test.sh` и `hooks/lint-deps.sh` в Python‑entrypoints с сохранением поведения (`AIDD_TEST_*`, deps allowlist). **AC:** `tests/test_format_and_test.py` и `tests/test_post_hook_paths.py` проходят.
- [x] Удалить `hooks/lib.sh` (или оставить пустой shim) и убрать `source` из всех хуков. **AC:** `rg "lib.sh" hooks/*.sh` пустой.
- [x] Обновить `hooks/hooks.json`, smoke и документацию на единый формат вызовов `${CLAUDE_PLUGIN_ROOT}/hooks/*.sh` без inline `python3 -m`. **AC:** нет упоминаний устаревших CLI‑вызовов в hook‑контексте.
- [x] Перенести логику runtime в `hooks/` и `tools/`, затем удалить устаревший runtime‑пакет полностью. **AC:** `rg` не находит совпадений старых runtime‑путей; все хуки/инструменты работают без импорта устаревшего пакета.

### EPIC H — Python‑entrypoint runtime‑скрипты (вызов как `.sh`)
- [x] Зафиксировать директорию runtime‑entrypoints: `tools/*.sh` (только в plugin root, без копий в `templates/aidd/`) и базовый шаблон скрипта (shebang, **строгое** требование `CLAUDE_PLUGIN_ROOT`, запуск логики напрямую). **AC:** стандарт зафиксирован в `AGENTS.md`, примеры обновлены.
- [x] Сгенерировать entrypoints для всех runtime‑команд: `init`, `set-active-feature`, `identifiers`, `set-active-stage`, `prd-review`, `plan-review-gate`, `prd-review-gate`, `tasklist-check`, `researcher-context`, `analyst-check`, `research-check`, `research`, `reviewer-tests`, `review-report`, `tasks-derive`, `context-pack`, `index-sync`, `status`, `tests-log`, `qa`, `progress`. **AC:** каждая команда доступна как `${CLAUDE_PLUGIN_ROOT}/tools/<command>.sh`.
- [x] Удалить монолитный `tools/cli.py` и перевести entrypoints на прямой вызов модулей; добавить CLI‑обвязки для `context-pack`, `index-sync`, `prd-review` (с index‑sync). **AC:** entrypoints не зависят от роутера CLI.
- [x] Уточнить `tasks-derive`: вставка handoff‑блоков под `AIDD:HANDOFF_INBOX`, merge по `id`/signature и корректные задачи QA/Research (`QA tests: fail`, recommendations, reuse candidates). **AC:** `tests/test_tasks_derive.py` проходит.
- [x] Обновить `commands/*.md` и `agents/*.md` (tools whitelist + примеры) на новые runtime‑скрипты `${CLAUDE_PLUGIN_ROOT}/tools/*.sh`. **AC:** в командах/агентах нет inline `python3 -m` вызовов runtime.
- [x] Обновить документацию и шаблоны: `README.md`, `README.en.md`, `AGENTS.md`, `templates/aidd/conventions.md`, `templates/aidd/docs/prd/template.md`. **AC:** в docs нет упоминаний `python3 -m` как основного способа вызова.
- [x] Обновить сообщения/подсказки в хуках и runtime, которые ссылаются на устаревшие CLI‑вызовы (например, в `hooks/gate-workflow.sh`, `hooks/gate-tests.sh`, `hooks/gate-qa.sh`). **AC:** все подсказки используют новые пути `${CLAUDE_PLUGIN_ROOT}/tools/<command>.sh`.
- [x] Обновить тесты и smoke: `tests/helpers.py`, `tests/test_init_aidd.py`, `tests/test_research_command.py`, `tests/test_cli_subcommands.py`, `tests/repo_tools/smoke-workflow.sh` — переход на новые runtime‑entrypoints. **AC:** тесты/смоук вызывают только entrypoint‑скрипты.
- [x] Удалить устаревший runtime‑пакет целиком и очистить все документы/подсказки от упоминаний устаревшего CLI (оставить только `tools/*.sh`). **AC:** `rg` не находит совпадений старых runtime‑путей в доках/коде; `CHANGELOG.md`/`AGENTS.md` отражают удаление.

### EPIC J — Cleanup runtime vs dev‑only
- [x] Убрать runtime‑smoke entrypoint, оставив repo‑smoke в `tests/repo_tools/`. **AC:** в `tools/` нет smoke‑скрипта; runtime‑доки не ссылаются на smoke; dev‑smoke остаётся в `tests/repo_tools/`.
- [x] Удалить документ миграции CLI и все ссылки на него. **AC:** в репозитории нет упоминаний документа миграции CLI.
- [x] Решение по объединению runtime‑скриптов: оставить отдельные entrypoints (единый скрипт не вводим). **AC:** решение зафиксировано в backlog.
- [x] Реализация единого entrypoint не требуется (решение: сохранить per‑command entrypoints). **AC:** никаких новых unified‑entrypoint изменений не внесено.
- [x] Удалить dev‑playbook‑доки и убрать ссылки. **AC:** в репозитории нет ссылок на удалённые playbook‑доки.
- [x] Разделить smoke vs runtime: dev‑smoke отмечен как dev‑only, runtime‑доки не требуют `tests/repo_tools/*`. **AC:** dev‑only упомянуты отдельно от runtime‑шагов.

### EPIC I — Marketplace install hardening
- [x] Выровнять команды с namespace‑правилами плагинов или явно задокументировать alias‑сценарий. **AC:** `README.md`, `README.en.md`, `AGENTS.md`, `commands/*.md` содержат корректные примеры (`/feature-dev-aidd:<command>` или описанный alias), новые пользователи не получают `unknown command`. Файлы: `README.md`, `README.en.md`, `AGENTS.md`, `commands/*.md`.
- [x] Сделать marketplace‑источник устойчивым для GitHub/URL‑установок (явный `source` для GitHub или документация об ограничениях относительных путей). **AC:** `/plugin marketplace add owner/repo` и добавление через URL‑marketplace приводят к успешной установке без ошибок путей. Файлы: `.claude-plugin/marketplace.json`, `README.md`, `README.en.md`.
- [x] Добавить install‑диагностику (`tools/doctor.sh` или аналог) для проверки `python3`, `rg`, `git`, `CLAUDE_PLUGIN_ROOT`, наличия `aidd/` и подсказки про `/feature-dev-aidd:aidd-init`. **AC:** команда возвращает понятные ошибки и шаги устранения; README/доки ссылаются на диагностику. Файлы: `tools/doctor.sh`, `README.md`, `AGENTS.md` (и при необходимости `README.en.md`).
- [x] Дополнить `.claude-plugin/plugin.json` метаданными (`author`, `repository`, `homepage`, `license`) и синхронизировать версии с marketplace/CHANGELOG. **AC:** плагин‑менеджер показывает метаданные, версии в `plugin.json` и `marketplace.json` совпадают. Файлы: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`.

### EPIC K — Path resolution hardening (plugin cache vs workspace)
- [x] Унифицировать корневую логику `tools.feature_ids.resolve_project_root`: убрать приоритет `CLAUDE_PLUGIN_ROOT` и делать детекцию только по workspace‑пути (`cwd` → `./aidd` → `.`, если `cwd` уже `aidd` — использовать его), чтобы записи не уходили в кеш плагина. **AC:** при установленном плагине в кеше и запуске из workspace все записи (`docs/.active_*`, PRD scaffold) остаются в `./aidd`; тесты `tests/test_feature_ids_root.py` обновлены/проходят.
- [x] Убрать `--target` из runtime CLI (и из help/доков), оставить один источник истины: `cwd/aidd` как рабочий root. **AC:** `--target` не принимается нигде; при запуске из корня проекта всё пишется в `./aidd`; инструкции в `commands/*.md`/`AGENTS.md` не ссылаются на `--target`.
- [x] Исправить hook‑root резолвинг: `hooks.hooklib.resolve_project_root()` должен учитывать `cwd` из hook payload (если передан), а хуки (`gate-*`, `lint-deps`) должны использовать этот путь, а не `Path.cwd()`. **AC:** хуки корректно находят `aidd/docs` даже при запуске из произвольного CWD; smoke/test покрывают кейс.
- [x] Выправить `hooks/format-and-test.sh`: убрать использование `CLAUDE_PLUGIN_ROOT` как кандидата project root; использовать `CLAUDE_SETTINGS_PATH`/workspace root и надёжный поиск `./aidd`. **AC:** форматтер/тесты пишут отчёты в workspace `aidd/reports/**`, не в кеш плагина; `tests/test_post_hook_paths.py` обновлён и проходит.
- [x] Нормализовать относительные пути в gate‑скриптах (`tools/prd_review_gate.py`, `tools/plan_review_gate.py`, `tools/tasklist_check.py`): вычислять относительность от найденного project root, а не от `Path.cwd()`. **AC:** `--file-path` и report‑пути корректно обрабатываются при любом CWD; `tests/test_gate_*` обновлены при необходимости.
- [x] Обновить документацию по root‑резолвингу и кешу плагина: явно зафиксировать, что рабочий root — это workspace, а `CLAUDE_PLUGIN_ROOT` используется только для ресурсов плагина. **AC:** `AGENTS.md` (и при необходимости README) описывают правило и не содержат двусмысленностей.
- [x] Зафиксировать в документации правила из офиц. доки Claude Code: плагин **копируется в кеш**, доступ к файлам **вне корня запрещён**, пути в `plugin.json` должны быть относительными `./`, а скрипты/хуки должны использовать `${CLAUDE_PLUGIN_ROOT}`; cwd хуков не гарантирован. **AC:** в `AGENTS.md` (и при необходимости README) есть явное описание и ссылка на `https://code.claude.com/docs/en/plugins-reference#plugin-caching-and-file-resolution`.

### EPIC L — Убрать legacy дерево и вынести dev‑правила в `AGENTS.md`
- [x] Перенести legacy CI workflow в `.github/workflows/ci.yml` и обновить шаги на новые пути (`tests/repo_tools/ci-lint.sh`). **AC:** CI запускается из корня и не использует старые пути.
- [x] Перенести markdownlint/pre-commit конфиги в корень. **AC:** `tests/repo_tools/ci-lint.sh` использует корневой `.markdownlint.yaml`, pre‑commit работает без legacy путей.
- [x] Перенести тесты в `tests/**` и обновить все ссылки/дискавери тестов. **AC:** `python3 -m unittest discover -s tests -t .` проходит, упоминаний старых путей нет.
- [x] Перенести repo tools в `tests/repo_tools/**` и обновить пути в скриптах/доках/хуках. **AC:** `tests/repo_tools/ci-lint.sh` и `tests/repo_tools/smoke-workflow.sh` запускаются из корня.
- [x] Перенести backlog в `backlog.md` (корень) и обновить все ссылки. **AC:** `backlog.md` в корне.
- [x] Свернуть содержание legacy doc tree в корневой `AGENTS.md` (dev‑гайд, релизы, prompt‑versioning, reports‑format, migration, install‑decision, templates) и удалить legacy docs. **AC:** все dev‑правила доступны в `AGENTS.md`.
- [x] Обновить все ссылки на новые пути (`README*`, `CHANGELOG.md`, `CONTRIBUTING.md`, `hooks/*`, `tests/repo_tools/*`, CI). **AC:** `rg` не находит старых путей вне `backlog.md`.
- [x] Удалить устаревший каталог разработки. **AC:** каталога нет, тесты/линтеры/смоук работают из корня.

## Wave 75

_Статус: новый, приоритет 2. A) research+docs+tests. Перенос из Wave 45/52/61. Цель — end‑to‑end call graph для Researcher._

### Research core: auto profile + graph-mode
- [x] W75-1 `tools/researcher_context.py`: разделить fast-scan vs graph-scan, добавить `--graph-mode auto|focus|full`, сохранять full graph в sidecar и columnar, всегда писать `call_graph_*` метаданные (engine/filter/limit/warning), при отсутствии tree-sitter печатать INSTALL_HINT + warning. Deps: -
- [x] W75-2 `tools/research.py` + `tools/research.sh`: в `--auto` включать `--deep-code` и call graph для kt/kts/java, для остальных — fast scan; логировать выбранный профиль; WARN «0 matches → сузить paths/keywords или graph-only»; поддержать `--graph-mode`/`--graph-engine none`. Deps: W75-1.
- [x] W75-3 `tools/reports_pack.py`: гарантировать сохранение `call_graph_*` метаданных в pack даже при пустом графе (engine/filter/limit/warning), обновить бюджеты/trim при необходимости. Deps: W75-1.

### Docs & adoption
- [x] W75-4 `commands/researcher.md`: описать авто‑сбор graph, `--graph-engine none`, `--graph-mode`, ссылку на `call_graph_full_path`. Deps: W75-1,W75-2.
- [x] W75-5 `agents/researcher.md`: требовать проверять `call_graph`/`import_graph`; при пустом графе запускать повторный сбор через `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --graph-engine ts --call-graph` или фиксировать WARN. Deps: W75-1.
- [x] W75-6 `agents/analyst.md`: упомянуть, что для “тонкого” контекста инициируется research с call graph. Deps: W75-2.
- [x] W75-7 `templates/aidd/docs/research/template.md`: добавить секцию с кратким summary call graph и ссылкой на full graph файл. Deps: W75-1.
- [x] W75-8 Документация: `AGENTS.md`, `README.md`, `README.en.md` — таблица «когда graph обязателен», примеры WARN/INSTALL_HINT, troubleshooting для пустого контекста. Deps: W75-1,W75-2.

### Tests
- [x] W75-9 `tests/test_researcher_context.py` + `tests/test_research_command.py`: кейсы JVM auto graph, non-JVM fast scan, missing tree-sitter warning, zero-matches hint, `--graph-mode`. Deps: W75-1,W75-2.
- [x] W75-10 `tests/test_gate_researcher.py` + `tests/repo_tools/smoke-workflow.sh`: e2e проверки auto‑режима, наличия `call_graph`, и пути `--graph-engine none`. Deps: W75-2.

## Wave 76

_Статус: новый, приоритет 2. B) hooks+init+examples+tests. Цель — language‑agnostic hooks/init под marketplace‑only._

### Hooks & config
- [x] W76-1 `hooks/format-and-test.sh`: вынести `COMMON_PATTERNS`/`DEFAULT_CODE_PATHS`/`DEFAULT_CODE_EXTENSIONS` в `.claude/settings.json` (новые ключи), добавить дефолты для npm/py/go/rust/.NET; обновить чтение/валидацию. Deps: -
- [x] W76-2 `hooks/lint-deps.sh` + `templates/aidd/config/gates.json` + `templates/aidd/config/allowed-deps.txt`: сделать список dependency‑файлов конфигурируемым (Gradle/npm/py/go/rust/.NET) либо добавить режим “gradle-only”. Deps: -
- [x] W76-3 `templates/aidd/config/context_gc.json` + `hooks/hooklib.py`: привести guard‑regex к нейтральному набору build tools и синхронизировать дефолты. Deps: -

### Init & examples
- [x] W76-4 `tools/init.py` + `commands/aidd-init.md`: убрать Gradle‑специфику из init; опционально добавить `--detect-build-tools` для заполнения `.claude/settings.json`. Deps: W76-1.
- [x] W76-5 Решить судьбу демо‑проекта: оставить как optional example или пометить legacy/удалённым; обновить `README.md`, `README.en.md`, `AGENTS.md`. Deps: -
- [x] W76-6 Пересмотреть gradle helper (если нужен): добавить/удалить helper в `examples/` и зафиксировать в документации. Deps: W76-5.

### Tests
- [x] W76-7 `tests/test_init_aidd.py`, `tests/test_format_and_test.py`, `tests/repo_tools/smoke-workflow.sh`: проверки новых config‑ключей и language‑agnostic поведения. Deps: W76-1,W76-4.

## Wave 77

_Статус: новый, приоритет 1. Цель — запретить правки кода на review/qa и закрепить handoff‑контракт._

### EPIC A — Review/QA edit policy + handoff schema
- [ ] W77-1 `agents/reviewer.md`, `agents/qa.md`: добавить hard‑policy (редактировать только `aidd/docs/tasklist/<ticket>.md`), `MUST NOT` (без правок кода/конфигов/тестов/CI и без «чинить самому»), требование handoff‑задач на каждое замечание (fact→risk→recommendation + `scope/DoD/Boundaries/Tests`), удалить tool `Write`. Обновить `prompt_version/source_version`, прогнать `tests/repo_tools/prompt-version` и `tests/repo_tools/lint-prompts.py`. Deps: -
- [ ] W77-2 `templates/aidd/docs/anchors/{review,qa}.md`: добавить явный запрет правок вне tasklist и правило «каждый finding → handoff в `AIDD:HANDOFF_INBOX`». Для QA указать, что автогенерируемые отчёты в `aidd/reports/**` допустимы. Deps: W77-1.
- [ ] W77-3 `templates/aidd/docs/tasklist/template.md`: расширить `AIDD:HANDOFF_INBOX` схемой задачи (id, source, scope, DoD, Boundaries, Tests, Notes) и примером заполнения для review/qa. Deps: W77-1.

## Wave 78

_Статус: новый, приоритет 1. Цель — переработка Research (воспроизводимость, токено‑экономность, hybrid ast‑grep)._

### EPIC A — P0: Стабильность и корректность артефактов Research
- [x] W78-1 `tools/researcher_context.py`, `tools/research.py`, `templates/aidd/config/conventions.json`: нормализовать keywords (tokenize, стоп‑слова RU/EN, min длина, whitelist коротких), вынести slug_hint/notes в `keywords_raw`/`note`, извлечь `non_negotiables` из `dod:` и не включать в keywords; обновить pack + `templates/aidd/docs/research/template.md`. **AC:** `targets.json`/context без мусорных токенов, `non_negotiables` хранится отдельно и попадает в pack. Deps: -
- [x] W78-2 `tools/research.py`, `tools/researcher_context.py`, `tools/reports_pack.py`: лимитировать `call_graph_filter` (max_chars + max_tokens), добавить `filter_stats`/`filter_trimmed` в отчёт/pack и warn при trimming. **AC:** filter в лимитах, без стоп‑слов, trimming отражён. Deps: W78-1.
- [x] W78-3 `tools/researcher_context.py`: пред‑валидация путей (invalid_paths) + auto‑discover модулей (по settings.gradle(.kts) include и поиску по keywords), сохранять `paths_discovered` и merged paths в targets. **AC:** несуществующие пути помечены, найденные пути существуют и используются в scan. Deps: W78-1.
- [x] W78-4 `tools/reports_pack.py`, `tools/research.py`: санитизация output — pack/JSON пишутся только в файлы, stdout только логи; добавить post‑write JSON/YAML validity check (fail fast). **AC:** pack/context валидны, без мусора/дублей. Deps: -
- [x] W78-5 `tools/researcher_context.py`: улучшить `tests_detected` для multi‑module (`**/src/test/**`, `**/test/**`, Gradle plugin hints), добавить `tests_evidence` и `suggested_test_tasks` в context/pack. **AC:** для типичных JVM монорепо tests_detected=true с evidence. Deps: W78-3.
- [x] W78-6 `templates/aidd/docs/research/template.md`, `templates/aidd/docs/anchors/research.md`, `tools/reports_pack.py`, `tools/tasks_derive.py`: закрепить новые поля (например `keywords_raw`, `non_negotiables`, `tests_evidence`, `suggested_test_tasks`, `call_graph_edges_path`, `filter_stats`, `filter_trimmed`, `paths_discovered`) и обратную совместимость. **AC:** schema описан в шаблоне/anchors, consumers tolerant к отсутствующим полям; `call_graph_edges_path` опционален до W78-17. **Tests:** `tests/test_reports_pack.py`, `tests/test_tasks_derive.py`. Deps: W78-1,W78-2,W78-3,W78-5.

### EPIC B — P1: Hybrid ast-grep scan
- [x] W78-7 `tools/ast_grep_scan.py`, `tools/research.py`, `templates/aidd/config/conventions.json`: добавить шаг ast-grep scan (jsonl output), конфиг `ast_grep.enabled/required_for_langs`, graceful warning если cli нет; **scoped scan** только по `targets.paths`/`paths_discovered` с лимитами (max files + max matches). **AC:** `aidd/reports/research/<ticket>-ast-grep.jsonl` создаётся при включении и не раздувает контекст. **DoD:** дефолты в conventions (`enabled=false`, `required_for_langs=[]`, `max_files`, `max_matches`, `timeout_s`). Deps: -
- [x] W78-8 `templates/aidd/ast-grep/rules/**`: добавить rule-pack (jvm/common/web/mobile) + базовые правила (Spring endpoints, principals, tests). **AC:** ast-grep на JVM repo даёт матчи. Deps: W78-7.
- [x] W78-9 `tools/reports_pack.py` (или новый pack builder): добавить `*-ast-grep.pack.json|toon` с top‑N матчами + ссылкой на jsonl. **AC:** pack в бюджетах, содержит rule_id/file/line/snippet/why. Deps: W78-7.
- [x] W78-10 `templates/aidd/docs/research/template.md`, `agents/researcher.md`, `commands/researcher.md`: секция `AIDD:AST_GREP_EVIDENCE`, pack-first usage; **source-of-truth** для промптов — `agents/` + `commands/`, template только для docs. Bump prompt_version + lint. **AC:** исследователь использует pack как источник фактов. Deps: W78-9.
- [x] W78-11 `tools/tasks_derive.py`: derivation handoff из ast-grep pack (`astgrep:<rule_id>:<file>:<line>`), без дублей. **AC:** задачи появляются в `AIDD:HANDOFF_INBOX` после researcher. Deps: W78-9.

### EPIC C — P1: Review/QA write-guard (no-fix)
- [x] W78-13 `agents/reviewer.md`, `agents/qa.md`, `templates/aidd/docs/anchors/{review,qa}.md`: усилить no-fix policy + формализованный handoff (scope/blocking/DoD/Tests); **source-of-truth** для промптов — `agents/`, anchors — в `templates/aidd/docs/anchors/`. Bump prompt_version + lint. **AC:** отчёты фиксируют задачи, без правок кода. Deps: -

### EPIC D — P2: Форматы и авто-теги
- [x] W78-14 `templates/aidd/docs/research/template.md`, `AGENTS.md`: закрепить pack-first/JSONL стандарт (ast-grep, interview, call graph), примеры ссылок. **AC:** шаблоны и docs описывают pack-first. Deps: W78-9.
- [x] W78-15 `tools/researcher_context.py`, `templates/aidd/config/conventions.json`: auto‑tagging по slug/paths + мэппинг rule-pack (jvm/web/mobile/common). **AC:** tags не пустые при узнаваемом slug/path. Deps: W78-8.

### EPIC E — P0/P1/P2: Graph views + policy (large graph is DB, not context)
- [x] W78-16 `AGENTS.md`, `templates/aidd/AGENTS.md`, `templates/aidd/docs/anchors/{research,plan,tasklist,implement,review,qa}.md`: зафиксировать Graph Read Policy (MUST читать `*.pack.*`/`graph-slice`, `rg` по `*.edges.jsonl`; MUST NOT `Read` full `*-call-graph-full.json`). **Boundaries:** docs only. **DoD:** единый текст правила во всех документах. **Tests:** none. Deps: -
- [x] W78-17 `tools/research.py`, `tools/reports_pack.py` (или новый `tools/call_graph_views.py`): генерировать grep-friendly view `aidd/reports/research/<ticket>-call-graph.edges.jsonl` + поле `call_graph_edges_path` в context/pack. **DoD:** view пишется автоматически при наличии full graph, формат line‑per‑edge с `caller/callee/file/line/lang`, генерация streaming/чанками (без загрузки full graph целиком). **Tests:** `tests/test_researcher_call_graph.py` (unit) + smoke. Deps: W78-2.
- [x] W78-18 `tools/reports_pack.py`, `tools/research.py`: отдельный pack `aidd/reports/research/<ticket>-call-graph.pack.json|toon` (entrypoints/hotspots/top‑edges + links на full/jsonl), budgets ≤ лимитов. **DoD:** pack всегда создаётся, если есть граф; при отсутствии графа — pack с `status: unavailable` + how‑to‑enable. **Tests:** `tests/test_reports_pack.py` (pack created, budget). Deps: W78-17.
- [x] W78-19 `agents/{researcher,planner,tasklist-refiner,implementer,reviewer,qa}.md`: закрепить policy “pack/slice only”, добавить fail‑fast (“если pack отсутствует → blocker/handoff”), добавить allowed tool `Bash(${CLAUDE_PLUGIN_ROOT}/tools/graph-slice.sh:*)`; **source-of-truth** — `agents/` (не `templates/aidd/**`). Bump prompt_version + lint. **DoD:** одинаковые формулировки, без чтения raw graph. **Tests:** `tests/repo_tools/prompt-version`, `tests/repo_tools/lint-prompts.py`. Deps: W78-16,W78-18,W78-20.
- [x] W78-20 `tools/graph_slice.py`, `tools/graph-slice.sh`: утилита graph-slice (`--ticket`, `--query`, `--max-edges`, `--max-nodes`) → pack в `aidd/reports/context/<ticket>-graph-slice-<sha1>.pack.json` + `...-graph-slice.latest.pack.json`, input prefer `edges.jsonl` с fallback на raw. **DoD:** slice всегда small и детерминирован, имя включает hash(query); обработка `edges.jsonl` streaming с early-stop по лимитам. **Tests:** unit + smoke (slice created, limits respected). Deps: W78-17.
- [x] W78-21 `tools/research_guard.py`, `tools/research_check.py`, `templates/aidd/config/gates.json`: gate для графа — если `*-call-graph-full.json` > N MB, требовать `*-call-graph.pack.*` и `*-call-graph.edges.jsonl`; понятные ошибки и подсказка команд. **DoD:** `research-check` BLOCK, если raw есть, а pack/view нет. **Tests:** `tests/test_research_check.py`, `tests/test_gate_researcher.py`. Deps: W78-17,W78-18.
- [x] W78-22 `hooks/context_gc/working_set_builder.py`, `templates/aidd/AGENTS.md`: working set ссылается на `call-graph.pack.*`, `edges.jsonl` и пример `graph-slice`; явный запрет читать raw graph. **DoD:** `latest_working_set.md` содержит ссылки/команды, без raw. **Tests:** `tests/test_context_gc.py` (snapshot includes graph refs). Deps: W78-16,W78-18.
- [x] W78-23 `tools/backfill_graph_views.py`, `README.md`, `README.en.md`: backfill для старых тикетов — найти `*-call-graph-full.json` и сгенерировать missing pack/view. **DoD:** script idempotent, пишет только отсутствующие файлы. **Tests:** none. Deps: W78-17,W78-18.

### EPIC F — P1: Tasklist alignment for review/qa
- [x] W78-24 `templates/aidd/docs/tasklist/template.md`, `agents/tasklist-refiner.md`, `tools/tasklist_check.py`: гарантировать секции `AIDD:QA_TRACEABILITY`, `AIDD:CHECKLIST_REVIEW`, `AIDD:CHECKLIST_QA` и их сохранение при `/tasks-new`; при необходимости добавить мягкую проверку presence в tasklist-check. **AC:** review/qa находят требуемые секции без ручного добавления. **Tests:** `tests/test_tasklist_check.py`. Deps: -

### EPIC G — P1: Prompt/template sync guard
- [x] W78-25 `tools/` + `tests/repo_tools/`: защитить sync между source-of-truth (`agents/`, `commands/`) и шаблонами/payload. **DoD:** есть скрипт sync/verify (или lint) и тест, который падает при рассинхроне ключевых файлов (`agents/`, `commands/`, `templates/aidd/docs/anchors/**`, `templates/aidd/AGENTS.md`); сравнение после нормализации (ignore `generated_at`/timestamp-поля, при необходимости — `prompt_version`/`source_version` по правилу). **AC:** PR блокируется при расхождении. **Tests:** `tests/repo_tools/*`. Deps: W78-10,W78-13,W78-19.

### EPIC H — P1: JSONL schemas (edges / ast-grep) + contract
- [x] W78-26 `templates/aidd/docs/anchors/research.md`, `tools/research.py`, `tools/call_graph_views.py` (или `tools/reports_pack.py`), `tools/ast_grep_scan.py`, `tools/reports_pack.py`: зафиксировать JSONL-схемы и версии для `*-call-graph.edges.jsonl` и `*-ast-grep.jsonl`, добавить `schema_version` + `stats/truncation` в pack. **DoD:** стабильные ключи, ссылка на schema, pack содержит stats. **AC:** slice/derive не “угадывают” формат. **Tests:** `tests/test_call_graph_edges_jsonl_schema.py`, `tests/test_ast_grep_jsonl_schema.py`. Deps: W78-7,W78-17.

### EPIC I — P1: Stage write-guard test coverage

### EPIC J — P1: Hybrid evidence gate (graph OR ast-grep)
- [x] W78-28 `tools/research_guard.py`, `tools/research_check.py`, `templates/aidd/config/gates.json`: для `required_for_langs` валидировать наличие evidence: `call-graph.pack.*` + `edges.jsonl` **или** `ast-grep.pack.*`; при отсутствии инструментов выводить actionable hints и BLOCK только если нет альтернативного evidence. **DoD:** `research-check` детерминированно PASS/WARN/BLOCK по матрице availability. **Tests:** `tests/test_research_check.py`. Deps: W78-9,W78-18.

### EPIC K — P0/P1: Call-graph v2 (edge index only, no backward compat)
- [x] W78-29 `tools/research.py`, `tools/reports_pack.py`, `tools/graph_slice.py`, `templates/aidd/docs/anchors/{research,plan,tasklist,implement,review,qa}.md`: убрать генерацию `*-call-graph-full.json`/columnar и поля `call_graph_full_*`; сделать edges.jsonl единственным источником истины (без fallback на raw). **AC:** research больше не пишет full/columnar, context/pack не содержит full paths, graph-slice падает если edges отсутствует. **Tests:** обновить `tests/test_researcher_call_graph.py`, `tests/test_reports_pack.py`, `tests/test_graph_slice.py`. Deps: -
- [x] W78-30 `tools/research.py`, `tools/call_graph_views.py`, `templates/aidd/config/conventions.json`: перейти на streaming запись edges.jsonl прямо из графа, добавить лимит `call_graph.edges_max` и флаги `call_graph_edges_truncated`/`call_graph_edges_stats` в context/pack; лимит применяется до материализации массива. **DoD:** JSONL‑строки содержат обязательные поля (`schema`, `caller`, `callee`, `caller_file`, `caller_line`, `callee_file`, `callee_line`, `lang`, `type`), stats включают `edges_scanned` и `edges_written`. **AC:** память стабильна на больших графах, truncation детерминирован, stats отражают реальные лимиты. **Tests:** `tests/test_researcher_call_graph.py`, `tests/test_call_graph_edges_jsonl_schema.py`. Deps: W78-29.
- [x] W78-31 `tools/reports_pack.py`: пересобрать call-graph pack v2 из edges.jsonl (entrypoints/hotspots/top-edges) в streaming режиме, без `call_graph` в контексте; если `edges_truncated=true` → pack явно фиксирует truncation; жёстко держать budget (top-N/trim snippets). **AC:** pack всегда ≤ лимитов и не зависит от raw/full graph. **Tests:** `tests/test_reports_pack.py`. Deps: W78-30.
- [x] W78-32 `tools/graph_slice.py`, `tools/graph-slice.sh`: сделать graph-slice v2 только по edges.jsonl (streaming + early-stop), добавить опциональные фильтры `--paths/--lang`. **AC:** slice всегда small, deterministic, без чтения full graph. **Tests:** `tests/test_graph_slice.py`. Deps: W78-29.
- [x] W78-33 `tools/research_guard.py`, `tools/research_check.py`, `hooks/context_gc/working_set_builder.py`, `templates/aidd/AGENTS.md`: обновить gate/working set под v2: требовать edges.jsonl + pack, удалить проверки full graph и упоминания backfill. **AC:** gate BLOCK если отсутствуют edges/pack, working set ссылается только на edges/pack. **Tests:** `tests/test_research_check.py`, `tests/test_context_gc.py`. Deps: W78-31,W78-32.

### EPIC L — P1: Scanner signal quality (ast-grep/call-graph)
- [x] W78-34 `tools/ast_grep_scan.py`, `tools/researcher_context.py`, `templates/aidd/config/conventions.json`: добавить ignore‑директории для сканеров (build/output/vendor), применить к ast‑grep и call‑graph file discovery; дефолт: `build`, `out`, `target`, `.gradle`, `.idea`, `.git`, `node_modules`, `.venv`, `dist`, `aidd`. **AC:** ast‑grep/call‑graph не трогают `build/**` (spotless/генерёнка). **Tests:** новые unit‑тесты на фильтрацию путей. Deps: W78-30.
- [x] W78-35 `tools/reports_pack.py`: авто‑trim для ast‑grep pack по budget (как для call‑graph), с логом `pack-trim`; гарантировать лимиты `rules` + `matches_per_rule` и при необходимости урезать snippets. **AC:** `*-ast-grep.pack.*` всегда ≤ budget; при overflow — trim вместо warn. **Tests:** `tests/test_reports_pack.py` (ast‑grep pack budget). Deps: W78-9.
- [x] W78-36 `tools/reports_pack.py`: поменять стратегию trim call‑graph pack — сначала урезать `hotspots/entrypoints`, затем `edges`; гарантировать минимум N edge‑примеров, если edges.jsonl не пустой. **AC:** call‑graph pack всегда содержит edge‑примеры при наличии данных, даже при жёстком бюджете. **Tests:** `tests/test_reports_pack.py` (edge‑presence). Deps: W78-31.
- [x] W78-37 `tools/researcher_context.py`, `templates/aidd/config/conventions.json`: поднять дефолт `call_graph.edges_max` для больших JVM repo (например 2000) или сделать эвристику по количеству файлов; документировать в conventions. **AC:** edge‑limit не застревает на 300 для больших реп, truncation остаётся предсказуемым. **Tests:** `tests/test_researcher_call_graph.py` (limit fallback). Deps: W78-30.
## Wave 79

_Статус: новый, приоритет 1. Цель — команды остаются inline, контекст передаётся через Context Pack, запуск саб‑агентов явный, аргументы унифицированы._

### EPIC A — Subagent naming + inline orchestrator pattern
- [x] W79-1 Нормализовать имена саб‑агентов по фактическим типам из `/agents` (использовать `feature-dev-aidd:<name>`), обновить упоминания в `commands/*.md` и `agents/*.md` (включая “Use the … subagent” и ссылки в тексте). Deps: -
- [x] W79-2 Обновить одноагентные команды‑оркестраторы (`commands/idea-new.md`, `commands/researcher.md`, `commands/tasks-new.md`, `commands/implement.md`, `commands/review.md`, `commands/qa.md`, `commands/spec-interview.md`) по паттерну: inline (без `context: fork`), сбор контекста → запись pack `aidd/reports/context/$1.<stage>.pack.md` (с `$ARGUMENTS`), затем явная инструкция “Use the feature-dev-aidd:<agent> subagent. First action: Read <pack>.” Для каждой команды явно зафиксировать, что делает команда ДО subagent (stage/CLI/side‑effects), что делает subagent (редактирование артефактов), и что делает команда ПОСЛЕ subagent (report/tasks-derive/progress). Для `spec-interview` — двухфазный паттерн: интервью+лог → pack для `spec-interview-writer` → запуск writer. DoD: в тексте команды есть явная фраза `Use the <agent> subagent` + `First action: Read <pack>`. Deps: W79-1,W79-10.
- [x] W79-3 Обновить multi‑agent orchestrators (`commands/plan-new.md`, `commands/review-spec.md`): inline + отдельные packs на каждого агента (например, `.planner.pack.md`/`.validator.pack.md`, `.review-plan.pack.md`/`.review-prd.pack.md`), явные инструкции “Use the … subagent; First action: Read <pack>”, и пояснение про запрет nested subagents. DoD: в тексте команды есть явная фраза `Use the <agent> subagent` + `First action: Read <pack>`. Deps: W79-1,W79-10.

### EPIC B — Agent pack consumption + edit permissions
- [x] W79-4 Добавить правило “если в сообщении указан путь `aidd/reports/context/*.pack.md`, прочитай его первым шагом и считай источником истины” во все используемые саб‑агенты (analyst, researcher, planner, validator, plan-reviewer, prd-reviewer, spec-interview-writer, tasklist-refiner, implementer, reviewer, qa). Deps: W79-2,W79-3,W79-10.
- [x] W79-5 Добавить `Edit` в `agents/analyst.md`, `agents/plan-reviewer.md`, `agents/prd-reviewer.md` (решить, оставлять ли `Write`). Deps: -
- [x] W79-10 Стандартизировать формат Context Pack: единый шаблон с полями `ticket`, `stage`, `agent`, `generated_at`, `paths` (plan/tasklist/prd/spec/research/test-policy), `iteration_focus`/`what_to_do_now`, `user_note=$ARGUMENTS`, опционально `git branch/diffstat`; команды пишут pack по шаблону, агенты используют эти поля как источник истины. Deps: -

### EPIC C — Argument placeholders + idea-new contract
- [x] W79-6 Заменить `<ticket>` на `$1`/`$ARGUMENTS` в `commands/*.md` там, где это влияет на резолвинг файлов и вызовы CLI (file refs, `--ticket`, примеры). Deps: -
- [x] W79-7 Уточнить контракт аргументов `/feature-dev-aidd:idea-new` (slug‑hint vs note): выбрать правило (например, `slug=<...>` или строгий `$2` для slug‑hint) и обновить инструкции/примеры. Deps: W79-6.

### EPIC D — Implement/test policy + allowlists
- [x] W79-8 Выровнять контракт владения `aidd/.cache/test-policy.env` между `commands/implement.md` и `agents/implementer.md` (единый владелец/условия записи). Deps: -
- [x] W79-9 Сузить `Bash(git:*)` в `commands/implement.md` и `agents/implementer.md` до безопасного набора подкоманд. Deps: -

### EPIC E — Command context hygiene
- [x] W79-11 Убрать/экранировать `@`‑инлайны больших артефактов в командах (plan/tasklist/prd/spec/research): вместо инлайна оставлять путь строкой и читать через `Read`, упаковывать в Context Pack. Deps: W79-2,W79-6.

### EPIC G — Prompt versioning + lint/tests
- [x] W79-13 Обновить `prompt_version/source_version` у всех затронутых команд/агентов и прогнать `tests/repo_tools/prompt-version` + `tests/repo_tools/lint-prompts.py` (обновить тесты при необходимости). Deps: W79-1,W79-2,W79-3,W79-4,W79-5,W79-6,W79-7,W79-8,W79-9,W79-10,W79-11.
## Wave 80

_Статус: новый, приоритет 1. Цель — hardening промптов и инвариантов tasklist (NEXT_3/статусы/QA/handoff/progress) по итогам аудита._

### EPIC A — NEXT_3 invariant + evidence
- [x] W80-1 `templates/aidd/docs/anchors/tasklist.md`, `templates/aidd/docs/tasklist/template.md`, `agents/tasklist-refiner.md`, `agents/implementer.md`, `commands/tasks-new.md`, `commands/implement.md`: закрепить инвариант `AIDD:NEXT_3`:
  - NEXT_3 формируется из open work items: сначала open‑итерации из `AIDD:ITERATIONS_FULL`, затем open handoff‑задачи из `AIDD:HANDOFF_INBOX` (приоритет: Blocking=true → Priority=critical → Priority=high → остальные);
  - `AIDD:ITERATIONS_FULL` должен иметь машинно‑считываемый state итерации: чекбокс `- [ ]`/`- [x]` или поле `State: open|done|blocked` (предпочтительно чекбокс);
  - canonical format итерации (в template): `- [ ] I7: <title> (iteration_id: I7)` + строго именованные подполя `DoD/Boundaries/Tests`;
  - canonical format handoff (для ссылок из NEXT_3): `- [ ] <title> (id: review:F6) (Priority: high) (Blocking: true)`;
  - `[x]` в NEXT_3 запрещены;
  - кардинальность: если open_total>=3 → ровно 3; если open_total<3 → open_total; если open_total==0 → один маркер `- (none)`;
  - запрет истории/подробностей в NEXT_3 (детали только в `AIDD:ITERATIONS_FULL`);
  - NEXT_3 = thin pointer list: 1–2 строки на пункт + `ref: iteration_id=I7` / `ref: id=review:F6` (без markdown‑якорей; чекер валидирует наличие id);
  - каждый пункт NEXT_3 содержит `iteration_id` или `id`, а DoD/Boundaries/Tests находятся в `AIDD:ITERATIONS_FULL`/`AIDD:HANDOFF_INBOX`;
  - evidence для `[x]` в tasklist: `AIDD:PROGRESS_LOG` или `aidd/reports/progress/<ticket>.log` или inline `(link: aidd/reports/...|commit|PR)`;
  - после отметки `[x]` в `AIDD:ITERATIONS_FULL`/`AIDD:HANDOFF_INBOX` implementer обязан refresh NEXT_3 (ручной или через normalize `--fix`).
  Обновить `prompt_version/source_version`, прогнать `tests/repo_tools/prompt-version` + `tests/repo_tools/lint-prompts.py`. Deps: -
- [x] W80-2 `tools/tasklist_check.py`, `tests/test_tasklist_check.py`: валидировать:
  - NEXT_3 кардинальность по правилу выше + отсутствие `[x]` + уникальные id;
  - обязательные поля в NEXT_3 items: `iteration_id|id` + `ref:` на блок (`AIDD:ITERATIONS_FULL`/`AIDD:HANDOFF_INBOX`), а DoD/Boundaries/Tests должны быть в целевом блоке;
  - определение open items: итерация open = чекбокс `[ ]` или `State=open`; handoff open = чекбокс `[ ]` и/или `Status=open`; если state вычислить нельзя → WARN/BLOCKED + подсказка normalize;
  - NEXT_3 ⊆ open items (ITERATIONS_FULL + HANDOFF_INBOX), иначе BLOCKED + подсказка normalize;
  - сортировка NEXT_3: глобально по Blocking=true → Priority (critical>high>medium>low) → kind (handoff vs iteration) → tie‑breaker (plan order для итераций, id для handoff); несортировано → WARN/BLOCKED;
  - enum‑валидация: `Priority/Status/Blocking/source` в handoff и `State` в итерациях соответствуют каноническим enum‑ам (stage=implement → WARN, stage=review/qa → BLOCKED);
  - legacy/неизвестные форматы (marker/field) допускаются с WARN на implement, но BLOCK на review/qa до normalize;
  - классификация severity:
    - BLOCK всегда: duplicate `## AIDD:*`, status mismatch, NEXT_3 содержит `[x]`, NEXT_3 не ⊆ open items, READY при NOT MET, keyword‑lint “PASS/0 findings” при NOT MET;
    - WARN на implement / BLOCK на review+qa: legacy форматы, enum mismatch, несортированность NEXT_3, превышение мягких бюджетов.
  - синхрон `Status` (front‑matter ↔ `AIDD:CONTEXT_PACK Status`), источник истины — front‑matter;
  - запрет `READY`, если `AIDD:QA_TRACEABILITY` содержит `NOT MET` по любому AC (без override);
  - тестовый статус: если reviewer‑tests=required или stage=qa → любые test failures/compilation errors => BLOCKED; если optional → WARN (marker: `aidd/reports/reviewer/<ticket>.json`, field `tests`);
  - evidence для `[x]` ищется в `AIDD:PROGRESS_LOG`, progress archive и inline link.
  - каждая top-level секция `## AIDD:*` встречается ровно один раз (дубли → BLOCKED + подсказка normalize);
  - stage=qa берётся из `aidd/docs/.active_stage`, fallback — `AIDD:CONTEXT_PACK Stage`;
  - если `QA_TRACEABILITY` содержит `NOT MET`, то `AIDD:CHECKLIST_QA` (если есть) или QA‑подсекция в `AIDD:CHECKLIST` не может иметь `[x] acceptance verified`, а строки вида `PASS/0 findings/ready for deploy` запрещены (keyword lint).
  Добавить фикстуры: next3_open>3, next3_open<3, next3_has_x, status_mismatch, done_without_evidence, qa_not_met_but_ready, duplicate_sections. Deps: W80-1.

### EPIC B — Handoff format + idempotency
- [x] W80-3 `tools/tasks_derive.py`, `templates/aidd/docs/tasklist/template.md`, `tests/test_tasks_derive.py`: перейти на единый структурированный формат задач в `AIDD:HANDOFF_INBOX`:
  - обязательные поля: `id`, `source`, `title`, `scope`, `DoD`, `Boundaries`, `Tests`, `Priority`, `Blocking`, `Status`;
  - enums: `Priority=critical|high|medium|low`, `Status=open|done|blocked`, `Blocking=true|false`, `source=research|review|qa|manual`;
  - canonical source name: `review` (алиасы `reviewer` → `review`), normalize переписывает маркеры/значения в канон;
  - `id` — канон; `handoff_id` допускается только как legacy alias при normalize (переписывать в `id`);
  - стабильный `id` обязателен, повторные derive обновляют по id без дублей; `id` короткий, без двойных префиксов (`review:review:` и т.п.);
  - legacy-строки вида `Research: ...`, `QA report: ...`, `QA: ...`, `Review: ...`, `Review report: ...` мигрируются/удаляются (оставляем только structured);
  - `tasks_derive` пишет derived задачи только внутри `<!-- handoff:<source> start --> ... <!-- end -->`;
  - legacy‑чистка только внутри `## AIDD:HANDOFF_INBOX`, удаляются только строки, матчящие whitelist (например `^- \\[.\\] (Research|QA|Review)( report)?:`) или без обязательных structured‑полей;
  - ручные задачи живут в `<!-- handoff:manual start --> ... <!-- handoff:manual end -->` (derive/normalize не трогают).
  - если у задачи есть и checkbox, и `Status` — enforce sync: `[x]` ↔ `Status=done`, `[ ]` ↔ `Status=open` (mismatch → WARN/BLOCKED в tasklist_check).
  - completion/status поля сохраняются при повторных derive.
  Deps: -

### EPIC C — Progress log budget
- [x] W80-4 `tools/progress.py`, `templates/aidd/docs/tasklist/template.md`, `templates/aidd/docs/anchors/tasklist.md`, `agents/implementer.md`: добавить:
  - дедуп PROGRESS_LOG по `(date, source, iteration_id|handoff_id, short_hash)`;
  - лимит N=20 строк + лимит длины строки (<=240 chars);
  - overflow архивировать в `aidd/reports/progress/<ticket>.log`;
  - запрет narrative-логов (валидируемый формат строки + regex в template), напр.: `- YYYY-MM-DD source=implement id=I4 kind=iteration hash=abc123 link=aidd/reports/tests/... msg=...` (msg короткий, без переносов/кавычек; для stage=review/qa link обязателен; допускается `kind=handoff`, check/normalize опираются на формат).
  - enums: `source=implement|review|qa|research|normalize`, `kind=iteration|handoff`; если формат/enum не совпадает → WARN (BLOCK для stage=review/qa).
  Добавить `tests/test_progress.py`. Deps: -

### EPIC D — QA status semantics
- [x] W80-5 `agents/qa.md`, `commands/qa.md`, `templates/aidd/docs/anchors/qa.md`, `templates/aidd/docs/tasklist/template.md`: статус QA вычисляется из:
  - `AIDD:QA_TRACEABILITY` (NOT MET → BLOCKED; NOT VERIFIED → WARN);
  - + тестового статуса (если reviewer‑tests=required → failures => BLOCKED; если optional → WARN).
  - source‑of‑truth для QA‑статуса: front‑matter `Status` (зеркало в `AIDD:CONTEXT_PACK Status`).
  - если `AIDD:CHECKLIST_QA` отсутствует, QA отмечает чеклист в QA‑подсекции `AIDD:CHECKLIST`.
  Запрет “PASS/0 findings” при blocker/critical или NOT MET; `AIDD:CHECKLIST_QA` не может утверждать acceptance при `NOT MET`; traceability должна ссылаться на evidence (`aidd/reports/qa/<ticket>.json`, tests report). Обновить `prompt_version/source_version`, прогнать prompt-lint. Deps: W80-2.

### EPIC E — Review guardrails
- [x] W80-6 `agents/reviewer.md`, `commands/review.md`, `templates/aidd/docs/anchors/review.md`: guardrails:
  - reviewer не пишет “летопись” в tasklist: summary ≤30 строк, подробности только в `aidd/reports/reviewer/<ticket>.json`;
  - reviewer обязан проверить исполнимость tasklist (NEXT_3 правило, статус‑синхрон, наличие TEST_EXECUTION);
  - на каждый finding → handoff‑задача (scope/blocking/DoD/Boundaries/Tests);
  - reviewer НЕ переписывает `AIDD:ITERATIONS_FULL`, `AIDD:SPEC_PACK`, `AIDD:TEST_EXECUTION`;
  - reviewer/qa MUST NOT создавать новые копии `## AIDD:*` секций (только обновление существующих).
  - write surface: разрешено редактировать front‑matter `Status/Updated` (и `Stage`, если есть), `AIDD:CHECKLIST_REVIEW`/`AIDD:CHECKLIST_QA`, `AIDD:HANDOFF_INBOX` (через derive), `AIDD:QA_TRACEABILITY` (qa only), `AIDD:CONTEXT_PACK` (только Status/Stage/Blockers summary); запрещено трогать `AIDD:NEXT_3` (кроме запроса normalize/implementer).
  Обновить `prompt_version/source_version`, прогнать prompt-lint. Deps: W80-1,W80-2.

### EPIC F — Plan vs tasklist drift
- [x] W80-7 `templates/aidd/docs/tasklist/template.md`, `agents/tasklist-refiner.md`, `tools/tasklist_check.py`, `tests/test_tasklist_check.py`: plan/tasklist drift:
  - добавить `parent_iteration_id` (строго: ID из plan, не свободный текст);
  - soft‑WARN если tasklist содержит `iteration_id` вне плана без parent;
  - refiner обязан ставить parent или создавать handoff “update plan”.
  - парсить IDs из плана: брать `Plan:` из front‑matter и читать `## AIDD:ITERATIONS` → `iteration_id:`; если plan отсутствует → WARN + handoff “update plan”.
  Deps: W80-2.

### EPIC G — Prompt hygiene (tools mismatch)
- [x] W80-8 `commands/researcher.md`: привести allowed-tools в соответствие с инструкциями (tasks-derive/progress) или убрать упоминание недоступных инструментов; обновить `prompt_version/source_version`, прогнать prompt-lint. Deps: -

### EPIC H — Tasklist normalize autofix
- [x] W80-9 `tools/tasklist_check.py` (или `tools/tasklist_normalize.py`), `tests/test_tasklist_normalize.py`: добавить `--fix` (или отдельную команду), которая:
  - пересобирает NEXT_3 по правилу W80-1 (open iterations + open handoff, сортировка по blocking/priority);
  - удаляет `[x]` из NEXT_3;
  - удаляет legacy‑дубли в HANDOFF_INBOX;
  - дедупит PROGRESS_LOG и архивирует overflow.
  - сливает/удаляет дубли `## AIDD:*` секций:
    - `AIDD:HANDOFF_INBOX` → merge по `id`;
    - `AIDD:PROGRESS_LOG` → merge+dedup+budget;
    - `AIDD:QA_TRACEABILITY` → merge по AC-id, статус по худшему (`NOT MET` > `NOT VERIFIED` > `met`), evidence объединять списком;
    - остальные секции → оставить первую, остальные в backup + подсказка ручной сверки.
  - normalize переписывает alias‑маркеры handoff (`reviewer` → `review`) и legacy `handoff_id` → `id`;
  - при merge handoff: сохранять пользовательский checkbox/Status, обновлять title/DoD/Boundaries/Tests из derive (если отличаются).
  - backup перед записью: `aidd/reports/tasklist_backups/<ticket>/<timestamp>.md`;
  - `--dry-run` (печатает diff/кол-во правок);
  - после `--fix` запуск self-check (tasklist_check), fail fast при ошибке.
  - после `--fix` печатать summary: сколько секций слито, сколько задач дедупнуто, сколько строк перенесено в архив.
  Deps: W80-2,W80-3,W80-4.

### EPIC I — Budgets for heavy sections
- [x] W80-10 `templates/aidd/docs/anchors/tasklist.md`, `agents/{implementer,tasklist-refiner,reviewer,qa}.md`, `tools/tasklist_check.py`: зафиксировать budget‑инварианты:
  - CONTEXT_PACK TL;DR ≤12 bullets;
  - Blockers summary ≤8 строк;
  - `AIDD:NEXT_3` item ≤12 строк (иначе WARN → перенос деталей в `AIDD:ITERATIONS_FULL`/`AIDD:HANDOFF_INBOX`);
  - запрет stacktrace/logs в tasklist (только ссылки на reports);
  - HANDOFF_INBOX без “простыней” (детали → reports), item >20 lines → WARN.
  tasklist_check: WARN если TL;DR >12 bullets или blockers >8 строк или tasklist >800 lines; BLOCK если >2000 lines или >200k chars, а также при stacktrace-like паттернах без ссылки на report (>=5 подряд строк `^\s+at\s+`, >=2 `^Caused by:`, или fenced code block > 20 строк). Deps: W80-2.

### EPIC J — Global prompt/tool lint
- [x] W80-11 `tests/repo_tools/lint-prompts.py` (или новый тест): добавить проверку: если промпт упоминает tool (`claude-workflow X` / `${CLAUDE_PLUGIN_ROOT}/tools/*.sh`) → в allowed-tools должен быть соответствующий `Bash(...)`; добавить ignore list для примеров (code fences/Примеры CLI) и markdown‑ссылок с `tools/`; для `agents/{implementer,tasklist-refiner,reviewer,qa}.md` и `commands/{tasks-new,implement,review,qa}.md` требовать `Write` + `Edit` (и видеть `Read`). Deps: -

### EPIC K — Tasklist check as gate
- [x] W80-12 `hooks/gate-workflow.sh` (или stage‑hooks), `tools/tasklist_check.py`, `tests/test_gate_workflow.py`: на Stop/SubagentStop запускать `tasklist_check` для активного тикета; при stage=review/qa и BLOCKED → падать, при stage=implement → WARN не блокирует. Тесты: fixture с status mismatch/duplicate sections/NOT MET + “PASS/0 findings” должны блокировать на review/qa. Deps: W80-2.
  - если `.active_ticket` отсутствует или tasklist не найден → WARN и exit 0 (не блокировать).

### EPIC L — Tasklist check/normalize wrappers (optional)
- [x] W80-13 `tools/tasklist-check.sh`, `tools/tasklist-normalize.sh`, `commands/implement.md`, `commands/review.md`, `commands/qa.md`: thin‑wrapper для удобного запуска check/normalize из промптов; обновить allowed-tools/примеры. Deps: W80-2,W80-9.

## Wave 81

_Статус: новый, приоритет 1. Цель — переход на RLM evidence (recursive summaries + verified links) вместо call-graph/ast-grep, сохранение pack-first, детерминизм артефактов и поддержка Claude Code plugin._

### EPIC A — RLM contract: артефакты, схемы, бюджеты (P0)
- [x] W81-1 `templates/aidd/docs/anchors/rlm.md`, `AGENTS.md`, `README.md`, `README.en.md`: ввести anchor **RLM** и формализовать:
  - что такое RLM evidence в AIDD;
  - какие артефакты MUST READ FIRST / MUST UPDATE;
  - “RLM Read Policy”: агенты читают только `*.pack.*` и `rlm-slice`, не читают raw index целиком.
  **AC:** есть единый текст политики и он подключён во все релевантные anchors (research/plan/implement/review/qa).
  **Deps:** -
- [x] W81-2 `tools/schemas/rlm_node.schema.json`, `tools/schemas/rlm_link.schema.json`, `tests/test_rlm_schema.py`: зафиксировать версии и JSONL‑схемы:
  - `aidd/reports/research/<ticket>-rlm.nodes.jsonl` (node records),
  - `aidd/reports/research/<ticket>-rlm.links.jsonl` (link records),
  - минимальный набор обязательных полей + `schema_version`:
    - file node: `node_kind="file"`, `file_id`, `id` (== `file_id`), `path`, `rev_sha`, `lang`, `prompt_version`, `summary`, `public_symbols[]`, `key_calls[]`, `framework_roles[]`, `test_hooks[]`, `risks[]`, `verification`, `missing_tokens[]`;
    - dir node: `node_kind="dir"`, `dir_id` (или `file_id` от normalized dir path), `id` (== `dir_id`), `children_file_ids[]` (truncated) + `children_count_total`, `summary`;
    - link record: `link_id`, `src_file_id`, `dst_file_id`, `type`, `evidence_ref` (структура: `path`, `line_start`, `line_end`, `extractor`, `match_hash`), `unverified`.
  **AC:** schema-валидация проходит на фикстурах; любые изменения полей требуют bump версии.
  **Deps:** -
- [x] W81-3 `templates/aidd/config/conventions.json`, `templates/aidd/config/gates.json`: добавить секцию `rlm`:
  - `enabled`, `required_for_langs`, `max_files`, `max_nodes`, `max_links`, `max_file_bytes`,
  - бюджеты для pack/slice,
  - ignore dirs (общие),
  - политика “verification required” для линков.
  **AC:** конфиг валиден; значения по умолчанию безопасные (не взрывают токены).
  **Deps:** W81-1,W81-2

### EPIC B — Deterministic targeting: какие файлы RLM имеет право трогать (P0)
- [x] W81-4 `tools/rlm_targets.py`, `tools/researcher_context.py`, `tools/research.py`: добавить генерацию **RLM targets** на основе:
  - `targets.paths`/`paths_discovered`,
  - (опционально) “files touched” из plan/review report,
  - keyword hits (через `rg`) только внутри targets,
  - нормализованных keywords (`keywords`), но не `keywords_raw`.
  Выход: `aidd/reports/research/<ticket>-rlm-targets.json` с детерминированным упорядочиванием.
  **AC:** одинаковый вход → одинаковый targets.json; никакие build/out/vendor/aidd/** не попадают.
  **Tests:** unit на сортировку/фильтры/ignore.
  **Deps:** W81-3
- [x] W81-5 `tools/rlm_manifest.py`: добавить manifest с hashing:
  - вводит стабильный `file_id = sha1(normalized_path)` и ревизию `rev_sha = sha1(file_bytes)`;
  - хранит `file_id`, `rev_sha`, `path`, `lang`, `size`, `prompt_version`;
  - поддерживает incremental: не пересчитывать nodes, если `rev_sha` не изменился.
  Выход: `aidd/reports/research/<ticket>-rlm-manifest.json`.
  **AC:** file node id = `file_id`, dir node id = `dir_id`; пере-запуск без изменений не меняет `file_id/dir_id`, при изменении файла меняется только `rev_sha`, derive остаётся идемпотентным.
  **Tests:** unit на incremental + стабильность id.
  **Deps:** W81-4

### EPIC C — RLM extraction: “nodes” и верификация (P0)
- [x] W81-6 `templates/aidd/rlm/prompts/file_node.md`, `templates/aidd/rlm/prompts/dir_node.md`, `agents/researcher.md`: добавить канонические prompt‑шаблоны для RLM:
  - **file node**: `summary`, `public_symbols`, `key_calls`, `framework_roles` (web/controller/service/repo), `test_hooks`, `risks`;
  - **dir node**: “что это за модуль/пакет”, “главные entrypoints”, “где тесты”.
  Строго JSON output, канонический EN prompt (RU пояснения — в docs); dir_node prompt — docs-only reference, генерация dir nodes описана в W81-21 (без LLM).
  **AC:** промпт стабилен, короткий, требует JSON без “воды” и соответствует schema (W81-2) как source-of-truth; обновлён `prompt_version/source_version`.
  **Deps:** W81-2
- [x] W81-7 `tools/rlm_verify.py`: валидация node output:
  - проверять, что `public_symbols` реально встречаются в файле (string match, допускаем qualified/short),
  - проверять, что `key_calls` ссылаются на реально встречающиеся идентификаторы,
  - проставлять `verification = passed|partial|failed`, `missing_tokens=[...]`.
  **AC:** любые “выдуманные” символы маркируются как `partial/failed` и не попадают в top evidence pack.
  **Tests:** unit на фикстурах с fake symbols.
  **Deps:** W81-6
- [x] W81-8 `tools/rlm_nodes_build.py`: сборка `*-rlm.nodes.jsonl` по manifest:
  - режим `--mode=agent-worklist`: не вызывает LLM, а генерит “worklist pack” (список файлов + что из них извлечь) для агента;
  **AC:** agent-worklist режим работает без API и пишет `*-rlm.worklist.pack.*` + мета `rlm_status=pending`/`rlm_worklist_path`; worklist инкрементален (читает существующий `*-rlm.nodes.jsonl` и включает только missing/outdated `(file_id, rev_sha, prompt_version)`), в записи есть `file_id`, `path`, `rev_sha`, `lang`, `prompt_version`, `size`, `reason=missing|outdated|failed`.
  **Tests:** unit на генерацию worklist + jsonl output writer.
  **Deps:** W81-5,W81-7

### EPIC D — RLM links: построение “графа” без AST (P0)
- [x] W81-9 `tools/rlm_links_build.py`: построить `*-rlm.links.jsonl` из nodes:
  - линк типы: `imports`, `calls`, `extends/implements`, `config/bean`, `endpoint->handler` (если удаётся);
  - linking происходит по verified symbols (из W81-7) + fallback на `rg` “definition search” в targets.
  **AC:** links строятся детерминированно; каждый линк имеет `link_id = sha1(src_file_id + dst_file_id + type + evidence_ref.match_hash)` и `evidence_ref` с `path`, `line_start`, `line_end`, `extractor=rg|regex|manual`, `match_hash = sha1(path + ":" + line_start + ":" + line_end + ":" + matched_text_normalized)`; `matched_text_normalized` = trim + collapse spaces + normalize `\n`; дедуп по `link_id`, сортировка по `(src_path, type, dst_path, match_hash)`; fail-fast только если `nodes.jsonl` отсутствует/пустой (подсказка выполнить W81-27).
  **Tests:** unit на linking + schema.
  **Deps:** W81-2,W81-4,W81-7,W81-8
- [x] W81-10 `tools/rlm_slice.py`, `tools/rlm-slice.sh`: on-demand slice:
  - вход: `--ticket`, `--query`, `--max_nodes`, `--max_links`, `--paths`, `--lang`;
  - выход: `aidd/reports/context/<ticket>-rlm-slice-<sha1>.pack.json` + `.latest`.
  **AC:** slice всегда small, deterministic, не требует чтения всего nodes в память (streaming JSONL).
  **Tests:** unit + smoke.
  **Deps:** W81-9

### EPIC E — Packs: pack-first как замена graph/ast-grep packs (P0)
- [x] W81-11 `tools/reports_pack.py`: добавить RLM pack builder:
  - `aidd/reports/research/<ticket>-rlm.pack.json|toon` включает:
    - entrypoints (top),
    - hotspots (по кол-ву verified links + keyword hits),
    - integration points,
    - test hooks,
    - “recommended reads” (5–15 файлов).
  - бюджеты: строгие лимиты на строки/символы.
  **AC:** pack <= budgets; если не помещается — trim с `pack_trim` stats; evidence snippets извлекаются по `evidence_ref` только для top‑N links (или `evidence_snippet` хранится в links с лимитом длины) с нормализацией строк и max chars.
  **Tests:** budget tests.
  **Deps:** W81-8,W81-9
- [x] W81-12 `tools/tasks_derive.py`: derivation из RLM pack:
  - stable ids: `rlm:<kind>:<file_id>:<reason_hash>`, где `reason_hash = sha1(normalized_reason + rule_kind + scope)`;
  - handoff задачи: “проверь интеграцию”, “проверь тест-хук”, “риск: X”.
  **AC:** derive идемпотентен, не дублирует; пишет structured handoff в формате Wave 80 (`id/source/title/scope/DoD/Boundaries/Tests/Priority/Blocking/Status`), `source=research`, `Status=open`, `Priority/Blocking` вычисляются детерминированно.
  **Tests:** `tests/test_tasks_derive.py`.
  **Deps:** W81-11

### EPIC F — Полная замена tree-sitter/ast-grep в research stage (P0/P1)
- [x] W81-13 `tools/research.py`, `tools/research.sh`, `commands/researcher.md`: заменить pipeline evidence:
  - новый флаг `--evidence-engine rlm|auto`;
  - `auto`: всегда RLM (без legacy fallback), поведение по конфигу;
  - записывать в context/pack ссылки: `rlm_nodes_path`, `rlm_links_path`, `rlm_pack_path`.
  **AC:** research всегда генерит targets+manifest и worklist pack, выставляет `rlm_status=pending` в `aidd/reports/research/<ticket>-context.json` и в context pack; source-of-truth = context.json, после W81-27 статус обновляется на `ready`; pack строится только если nodes+links уже есть.
  **Deps:** W81-4,W81-8,W81-11
- [x] W81-14 `tools/research_guard.py`, `tools/research_check.py`, `templates/aidd/config/gates.json`: обновить gates:
  - для `required_for_langs` теперь требовать RLM pack + (nodes+links присутствуют);
  - stage=research: допускает `rlm_status=pending` → WARN, но `worklist+targets+manifest` MUST exist;
  - stage-aware: stage=implement допускает `rlm_status=pending` → WARN; stage=plan/review/qa требует `rlm_status=ready` + nodes+links → BLOCK;
  - выдавать actionable hints: как запустить `rlm_nodes_build`/`rlm_slice`.
  **AC:** gate не упоминает tree-sitter/ast-grep; матрица PASS/WARN/BLOCK прозрачна; source-of-truth для `rlm_status` = `aidd/reports/research/<ticket>-context.json`.
  **Tests:** `tests/test_research_check.py`.
  **Deps:** W81-13
- [x] W81-15 `templates/aidd/docs/anchors/research.md`, `agents/researcher.md`, `agents/{planner,tasklist-refiner,implementer,reviewer,qa}.md`, `commands/{plan-new,tasks-new,implement,review,qa}.md`: переписать anchor/поведение агентов:
  - MUST READ FIRST: `*-rlm.pack.*` и при необходимости `rlm-slice`;
  - MUST NOT: читать `*-rlm.nodes.jsonl` целиком.
  **AC:** промпты агентов/команд не содержат упоминаний tree-sitter/ast-grep; есть fail-fast если RLM pack отсутствует; обновлён `prompt_version/source_version`; allowed-tools содержит `Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh:*)` там, где упоминается slice.
  **Deps:** W81-11,W81-13

### EPIC G — Полная деактивация и удаление legacy сканеров (P1)
- [x] W81-16 `templates/aidd/config/conventions.json`, `README*`, `AGENTS.md`: пометить `ast_grep` и `call_graph` как deprecated → disabled by default.
  **AC:** документация больше не предлагает запуск ast-grep/call-graph как рекомендованный путь.
  **Deps:** W81-13
- [ ] W81-17 удалить/выпилить code-paths:
  - `tools/ast_grep_scan.py` + rules pack (если решаете “полный отказ”),
  - `call_graph_*` в research.py (edges логика уходит в RLM).
  **AC:** сборка/тесты репо проходят; никакие команды не ссылаются на удалённые файлы.
  **Tests:** полный прогон CI.
  **Deps:** W81-14,W81-15,W81-16

### EPIC I — RLM recursion: dir/module nodes (P0)
- [x] W81-21 `tools/rlm_nodes_build.py`, `tools/schemas/rlm_node.schema.json`, `tests/test_rlm_nodes_build.py`: добавить второй проход “dir nodes”:
  - `node_kind=file|dir`;
  - dir node строится из child nodes (без чтения исходников);
  - детерминированный порядок child, бюджеты на размер dir summary;
  - алгоритм: сортировать children по path, выбирать top-K по лимиту, summary = агрегация child summaries + топ symbols + entrypoints; поля соответствуют schema.
  **AC:** есть и file nodes, и dir nodes; dir nodes строятся из JSON child nodes без LLM по детерминированному алгоритму.
  **Deps:** W81-2,W81-8

### EPIC J — Working set + index sync migration (P0)
- [x] W81-22 `hooks/context_gc/working_set_builder.py`, `tools/index_sync.py`, `templates/aidd/AGENTS.md`: миграция working set:
  - working set ссылается на `*-rlm.pack.*` и `rlm-slice`;
  - убрать ссылки на graph/ast-grep packs из working set;
  - добавить “как запросить slice”.
  **AC:** `latest_working_set.md` всегда pack-first по RLM.
  **Deps:** W81-10,W81-11

### EPIC N — E2E smoke test pipeline (P1)
- [x] W81-26 `tests/test_research_rlm_e2e.py`: e2e тест пайплайна:
  - минимальный repo‑fixture (пара файлов) →
  - прогон: targets → manifest → (fixture nodes.jsonl) → links → pack → slice → derive.
  **AC:** один тест проверяет связность всего пайплайна.
  **Deps:** W81-4,W81-5,W81-8,W81-9,W81-10,W81-11,W81-12

### EPIC O — Claude Code agent flow (P0)
- [x] W81-27 `agents/researcher.md`, `commands/researcher.md` (опц. `agents/rlm-node-writer.md`): формализовать “agent-worklist → nodes/links → pack”:
  - агент читает `*-rlm.worklist.pack.*`, генерит `*-rlm.nodes.jsonl` (строго schema), запускает `tools/rlm_verify.py`;
  - затем запускает `tools/rlm_links_build.py` и `tools/reports_pack.py`.
  **AC:** после генерации nodes/links/pack агент обновляет `rlm_status=ready` и `rlm_*_path` в `aidd/reports/research/<ticket>-context.json` и context pack; записи пишутся атомарно (tmp → rename) и с последующим `rlm_jsonl_compact`.
  **Deps:** W81-8,W81-9,W81-11,W81-28

### EPIC P — JSONL compaction/rewrite (P0)
- [x] W81-28 `tools/rlm_jsonl_compact.py` (или расширить rlm_nodes_build/rlm_links_build): детерминированный rewrite:
  - nodes.jsonl/links.jsonl без дублей, сортировка, удаление устаревших ревизий;
  - byte-identical output при повторном прогоне без изменений.
  **AC:** повторный прогон без изменений даёт byte-identical JSONL.
  **Deps:** W81-5,W81-8,W81-9

### EPIC Q — rg-budget & batching policy (P1)
- [x] W81-29 `tools/rlm_links_build.py`, `templates/aidd/config/conventions.json`, tests: performance hardening:
  - `rlm.rg_timeout_s`, `rlm.max_symbols_per_file`, `rlm.max_definition_hits_per_symbol`, batching запросов;
  - ограничение link‑поиска при превышении budget → WARN в pack.
  **AC:** links_build не умирает по времени на больших репо.
  **Deps:** W81-3,W81-9

### EPIC R — RLM field hardening (P0/P1)
- [x] W81-30 `tools/rlm-slice.sh`, `tools/rlm-verify.sh`, `tools/rlm-links-build.sh`, `tools/rlm-jsonl-compact.sh`, `agents/researcher.md`, `commands/researcher.md`: привести entrypoints к рабочему виду в workspace:
  - `rlm-slice.sh` исполняемый и запускается как Bash tool;
  - добавить bootstrap‑wrappers для verify/links/compact (CLAUDE_PLUGIN_ROOT + sys.path);
  - обновить allowed-tools, чтобы agent-flow мог вызывать wrappers.
  **AC:** команды работают из workspace без `PYTHONPATH`; `Bash(${CLAUDE_PLUGIN_ROOT}/tools/rlm-*.sh:*)` запускается без permission errors.
  **Tests:** smoke `--help`/entrypoint для каждого wrapper.
  **Deps:** W81-27
- [x] W81-31 `tools/reports_pack.py`, `tools/research_check.py`, `tools/rlm_nodes_build.py`, tests: синхронизировать `rlm_status` с worklist:
  - `rlm_status=ready` только если worklist пуст/ready и nodes+links есть;
  - если worklist pending/непустой — сохранять `rlm_status=pending` или вводить `partial` (с gate-правилами);
  - `research_check` использует worklist как source-of-truth для статуса и выдаёт явные WARN/BLOCK.
  **AC:** pack не переводит статус в ready при непустом worklist; gates согласованы со статусом.
  **Tests:** `tests/test_reports_pack.py`, `tests/test_research_check.py`.
  **Deps:** W81-8,W81-14
- [x] W81-32 `tools/rlm_links_build.py`, `tools/rlm_manifest.py`, `tools/rlm_targets.py`, tests: расширить набор `target_files` для rg‑поиска:
  - если `rlm-targets.files` пуст или слишком узок — fallback на manifest files (bounded max_files);
  - фиксировать в stats источник списка (targets|manifest) и предупреждать при пустом списке.
  **AC:** `rg` работает даже при keyword‑таргетах, links не “пустеют” из‑за отсутствия target_files.
  **Tests:** unit на fallback источника и stats.
  **Deps:** W81-5,W81-9
- [x] W81-33 `tools/rlm_targets.py`, `templates/aidd/config/conventions.json`, tests: улучшить auto‑discovery путей для монореп:
  - обнаруживать `**/src/main`, `**/src/test`, `frontend/src`, `backend/src/main` (если есть);
  - фильтровать несуществующие paths, чтобы не плодить WARN.
  **AC:** rlm-targets не содержит несуществующих путей; монорепа получает релевантные `paths` без ручного `--paths`.
  **Tests:** unit на discovery + фильтрацию.
  **Deps:** W81-4

### EPIC S — RLM field test fixes (P0/P1)
- [x] W81-34 `tools/researcher_context.py`, `tools/research.py`, `templates/aidd/config/conventions.json`, tests: снизить шум “missing research paths” для монореп:
  - считать отсутствующие дефолтные пути warning только если нет валидных `paths_discovered`;
  - при наличии auto‑discovery — исключать несуществующие пути из `scope.paths`/`targets.paths`.
  **AC:** для монореп предупреждения о `src/main`/`src/test` не появляются, если есть найденные пути; `targets.json` не содержит несуществующих путей.
  **Tests:** unit на фильтрацию invalid paths + отсутствие WARN при discovery.
  **Deps:** W81-3,W81-4
- [x] W81-35 `tools/reports_pack.py`, `tests/test_reports_pack.py`: синхронизировать лог/статус RLM pack с worklist:
  - логировать фактический `rlm_status` после апдейта, без “ready” при pending;
  - `pack.status` отражает pending/ready и добавляет warn при `worklist_entries > 0`.
  **AC:** сообщение и pack‑статус совпадают с `aidd/reports/research/<ticket>-context.json`; при pending есть явный warn в pack.
  **Tests:** обновить `tests/test_reports_pack.py` на pending case.
  **Deps:** W81-31
- [x] W81-36 `tools/rlm_links_build.py`, `templates/aidd/config/conventions.json`, tests: улучшить link‑coverage при пустых `key_calls`:
  - добавить конфиг `rlm.link_key_calls_source = key_calls|public_symbols|both` (или boolean fallback);
  - при пустых `key_calls` использовать ограниченный набор `public_symbols` (детерминированно) и логировать stats.
  **AC:** links строятся даже при пустых `key_calls` (если включён fallback); поведение детерминировано и ограничено по budget.
  **Tests:** unit на fallback + лимиты.
  **Deps:** W81-3,W81-9
- [x] W81-37 `tools/rlm_links_build.py`, `templates/aidd/config/conventions.json`, tests: ограничить rg‑скан по `target_files`:
  - применять `rlm.max_files` к `target_files` даже если они пришли из targets;
  - при больших списках предпочитать `keyword_hits` (если есть) и фиксировать `target_files_trimmed` в stats.
  **AC:** `rg` не сканирует сверх лимита; stats отражают trim и источник списка.
  **Tests:** unit на trim/источник.
  **Deps:** W81-3,W81-4,W81-9
- [x] W81-38 `tools/reports_pack.py`, `tools/research_check.py`, tests: добавить видимость “partial pack”:
  - пак содержит `worklist_entries`/`nodes_total` и предупреждение при сильном дисбалансе;
  - `research_check` WARN при `nodes_total << worklist_entries` даже если есть pack.
  **AC:** partial‑state отражён в pack и gate‑WARN детерминирован.
  **Tests:** unit на partial pack WARN.
  **Deps:** W81-11,W81-31

### EPIC T — RLM field run follow-ups (P1)
- [x] W81-39 `tools/rlm_nodes_build.py`, `templates/aidd/config/conventions.json`, tests: ограничить размер worklist и сделать его управляемым:
  - добавить `rlm.worklist_max_entries` (или `--worklist-max`) с детерминированным trim;
  - писать в pack `entries_total`, `entries_trimmed`, `trim_reason=max_entries`.
  **AC:** worklist capped без изменения порядка; `entries_total/trimmed` отражают факт усечения.
  **Tests:** unit на trim и стабильность.
  **Deps:** W81-8,W81-5
- [x] W81-40 `tools/rlm_links_build.py`, `templates/aidd/config/conventions.json`, tests: снизить false‑positive links при fallback на `public_symbols`:
  - добавить `rlm.link_fallback_mode=types_only|all` (default `types_only`);
  - в `types_only` учитывать только PascalCase символы и помечать links как `unverified` (или полностью исключать) при fallback.
  **AC:** при пустых `key_calls` не создаются ложные links по именам методов (list*/get*/set*).
  **Tests:** unit на fallback‑mode.
  **Deps:** W81-36,W81-9
- [x] W81-41 `tools/rlm_targets.py`, `templates/aidd/config/conventions.json`, tests: исключить workspace‑документацию из RLM roots:
  - добавить `rlm.exclude_path_prefixes` (default: `aidd/docs`, `aidd/reports`, `aidd/.cache`);
  - фильтровать `paths/paths_discovered` перед построением roots.
  **AC:** rlm-targets не содержит `aidd/docs/**` в `paths` и не сканирует их.
  **Tests:** unit на фильтрацию.
  **Deps:** W81-4
- [x] W81-42 `tools/rlm_links_build.py`, `templates/aidd/config/conventions.json`, tests: ограничить `rg`‑скан при больших `target_files`:
  - добавить `rlm.link_target_threshold` и при `target_files_total >= threshold` использовать `keyword_hits` (если есть);
  - записывать `target_files_source=keyword_hits` + `target_files_trimmed` в stats.
  **AC:** при больших repo links_build сканирует ограниченный список без ручной настройки.
  **Tests:** unit на threshold‑переключение.
  **Deps:** W81-37,W81-9
- [x] W81-43 `tools/rlm_nodes_build.py`, `tools/rlm_targets.py`, `templates/aidd/config/conventions.json`, docs/tests: narrow‑worklist режим для монореп:
  - добавить `--worklist-paths`/`--worklist-keywords` (или `rlm.worklist_paths`, `rlm.worklist_keywords`) для генерации ограниченного worklist;
  - при наличии фильтра сохранять `worklist_scope` в pack (`paths/keywords` + counts);
  - обновить `agents/researcher.md`/`commands/researcher.md` с советом запускать narrow‑worklist при `entries_total` >> лимита.
  **AC:** можно получить worklist < N по явным путям/keywords; pack отражает scope; детерминизм сохранён.
  **Tests:** unit на фильтрацию worklist по paths/keywords.
  **Deps:** W81-39,W81-4

### EPIC U — RLM scope & pack hardening (P1)
- [x] W81-44 `tools/rlm_links_build.py`, tests: учитывать `worklist_scope` при линковке:
  - если есть `*-rlm.worklist.pack.*` и `worklist_scope.paths/keywords` — ограничивать `target_files/keyword_hits` этим scope;
  - логировать `target_files_scope=worklist` + counts в stats (и fallback на `targets` при отсутствии scope).
  **AC:** links/build не уходит в внешние модули при заданном worklist; unverified links снижаются; stats отражают источник.
  **Tests:** unit на фильтрацию `target_files` по worklist scope.
  **Deps:** W81-43,W81-9
- [x] W81-45 `tools/rlm_targets.py`, `templates/aidd/config/conventions.json`, tests: strict‑paths режим для RLM targets:
  - добавить `rlm.targets_mode=explicit|auto` (default `auto`);
  - в `explicit` отключать auto‑discovery и tag‑paths, если пользователь задал `paths`;
  - отражать режим в `rlm-targets.json` (`targets_mode`).
  **AC:** при explicit‑режиме `paths_discovered` пуст, список файлов ограничен явными путями.
  **Tests:** unit на поведение explicit/auto.
  **Deps:** W81-4
- [x] W81-46 `tools/reports_pack.py`, `templates/aidd/config/conventions.json`, tests: жёсткое соблюдение pack‑budget:
  - добавить `rlm.pack_budget.enforce=true` и trim‑стратегию (снижение top‑N + обрезка snippets) до достижения лимитов;
  - писать `pack_trim_stats` для причин/шагов.
  **AC:** итоговый RLM pack всегда <= `max_chars/max_lines` при enforce.
  **Tests:** unit на hard‑budget.
  **Deps:** W81-11
- [x] W81-47 `templates/aidd/docs/anchors/research.md`, `agents/researcher.md`, `commands/researcher.md`: обновить guidance по scope‑контролю:
  - описать `worklist_scope`, `targets_mode`, `exclude_path_prefixes`;
  - показать пример узкого скоупа для снижения unverified links.
  **AC:** docs/agents отражают новые knobs.
  **Deps:** W81-44,W81-45
- [x] W81-34 `tools/research.py`, tests: RLM‑режим отключает call‑graph по умолчанию:
  - при `--evidence-engine rlm` не запускать call‑graph/ast‑grep, если они не запрошены явно;
  - исключить генерацию `*-call-graph.pack.*` и edges в RLM‑режиме.
  **AC:** RLM‑режим не создаёт legacy артефактов без явного флага.
  **Tests:** `tests/test_research_rlm_e2e.py` (assert no call-graph artifacts).
  **Deps:** W81-13
- [x] W81-35 `tools/rlm_links_build.py`, `tools/schemas/rlm_link.schema.json`, `tools/reports_pack.py`, tests: поддержать unverified links при отсутствии target‑node:
  - если rg/regex находит определение, но dest‑node нет → создать link с `dst_file_id` от path и `unverified=true`;
  - pack builder исключает unverified из топ‑evidence.
  **AC:** unverified links фиксируются в jsonl, но не попадают в pack.
  **Tests:** unit на unverified link и фильтрацию в pack.
  **Deps:** W81-9,W81-11

### EPIC V — Field-run fixes (P1)
- [x] W81-48 `tools/rlm-nodes-build.sh`, `agents/researcher.md`, `commands/researcher.md`: добавить bootstrap‑wrapper для `rlm_nodes_build`:
  - wrapper выставляет `CLAUDE_PLUGIN_ROOT` + `sys.path`, запускает `tools/rlm_nodes_build.py`;
  - обновить allowed-tools и примеры agent‑flow (без `PYTHONPATH`).
  **AC:** `rlm-nodes-build.sh --help` запускается из workspace; agent‑flow работает без ручного `PYTHONPATH`.
  **Tests:** smoke `--help`.
  **Deps:** W81-27
- [x] W81-49 `templates/aidd/rlm/prompts/file_node.md`, `tools/schemas/rlm_node.schema.json`, `tools/rlm_links_build.py`, `tools/rlm_verify.py`, tests: добавить type‑refs для линковки:
  - в prompt добавить `type_refs[]` (типы полей/параметров/return‑type, особенно для record/DTO);
  - schema: добавить `type_refs[]` (bump schema_version) и включить в verify;
  - links_build использует `type_refs` как отдельный источник (merge с key_calls по config).
  **AC:** links строятся между DTO/record файлами без ручного key_calls; unverified снижаются.
  **Tests:** unit на `type_refs` (schema + links build).
  **Deps:** W81-2,W81-6,W81-9
- [x] W81-50 `templates/aidd/rlm/prompts/file_node.md`, `tools/reports_pack.py`, docs/tests: привести `framework_roles` для моделей/DTO:
  - добавить роль `model|dto` (guidance) и запретить default `web` для payload‑классов;
  - entrypoints‑ролям не учитывать `model|dto`, чтобы не раздувать pack.
  **AC:** DTO‑файлы не попадают в entrypoints без явной роли; pack остаётся компактным.
  **Tests:** unit на фильтрацию entrypoints по roles.
  **Deps:** W81-6,W81-11
- [x] W81-51 `tools/reports_pack.py`, `templates/aidd/config/conventions.json`, tests: стабилизировать соблюдение `max_lines` для RLM pack:
  - auto‑trim продолжает сокращение списков до прохождения `max_lines` (даже при `enforce=false`);
  - если `pack_trim_stats` делает pack больше лимита — опционально сворачивать его до `{"enforce": false}`.
  **AC:** RLM pack не превышает `max_lines` при дефолтном бюджете; предупреждения уменьшаются.
  **Tests:** unit на max_lines‑trim.
  **Deps:** W81-11,W81-46
- [x] W81-52 `tools/rlm_nodes_build.py`, `tools/reports_pack.py`, `agents/researcher.md`: автоматизировать refresh worklist‑статуса:
  - добавить `--refresh-worklist` (или авто‑refresh в agent‑flow) после записи nodes/links;
  - обновлять worklist pack и `rlm_status` без ручного повторного запуска.
  **AC:** после agent‑flow статус становится `ready` без дополнительного шага; worklist корректно очищается.
  **Tests:** unit на refresh flow.
  **Deps:** W81-8,W81-27
- [x] W81-53 `tools/research.py`, `tools/rlm_targets.py`, `tools/researcher_context.py`, docs/tests: добавить CLI‑override для `targets_mode`:
  - флаг `--targets-mode explicit|auto` в research/rlm_targets;
  - при `explicit` отключать discovery даже если config `auto`.
  **AC:** можно зафиксировать scope на `--paths` без правки config; targets_mode отражён в `rlm-targets.json`.
  **Tests:** unit на флаг explicit.
  **Deps:** W81-4,W81-45

### EPIC W — Field-run regression fixes (P1)
- [x] W81-54 `tools/rlm_links_build.py`, `tools/reports_pack.py`, tests: подтверждать links для `type_refs` без fallback‑unverified:
  - если link построен из `type_refs` и есть evidence (`regex`/`rg`) — считать его verified;
  - не включать `public_symbols` fallback, если `type_refs` присутствуют (или отдельный флаг приоритетов);
  - pack включает такие links в evidence.
  **AC:** `links_included > 0` для DTO‑модулей с `type_refs`; `fallback_nodes` не растёт при наличии `type_refs`.
  **Tests:** unit на verified links из `type_refs`.
  **Deps:** W81-49,W81-11
- [x] W81-55 `tools/rlm_nodes_build.py`, `tools/reports_pack.py`, tests: refresh worklist сохраняет scope:
  - `--refresh-worklist` читает текущий worklist pack и переиспользует `worklist_scope` (paths/keywords), если args не заданы;
  - статус не становится `pending` из‑за “расширения” скоупа.
  **AC:** refresh не расширяет worklist без явных флагов; `rlm_status` остаётся ready при полном покрытии.
  **Tests:** unit на refresh с scope.
  **Deps:** W81-52
- [x] W81-56 `tools/research.py`, `tools/researcher_context.py`, `tools/rlm_targets.py`, docs/tests: явные RLM‑paths при запуске research:
  - добавить флаг `--rlm-paths` (или использовать `--paths` как override для RLM targets);
  - при `targets_mode=explicit` использовать только явные RLM‑paths, без дополнительных default paths.
  **AC:** rlm-targets не содержит чужие roots (например `frontend`) при explicit‑scope.
  **Tests:** unit на CLI override.
  **Deps:** W81-53
- [x] W81-57 `tools/rlm_links_build.py`, `templates/aidd/config/conventions.json`, tests: корректировать stats при type_refs:
  - добавить `link_type_refs_priority` (например `prefer`), чтобы не учитывать fallback при наличии `type_refs`;
  - `symbols_source` отражает реальный источник без “+type_refs”, если key_calls пусты.
  **AC:** stats не вводят в заблуждение, `fallback_nodes` корректен.
  **Tests:** unit на stats.
  **Deps:** W81-54
- [x] W81-58 `tools/reports_pack.py`, `templates/aidd/config/conventions.json`, tests: улучшить trim‑политику для RLM pack:
  - добавить опцию `pack_budget.trim_priority` (например, `recommended_reads,hotspots,entrypoints,...`);
  - при `max_lines` сначала тримить high‑cardinality секции.
  **AC:** pack стабильно укладывается в max_lines без “случайных” срезов важных секций.
  **Tests:** unit на приоритет trim.
  **Deps:** W81-51

### EPIC X — Field-run follow-ups (P1)
- [x] W81-59 `tools/reports_pack.py`, `templates/aidd/config/conventions.json`, tests: стабилизировать research pack budget:
  - добавить config override для `RESEARCH_BUDGET` (например `reports.research_pack_budget.{max_chars,max_lines}`);
  - auto‑trim должен продолжаться до укладывания в `max_chars`/`max_lines`, с drop `pack_trim_stats`, если он мешает;
  **AC:** research pack не превышает `max_chars` при дефолтном бюджете; WARN о превышении пропадает.
  **Tests:** unit на research pack budget (max_chars).
  **Deps:** -
- [x] W81-60 `tools/reports-pack.sh`, `agents/researcher.md`, `commands/researcher.md`, tests: wrapper для `reports_pack.py` без `PYTHONPATH`:
  - wrapper выставляет `CLAUDE_PLUGIN_ROOT` и `sys.path`, принимает все аргументы `reports_pack.py`;
  - обновить agent‑flow примеры на wrapper.
  **AC:** `reports-pack.sh --help` работает из workspace; agent‑flow не требует `PYTHONPATH`.
  **Tests:** smoke `--help` в `tests/test_rlm_wrappers.py`.
  **Deps:** W81-48
- [x] W81-61 `templates/aidd/rlm/prompts/file_node.md`, docs: усилить extraction `type_refs` для Java:
  - явно требовать `type_refs` из `implements/extends`, record/enum компонентов, public API типов;
  - добавить короткий пример в prompt/anchor, чтобы сократить fallback‑symbols.
  **AC:** prompt явно покрывает `implements/extends` и record/enum типы; fallback_nodes снижаются на Java‑модулях.
  **Deps:** W81-49

### EPIC Y — Field-run tuning follow-ups (P1)
- [x] W81-62 `templates/aidd/docs/anchors/research.md`, `templates/aidd/conventions.md`, `README*`: задокументировать research pack budget overrides:
  - описать `reports.research_pack_budget.max_chars/max_lines` и когда их повышать;
  - добавить короткий пример конфига.
  - увеличить дефолтный бюджет в шаблонах (например `max_chars=2000`, `max_lines=120`) и отразить это в docs.
  **AC:** документация содержит knob + пример; дефолтный бюджет увеличен в шаблонах.
  **Deps:** W81-59
- [x] W81-63 `templates/aidd/rlm/prompts/file_node.md`, `tests/test_rlm_links_build.py`: усилить extraction `key_calls`:
  - явно извлекать `key_calls` из вызовов методов/конструкторов/фабрик (особенно Java);
  - добавить test, где links строятся из `key_calls`, когда `type_refs` отсутствуют и fallback выключен.
  **AC:** links_build опирается на `key_calls` для Java‑вызовов; fallback_nodes снижаются на модулях без type_refs.
  **Deps:** W81-49
- [x] W81-64 `tools/reports_pack.py`, `templates/aidd/config/conventions.json`, tests: предупреждать о высокой доле fallback‑symbols:
  - добавить `rlm.link_fallback_warn_ratio` (default 0.3);
  - если fallback_nodes/total_nodes превышает порог — добавить warning в RLM pack.
  **AC:** pack содержит предупреждение при высокой доле fallback; проще находить слабые node‑summary.
  **Tests:** unit на warning trigger.
  **Deps:** W81-57

### EPIC Z — Field-run scope & link quality fixes (P1)
- [x] W81-65 `tools/research.py`, `tools/researcher_context.py`, `commands/researcher.md`, `templates/aidd/docs/anchors/research.md`: синхронизировать research scope с RLM paths:
  - если передан `--rlm-paths` и `--paths` не задан — использовать RLM paths как `paths` для research;
  - теги/keywords формируются только по синхронизированному scope (без шума из несвязанных модулей).
  **AC:** `--rlm-paths` не приводит к фронтенд‑шуму в context; `paths` совпадают с RLM scope.
  **Tests:** unit в `tests/test_research_command.py` или `tests/test_researcher_context.py`.
  **Deps:** W81-4,W81-13
- [x] W81-66 `tools/rlm_links_build.py`, `templates/aidd/config/conventions.json`, tests: считать rg‑evidence verified при наличии dest‑node:
  - добавить `rlm.link_rg_verify=auto|never` (default `auto`);
  - если rg/regex hit указывает на файл с node и `verification != failed` → `unverified=false`;
  - если dest‑node отсутствует — сохранять `unverified=true`.
  **AC:** verified links растут без расширения scope; unverified‑ratio снижается в полевых прогонах.
  **Tests:** unit на verified rg‑link при наличии dest‑node.
  **Deps:** W81-9,W81-7
- [x] W81-67 `tools/reports_pack.py`, `templates/aidd/config/conventions.json`, tests/docs: предупреждать о высокой доле unverified links:
  - добавить `rlm.link_unverified_warn_ratio` (default 0.5);
  - если `links_unverified/links_total` превышает порог — warning с советом расширить worklist scope или улучшить public_symbols/type_refs.
  **AC:** pack сигнализирует о низком качестве evidence.
  **Tests:** unit в `tests/test_reports_pack.py`.
  **Deps:** W81-11,W81-64
- [x] W81-68 `templates/aidd/config/conventions.json`, docs/tests: повысить дефолтный RLM pack budget для малых scope:
  - увеличить `rlm.pack_budget.max_lines` (например до 240) и при необходимости `max_chars`;
  - задокументировать knob в anchors.
  **AC:** на малых модулях pack не триммится по дефолту; docs описывают параметры.
  **Tests:** обновить budget‑tests при изменении дефолта.
  **Deps:** W81-11,W81-62
- [x] W81-69 `tools/rlm_links_build.py`, `templates/aidd/config/conventions.json`, tests: фильтрация type_refs по префиксам:
  - добавить `rlm.type_refs_include_prefixes`/`rlm.type_refs_exclude_prefixes` (default excludes: `java.*`, `jakarta.*`, `org.springframework.*`);
  - фильтровать `type_refs` перед линковкой, чтобы не плодить внешние unverified.
  **AC:** внешние типы не доминируют в link stats; unverified‑ratio падает без расширения scope.
  **Tests:** unit на фильтрацию type_refs.
  **Deps:** W81-49,W81-9
- [x] W81-70 `tools/reports_pack.py`, tests/docs: авто‑перевод `rlm_status=ready` при наличии nodes+links:
  - при `--update-context` и наличии `rlm_nodes_path`+`rlm_links_path` выставлять `rlm_status=ready` после успешного build RLM pack;
  - если nodes/links отсутствуют — оставлять `rlm_status=pending`;
  - обновлять context pack синхронно.
  **AC:** field‑run после nodes/links/pack переводит status в `ready` без ручных правок.
  **Tests:** unit на `rlm_status=ready` при наличии nodes+links.
  **Deps:** W81-11,W81-27
- [x] W81-71 `tools/rlm_links_build.py`, tests: классификация типа линка по evidence‑строке:
  - если evidence‑строка содержит `import ...` → `type=imports`;
  - если содержит `extends`/`implements` → `type=extends|implements` (детерминированно);
  - иначе fallback на `calls`.
  **AC:** import/extends/implements больше не маркируются как `calls`; `link_id` учитывает новый `type`.
  **Tests:** unit на классификацию link type.
  **Deps:** W81-9
- [x] W81-72 `tools/rlm-finalize.sh`, `tools/rlm_finalize.py`, `agents/researcher.md`, `commands/researcher.md`: утилита финализации RLM после ручного nodes:
  - цепочка: `rlm_verify` → `rlm_links_build` → `rlm_jsonl_compact` → `reports_pack --update-context`;
  - пишет `rlm_status=ready` и актуальные `rlm_*_path` в context.json.
  **AC:** один запуск финализирует RLM после ручной генерации nodes; шаги агент‑flow упрощены.
  **Tests:** smoke `--help` в `tests/test_rlm_wrappers.py`.
  **Deps:** W81-27,W81-28,W81-70

### EPIC AA — Full call-graph removal (P1)
- [x] W81-73 `tools/research.py`, `tools/researcher_context.py`, `tools/graph_slice.py`, `tools/call_graph_views.py`, `tools/reports_pack.py`: удалить code-paths call-graph:
  - убрать флаги `--call-graph`, `--graph-*`, `call_graph_*` поля контекста;
  - удалить сбор edges/pack и любые ссылки на `call-graph` в reports_pack;
  - удалить `graph_slice` CLI (или сделать no-op с WARN).
  **AC:** `rg call_graph` не находит code-paths в `tools/` (кроме legacy docs/guards); сборка research не пишет call-graph артефакты.
  **Tests:** обновить/удалить unit на call-graph edges/pack.
  **Deps:** W81-16,W81-17
- [x] W81-74 `templates/aidd/config/conventions.json`, `templates/aidd/config/gates.json`, `hooks/*`, `templates/aidd/AGENTS.md`, `README*`: удалить конфиг/гейты call_graph:
  - убрать секции `call_graph` и проверки gate‑workflow;
  - убрать упоминания call‑graph в docs/anchors/agents/commands.
  **AC:** no call_graph settings in templates; gate не упоминает call_graph.
  **Deps:** W81-73
- [x] W81-75 `tests/*`: удалить или переписать тесты call-graph:
  - `tests/test_researcher_call_graph*.py`, `tests/test_call_graph_edges_jsonl_schema.py`, `tests/test_graph_slice.py`, call-graph кейсы в `tests/test_reports_pack.py`/`tests/test_research_command.py`;
  - обновить smoke‑workflow, если ожидает call_graph config.
  **AC:** тестовый набор не ссылается на call_graph; `ci-lint` и smoke проходят.
  **Deps:** W81-73,W81-74
## Wave 82

_Статус: новый, приоритет 2. Цель — архитектурный профиль + runbooks как канон кастомизации, плюс унификация промптов и регрессионные проверки._

- [x] W82-1 `templates/aidd/docs/architecture/{profile.md,README.md}`, `templates/aidd/docs/{prd,plan,tasklist}/template.md`, `templates/aidd/docs/anchors/*.md`, `templates/aidd/AGENTS.md`, `commands/*.md`: ввести Architecture Profile как канон:
  - шаблон с front‑matter + обязательные секции (Style/Modules/Allowed deps/Invariants/Interfaces/Runbooks/Conventions);
  - machine‑readable front‑matter поля и формы:
    - `schema`, `updated_at`, `style`, `conventions`, `stack_hint` (список строк, multi‑stack);
    - `modules`: список объектов `{id, roots, responsibility, public_interfaces}`;
    - `allowed_deps`: список правил `{from, to, kind: allow|deny, note}` (from/to = module.id);
    - `enabled_runbooks`: список строк `["testing-node", "formatting", ...]`;
    - `interfaces`: объект `{api: [...], db: [...], events: [...]}`.
  - единый канонический путь `aidd/docs/architecture/profile.md` и единый формат ссылок:
    - PRD: `## AIDD:ARCH_PROFILE`;
    - Plan: `Architecture Profile: aidd/docs/architecture/profile.md`;
    - Tasklist: `AIDD:CONTEXT_PACK → References` (или отдельный пункт);
  - Context Pack шаблоны команд стадий (idea/research/plan/tasklist/spec-interview/review-spec/implement/review/qa) содержат `arch_profile: aidd/docs/architecture/profile.md` в Paths;
  - anchors/AGENTS (templates/aidd/AGENTS.md) ссылаются на профиль в MUST READ FIRST.
  **AC:** профиль существует с front‑matter, ссылки на канонический путь есть во всех шаблонах/якорях/Context Pack, AGENTS упоминает профиль как источник ограничений.
  **Deps:** -
- [x] W82-2 `templates/aidd/runbooks/**/RUNBOOK.md`, `templates/aidd/runbooks/index.yaml`, `templates/aidd/docs/architecture/profile.md`, `templates/aidd/docs/anchors/*.md`, `templates/aidd/AGENTS.md`: добавить базовую библиотеку runbooks и связать с профилем:
  - минимальный набор runbooks (testing‑gradle/node/pytest, formatting, dev-run);
  - общий контракт RUNBOOK.md: `name`, `version`, `when_to_use`, `commands`, `evidence`, `pitfalls`, `tooling`;
  - registry `templates/aidd/runbooks/index.yaml` (runbook_id → path → описание);
  - `runbook_id` совпадает с именем директории: `templates/aidd/runbooks/<runbook_id>/RUNBOOK.md` и `index.yaml` использует тот же `runbook_id`;
  - `enabled_runbooks` в profile + секция “Runbooks enabled”;
  - правило “runbooks‑first для tests/format/run” + fallback (“если runbook отсутствует — не выдумывать команды, запросить/добавить runbook”).
  **AC:** runbooks и registry в templates, профиль их перечисляет, anchors требуют открывать RUNBOOK.md и описывают fallback.
  **Deps:** W82-1
- [x] W82-3 `tools/init.sh`, `tools/init.py`, `commands/aidd-init.md`: расширить init для архитектуры/runbooks:
  - `tools/init.sh` — entrypoint команды; `tools/init.py` — реализация, вызываемая entrypoint (без дублирования логики);
  - init гарантирует `aidd/docs/architecture/*` и `aidd/runbooks/**` (и не трогает существующий `aidd/AGENTS.md`);
  - обновить описание флагов и DoD в команде.
  **AC:** `/feature-dev-aidd:aidd-init` создаёт профиль/runbooks при отсутствии, не ломая существующие файлы.
  **Tests:** обновить `tests/test_init_aidd.py` (`aidd/AGENTS.md` сохраняется).
  **Deps:** W82-1,W82-2
- [x] W82-4 `tools/detect-stack.(py|sh)`, `tools/init.sh`, `tools/init.py`, `commands/aidd-init.md`, tests: stack‑detector → заполнение profile:
  - детект langs/build tools по маркерам (package.json/pyproject/go.mod/Cargo.toml/etc);
  - multi‑stack поддержка: `stack_hint` и `enabled_runbooks` пополняются без взаимоисключения;
  - детектор игнорирует `aidd/**`, `.git/**`, `node_modules/**`, `.venv/**`;
  - флаг `--detect-stack` (или расширение `--detect-build-tools`) заполняет `stack_hint` и `enabled_runbooks` в profile best‑effort;
  - формат вывода: `--format json|yaml` → stdout = чистый структурированный output, summary → stderr; без `--format` → stdout = summary;
  - не перезаписывать существующий profile без `--force`; сохранять markdown body/sections (merge front‑matter).
  **AC:** init пишет stack_hint/runbooks при детекте, поддерживает multi‑stack, игнорирует `aidd/**`, не разрушает существующие данные.
  **Tests:** unit/fixture на детект и non‑destructive init.
  **Deps:** W82-3
- [x] W82-5 `agents/*.md`, `templates/aidd/docs/anchors/*.md`, `commands/*.md`, `agents/implementer.md`, `commands/implement.md`: унификация промптов и команд:
  - “RLM Read Policy” → “Evidence Read Policy” с RLM‑first + rlm‑slice (agents/anchors/commands);
  - единый блок “Context precedence & safety” во всех агентах + ключевых anchors;
  - единый базовый output contract (Checkbox/Status/Artifacts/Next actions) во всех агентах/командах; implementer может иметь расширенные поля поверх базового;
  - убрать gradlew‑специфику из implementer/implement → runbooks‑first для тестов/формата;
  - allowed‑tools стратегия: безопасный superset конкретных раннеров (без `Bash(*)`), например `Bash(npm:*)`, `Bash(pnpm:*)`, `Bash(yarn:*)`, `Bash(pytest:*)`, `Bash(python:*)`, `Bash(go:*)`, `Bash(mvn:*)`, `Bash(./gradlew:*)`, `Bash(make:*)` (если применимо); gradlew можно оставить в allowlist, но не хардкодить в тексте.
  - при добавлении новых tools/скриптов команд (rlm-slice, loop-pack, review-pack, diff-boundary-check) обновлять allowlist.
  **AC:** единые блоки/термины в промптах/командах, нет build‑tool hardcode, allowed‑tools согласованы со runbooks, prompt_version/source_version обновлены.
  **Tests:** `tests/repo_tools/prompt-version` + `tests/repo_tools/lint-prompts.py`.
  **Deps:** W82-2
- [x] W82-6 `tests/repo_tools/prompt-regression.sh` (или расширение `lint-prompts.py`), `tests/repo_tools/ci-lint.sh`: prompt‑regression checks:
  - fail при наличии “Graph Read Policy”;
  - fail если нет ссылок на architecture profile в агентах/anchors;
  - fail если Context Pack шаблоны команд стадий (idea/research/plan/tasklist/spec-interview/review-spec/implement/review/qa) не содержат `arch_profile` путь; исключить `status` и `aidd-init`;
  - fail если нет упоминания `rlm-slice.sh` как primary tool;
  - fail если не найден “Evidence Read Policy”.
  **AC:** регресс‑скрипт падает на старых промптах и проходит на новых.
  **Deps:** W82-5
- [x] W82-7 `README.md`, `README.en.md`, `templates/aidd/docs/**`, `CHANGELOG.md`: документация профиля/runbooks/init:
  - разделы про Architecture Profile + Runbooks + stack‑detect;
  - краткий “how to customize” в templates;
  - миграция: `/aidd-init` без `--force` добавляет новые артефакты; `--force` или ручная синхронизация — для обновления шаблонов;
  - пояснение root `AGENTS.md` vs `aidd/AGENTS.md`.
  - когда и как обновлять Architecture Profile (1–2 предложения).
  - changelog/metadata при user‑facing изменениях.
  **AC:** docs отражают новый канон и команды init.
  **Deps:** W82-1,W82-3,W82-5
- [x] W82-8 `tools/arch-profile-validate.(py|sh)`, `tests/repo_tools/ci-lint.sh` (optional): валидатор profile:
  - проверка front‑matter `schema: aidd.arch_profile.v1` и ключевых секций;
  - non‑zero exit при отсутствии/битых секциях;
  - не валидировать существование файла `conventions` на этом wave (только поле);
  - (опционально) init вызывает валидатор и предупреждает при ошибках.
  **AC:** валидатор ловит пустой/битый профиль, CI/инициализация видит ошибку или warn.

## Wave 83

_Статус: новый, приоритет 2. Цель — “Ralph loop mode” для implement↔review: loop pack + scope guard + уменьшение читаемого контекста._

- [x] W83-1 `templates/aidd/docs/loops/README.md`, `templates/aidd/reports/loops/.gitkeep`, `templates/aidd/docs/tasklist/template.md`, `templates/aidd/docs/anchors/{implement,review,tasklist}.md`, `templates/aidd/AGENTS.md`, `tools/init.sh`, `tools/init.py`: ввести канонический Loop Mode (без runtime‑логики):
  - добавить `templates/aidd/docs/loops/README.md` с протоколом: “loop = 1 work_item → implement → review → (revise)* → ship” + правила “fresh context / no big paste / ссылки на reports”;
  - правило: review не инициирует новый scope; всё новое → `AIDD:OUT_OF_SCOPE_BACKLOG`/новый work_item;
  - добавить `templates/aidd/reports/loops/.gitkeep` (директория должна появиться после `/aidd-init`);
  - init гарантирует `aidd/docs/loops/README.md` и `aidd/reports/loops/`;
  - расширить tasklist: `## AIDD:OUT_OF_SCOPE_BACKLOG` (фиксировать побочки вместо расширения текущего work_item);
  - anchors implement/review/tasklist + `templates/aidd/AGENTS.md`: 5–10 строк о loop‑discipline, запрет scope‑creep, ссылка на `aidd/docs/loops/README.md`.
  **AC:** после `/aidd-init` есть `aidd/docs/loops/README.md` и `aidd/reports/loops/`; tasklist шаблон содержит `AIDD:OUT_OF_SCOPE_BACKLOG`; anchors явно упоминают loop‑режим и запрещают scope creep.
  **Deps:** W82-1, W82-2, W82-3

- [x] W83-2 `tools/loop-pack.sh`, `tools/loop_pack.py`, `templates/aidd/docs/loops/template.loop-pack.md`, `tests/test_loop_pack.py`, `tests/fixtures/loop_pack/**`: генерация “Loop Pack” (тонкий входной контекст на один work_item):
  - `tools/loop-pack.sh` — entrypoint; `tools/loop_pack.py` — реализация (без дубля логики);
  - вход: `aidd/docs/tasklist/<ticket>.md`, `aidd/docs/architecture/profile.md`, `aidd/runbooks/index.yaml` + `aidd/runbooks/**/RUNBOOK.md`;
  - выбор work_item:
    - default (stage=implement): если `.active_ticket == --ticket` и `aidd/docs/.active_work_item` существует — использовать его; иначе выбрать первый реальный item из `AIDD:NEXT_3` (игнорируя `(none)`), извлечь `ref: iteration_id=...` или `ref: id=...`, записать `aidd/docs/.active_work_item`;
    - default (stage=review): читать `aidd/docs/.active_work_item` только если `.active_ticket == --ticket`; если нет — fallback на последний implement из `AIDD:PROGRESS_LOG`, иначе `BLOCKED`;
    - override: `--work-item iteration_id=I3` или `--work-item id=review:F6` (опционально `--pick-next` для принудительного выбора из NEXT_3);
  - loop-pack владеет state: после выбора work_item записывает `aidd/docs/.active_ticket` и `aidd/docs/.active_work_item` (work_item_key);
  - имя файла: `aidd/reports/loops/<ticket>/<work_item_key>.loop.pack.md` (fs‑safe ключ без `:`); хранить `work_item_id` и `work_item_key` в front‑matter;
  - front‑matter включает `schema: aidd.loop_pack.v1`, `updated_at`, `ticket`, `boundaries: { allowed_paths: [...], forbidden_paths: [...] }`,
    а также `runbooks_required`, `tests_required`, `arch_profile`, `evidence_policy` (для стабильного парсинга);
  - pack содержит минимум: `work_item_id`, `work_item_key`, `goal`, `do_not_read` (запрещённые источники);
  - `tests_required` — список `runbook_id` (команды берутся только из `RUNBOOK.md`);
  - `boundaries.allowed_paths` строится из `Expected paths` выбранного work_item в tasklist (W83-6); `forbidden_paths` по умолчанию `[]`;
  - (опционально) `work_item_excerpt` ≤ 30 строк (вырезка из tasklist для выбранного item);
  - CLI формат: `--format json|yaml` → stdout = чистый structured output, summary → stderr; без `--format` → stdout = summary (path + work_item).
  **AC:** stage=implement использует `.active_work_item` только если `.active_ticket` совпадает (иначе пишет новый), stage=review валидирует `.active_ticket` и использует `.active_work_item` только при совпадении (иначе fallback/BLOCKED); имена файлов fs‑safe; pack содержит `schema` и `updated_at`; `--format json` стабилен для unit‑tests; генерация не требует чтения plan/PRD/research.
  **Deps:** W83-1, W82-1, W82-2, W82-5

- [x] W83-3 `commands/implement.md`, `agents/implementer.md`, `templates/aidd/docs/anchors/implement.md`, `templates/aidd/AGENTS.md`, `tests/repo_tools/lint-prompts.py`: loop-pack first на implement:
  - в `commands/implement.md` сначала выставить `aidd/docs/.active_stage=implement`, затем вызвать `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage implement` (loop-pack выставляет `.active_ticket`/`.active_work_item`) + allowlist tool;
  - Context Pack `aidd/reports/context/$1.implement.pack.md`: добавить `arch_profile` и `loop_pack` в Paths;
  - Context Pack: добавить `review_pack: aidd/reports/loops/$1/review.latest.pack.md` (if exists);
  - subagent instruction: **First action: Read loop_pack**, не tasklist целиком;
  - `agents/implementer.md`: MUST KNOW FIRST → loop_pack + runbooks; правило “если новая работа вне pack → AIDD:OUT_OF_SCOPE_BACKLOG, не расширять diff”; запрет больших вставок логов/диффов (только ссылки на `aidd/reports/**`);
  - `agents/implementer.md`: если `review.latest.pack.md` существует и verdict=REVISE — читать после loop_pack, до кода;
  - anchors implement: вставить “Loop protocol” (патч A).
  **AC:** `/feature-dev-aidd:implement` всегда создаёт loop pack и передаёт implementer как primary context; implementer не обязан читать PRD/Plan/Research на каждом прогоне; побочные идеи уходят в out‑of‑scope backlog.
  **Tests:** lint‑prompts требует loop_pack‑first.
  **Deps:** W83-2, W82-5

- [x] W83-4 `tools/review-pack.sh`, `tools/review_pack.py`, `commands/review.md`, `agents/reviewer.md`, `templates/aidd/docs/anchors/review.md`, `tests/test_review_pack.py`: тонкий feedback от review:
  - `tools/review-pack.sh` entrypoint + `tools/review_pack.py` реализация;
  - вход: `aidd/reports/reviewer/<ticket>.json`; выход: `aidd/reports/loops/<ticket>/review.latest.pack.md` (≤ 120 строк);
  - содержимое pack: `verdict: SHIP|REVISE`, top findings (id/severity/1‑line requirement), next_actions (≤ 5), ссылки на handoff ids + reviewer report json;
  - `commands/review.md`: сначала выставить `aidd/docs/.active_stage=review`, затем вызвать `${CLAUDE_PLUGIN_ROOT}/tools/loop-pack.sh --ticket $1 --stage review` (loop-pack выставляет `.active_ticket`/`.active_work_item`) + allowlist tool; после `review-report.sh` вызвать `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh --ticket $1`; Context Pack добавить `loop_pack` и `review_pack` в Paths;
  - `agents/reviewer.md` и anchor review: правило “детали в tasklist/отчётах, без распухания текста” + loop‑protocol (патч B/D).
  **AC:** `/feature-dev-aidd:review` всегда создаёт `review.latest.pack.md` ≤ 120 строк; следующий implement может опираться на review_pack вместо длинного контекста.
  **Deps:** W83-2, W82-5

- [x] W83-5 `tools/diff-boundary-check.sh`, `tools/diff_boundary_check.py`, `commands/implement.md`, `commands/review.md`, `tests/test_diff_boundary_check.py`: scope guard против раздувания diff:
  - input: `--ticket` (default: resolve loop_pack via `.active_work_item`) или `--loop-pack <path>`;
  - инструмент читает allowed/forbidden paths из loop_pack front‑matter (или `--allowed path1,path2`), сравнивает с `git diff --name-only` + `git diff --cached --name-only`, игнорирует `aidd/**` и сервисные пути;
  - non‑zero exit + список нарушений (стабильный вывод для CI);
  - ignored patterns: `aidd/**`, `.claude/**`, `.cursor/**`, `.github/copilot-instructions.md`, `AGENTS.md`, `CLAUDE.md` (не игнорировать `.github/workflows/**`);
  - если boundaries пустые/не найдены → WARN `NO_BOUNDARIES_DEFINED`, exit 0 (поэтапный rollout);
  - интеграция: implement — после subagent и до `progress.sh`; review — перед отчётом; добавить allowlist tool;
  - поведение при FAIL: статус `BLOCKED`, рекомендации “откатить лишние файлы или оформить отдельный work_item/обновить boundaries через tasks-new”.
  **AC:** выход за allowed_paths блокирует команду и печатает список файлов; scope creep перестаёт проходить “по-тихому”.
  **Deps:** W83-2, W83-3, W83-4

- [x] W83-6 `agents/tasklist-refiner.md`, `templates/aidd/docs/tasklist/template.md`, `templates/aidd/docs/anchors/tasklist.md`: микро‑итерации, пригодные для loop‑pack:
  - в `AIDD:ITERATIONS_FULL` добавить поля с фиксированным форматом:
    - `Expected paths:` список строк `- path/**`
    - `Size budget:` `max_files: N`, `max_loc: N`
    - `Runbooks:` список `- <runbook_id>`
    - `Exit criteria:` 2–5 bullets
  - `tasklist-refiner` обязан заполнять эти поля; при невозможности — `Status: BLOCKED` и запрос `/spec-interview`;
  - правило: 1 iteration = 1 work_item; всё лишнее → `AIDD:OUT_OF_SCOPE_BACKLOG`.
  **AC:** новый tasklist после `/tasks-new` содержит Expected paths/Size budget/Runbooks/Exit criteria для каждой итерации; loop-pack строится из tasklist без чтения plan/prd.
  **Deps:** W82-2, W83-1

- [x] W83-7 `templates/aidd/docs/anchors/{implement,review}.md`, `agents/{implementer,reviewer}.md`, `templates/aidd/AGENTS.md`, `tests/repo_tools/lint-prompts.py`: минимальные патчи для “Ralph loop дисциплины”:
  - общий блок “Loop discipline” (патчи A/B) в anchors + implementer/reviewer agents;
  - порядок чтения: loop_pack → runbooks → tasklist snippet/код; PRD/Plan/Research только по pointer в pack;
  - output budget: ≤ 10 bullets внутри findings/next actions; контрактные поля ответа сохраняются; без логов/стектрейсов/диффов (только ссылки на `aidd/reports/**`);
  - Evidence Read Policy: loop pack фиксирует `evidence_policy: RLM-first` (термин единый с W82);
  - lint‑prompts: проверка наличия “Loop pack first” + “no big paste”.
  **AC:** anchors/agents содержат одинаковые loop‑блоки; lint‑prompts валидирует loop‑discipline.
  **Deps:** W83-2, W83-3, W83-4

- [x] W83-8 `tests/repo_tools/loop-regression.sh`, `tests/repo_tools/ci-lint.sh`, `README.md`, `README.en.md`, `CHANGELOG.md`: регресс‑контроль и документация loop‑режима:
  - checks: implement/review commands вызывают `loop-pack.sh`; review command вызывает `review-pack.sh`; anchors implement/review содержат loop‑protocol; loop pack schema = `aidd.loop_pack.v1`;
  - checks: stage=implement создаёт `.active_work_item`; review вызывает `loop-pack --stage review` до subagent;
  - loop-regression: базовые checks (loop-pack/review-pack + anchors); расширение loop-step/loop-run — в W83-12.
  - docs: “Loop mode (implement↔review)” (цикл, loop_pack/review_pack, diff boundary guard, runbooks → loop pack).
  **AC:** CI падает без loop‑pack/review‑pack и проходит на новой версии; docs описывают новый режим.
  **Deps:** W83-3, W83-4, W83-5, W83-7

- [x] W83-9 `hooks/format-and-test.sh`, `tests/test_hook_loop_mode.py`, `README.md`, `.gitignore`: loop‑режим без автотестов (Ralph loop):
  - stage-aware: если `aidd/docs/.active_stage = review` и diff пустой/только service → SKIP; иначе normal mode (warn+run);
  - loop‑mode (`aidd/docs/.active_mode = loop`) на stage=implement: **не запускать тесты по умолчанию**, даже если есть policy; форматирование можно оставить;
  - тесты запускаются только при явном override (например `AIDD_LOOP_TESTS=1` или `AIDD_TEST_FORCE=1`); при запуске — `mkdir -p aidd/reports/tests`, полный stdout/stderr → `aidd/reports/tests/<ticket>.<ts>.log`, в чат — только summary + ссылка;
  - ticket source: читать `aidd/docs/.active_ticket` (fallback `unknown`); в loop‑mode владелец `active_ticket` — loop-pack (commands ставят только stage);
  - anti-spam: если `git diff --name-only` и `git diff --cached --name-only` пустые или только `aidd/**` → не запускать тесты даже при override;
  - если `.active_stage` отсутствует → normal mode (поведение как сейчас); если `.active_mode` отсутствует → normal mode;
  - (опционально) `AIDD_HOOK_VERBOSITY=summary|full` (default summary).
  - `.gitignore`: добавить `aidd/docs/.active_*` (включая `.active_mode`).
  **AC:** цикл `implement → review → implement → review` не запускает тесты на review и не запускает тесты в loop‑mode без explicit override; implement не спамит логами; тесты не запускаются при пустом diff.
  **Deps:** W83-3, W83-4

- [x] W83-10 `tools/review-pack.sh`, `tools/review_pack.py`, `tests/test_review_pack.py`, `templates/aidd/docs/loops/README.md`: сделать Review Pack машинно‑читаемым:
  - `review.latest.pack.md` получает front‑matter: `schema: aidd.review_pack.v1`, `updated_at`, `ticket`, `work_item_id`, `work_item_key`, `verdict: SHIP|REVISE|BLOCKED`;
  - источник work_item: читать текущий loop_pack (resolved via `.active_work_item`), иначе оставлять пустым и фиксировать WARN;
  - `tools/review-pack.sh --format json|yaml` → stdout = structured output (verdict/paths/ids/next_actions), summary → stderr;
  - `templates/aidd/docs/loops/README.md`: 3–5 строк про automation reliance на `review_pack` front‑matter и `--format json`.
  **AC:** `review.latest.pack.md` всегда содержит `schema` и `verdict` в front‑matter; `--format json` стабилен и проходит unit‑test; markdown pack остаётся ≤ 120 строк.
  **Deps:** W83-4, W83-1

- [x] W83-11 `tools/loop-step.sh`, `tools/loop_step.py`, `tests/test_loop_step.py`, `tests/fixtures/loop_step/**`: “Loop Step” для bash‑цикла (fresh session):
  - step selection:
    - если `.active_stage` отсутствует → execute implement;
    - если `.active_stage == implement` → execute review;
    - если `.active_stage == review` → `review_pack.verdict`: REVISE→implement, SHIP→exit 0, иначе BLOCKED/REVIEW (deterministic);
  - runner default: `claude -p --no-session-persistence` (override via `--runner` или `AIDD_LOOP_RUNNER`); runner executes `/feature-dev-aidd:implement <ticket>` or `/feature-dev-aidd:review <ticket>`;
  - loop-step выставляет `aidd/docs/.active_mode=loop` перед запуском runner;
  - runner logs → `aidd/reports/loops/<ticket>/cli.<stage>.<ts>.log`, stdout = summary + paths; `--format json|yaml` for structured output;
  - если `review.latest.pack.md` отсутствует или schema != `aidd.review_pack.v1` → exit `20=BLOCKED` + краткая причина в stdout;
  - exit codes: `0`=DONE (SHIP), `10`=CONTINUE, `20`=BLOCKED, `30`=ERROR.
  **AC:** `loop-step --ticket T` чередует implement/review, возвращает 0 только при SHIP; structured output стабилен; unit‑tests со stub runner проверяют exit codes/sequence.
  **Deps:** W83-3, W83-4, W83-9, W83-10

- [x] W83-12 `tools/loop-run.sh`, `tools/loop_run.py`, `tests/test_loop_run.py`, `README.md`, `README.en.md`, `templates/aidd/docs/loops/README.md`, `tests/repo_tools/loop-regression.sh`: “Loop Run” (крутить до SHIP):
  - `loop-run` вызывает `loop-step` в цикле; флаги: `--ticket`, `--max-iterations`, `--sleep-seconds`, `--runner`;
  - пишет прогресс в `aidd/reports/loops/<ticket>/loop.run.log`;
  - при SHIP очищает `aidd/docs/.active_stage`, `aidd/docs/.active_work_item`, `aidd/docs/.active_mode`, `aidd/docs/.active_ticket`;
  - docs: manual loop, bash loop (loop-step), one-shot loop-run; объяснить “fresh sessions” (`claude -p --no-session-persistence`);
  - loop-regression: расширить checks из W83-8 (loop-step/loop-run + docs examples), без дублирования базовых.
  **AC:** `loop-run --ticket T --max-iterations 5` → exit 0 on SHIP, exit 11 on max-iterations, exit 20 on BLOCKED; docs содержат команды запуска; регрессия падает при отсутствии loop-step/loop-run или сломанных schema.
  **Deps:** W83-11, W83-8, W83-10

## Wave 84

_Статус: новый, приоритет 2. Цель — убрать AIDD runbooks из репозитория, заменить на рекомендацию project runbooks, очистить промпты/линты, усилить verify/least‑privilege и сохранить loop‑дисциплину._

- [x] W84-1 `templates/aidd/runbooks/**`, `templates/aidd/runbooks/index.yaml`, `.claude-plugin/plugin.json`, `tools/init.{sh,py}`, `commands/aidd-init.md`, `templates/aidd/docs/architecture/profile.md`, tests: убрать AIDD runbooks из репозитория:
  - удалить `templates/aidd/runbooks/**` и `templates/aidd/runbooks/index.yaml`;
  - убрать `enabled_runbooks`/runbooks‑секцию из архитектурного профиля и связанных шаблонов;
  - обновить `.claude-plugin/plugin.json`: убрать/почистить `runbooks`‑пути (если есть);
  - `aidd-init` больше не копирует runbooks;
  - обновить/удалить тесты, ожидавшие runbooks.
  **AC:** в репозитории нет `templates/aidd/runbooks/**`; init не создаёт runbooks; тесты не требуют runbooks.
  **Deps:** W82-2

- [x] W84-2 `agents/*.md`, `commands/*.md`, `templates/aidd/docs/anchors/*.md`, `templates/aidd/AGENTS.md`, `templates/aidd/docs/{tasklist,loops}/template.*`: обновить ссылки/политики вокруг runbooks:
  - удалить любые ссылки на `aidd/runbooks/**` и “AIDD runbooks-first” в старом смысле;
  - новое правило:
    - если есть `commands/<runbook>/RUNBOOK.md` → использовать их;
    - иначе если есть `commands/**` → использовать их (legacy);
    - иначе → попытаться определить команды из repo; если не выходит → BLOCKED + запросить у пользователя команды;
  - обновить templates loop/tasklist, где упоминаются runbooks.
  **AC:** нет ссылок на `aidd/runbooks/**`; инструкции соответствуют “project runbooks optional”; templates loop/tasklist не подразумевают встроенные runbooks.
  **Deps:** W84-1

- [x] W84-3 `README.md`, `README.en.md`: рекомендация про project runbooks:
  - короткий блок: “процесс эффективнее с project-specific runbooks в `commands/`” + пример структуры;
  - явно указать, что это опционально.
  **AC:** README содержит ясную рекомендацию и пример `commands`.
  **Deps:** W84-2

- [x] W84-4 `templates/aidd/docs/loops/README.md`, `templates/aidd/docs/anchors/{implement,review}.md`, `README.md`, `README.en.md`: развести “Ralph plugin” и AIDD loop‑mode:
  - явно описать, что официальный Ralph loop — stop‑hook в той же сессии с completion promise;
  - отметить, что AIDD loop‑mode использует fresh sessions (`claude -p --no-session-persistence`);
  - добавить краткий safety‑блок: completion promise + max‑iterations.
  - в примерах CLI использовать формат `--max-iterations 5` (без `=`).
  **AC:** документация не конфликтует по терминологии; есть каноническое определение loop‑протокола в `aidd/docs/loops/README.md` и ссылка из anchors implement/review; пользователь видит разницу и безопасные ограничения.
  **Deps:** W83-12

- [x] W84-5 `agents/{implementer,reviewer,qa}.md`, `commands/{implement,review,qa}.md`, `templates/aidd/docs/anchors/{implement,review,qa}.md`, `tests/repo_tools/lint-prompts.py`: усилить verify‑шаг в промптах:
  - добавить явный пункт “verify results” (тесты/QA‑evidence) в пошаговый план;
  - закрепить, что без верификации нельзя выставлять финальный non‑BLOCKED статус (если не `profile: none`);
  - линт: проверять наличие verify‑шага в этих промптах.
  **AC:** промпты содержат verify‑шаг и правила статуса; lint‑prompts ловит отсутствие verify‑шага; финальный non‑BLOCKED статус запрещён без verify при `profile != none`.
  **Deps:** W82-5

- [x] W84-6 `agents/*.md`, `tests/repo_tools/lint-prompts.py`: stage drift guard:
  - убрать `set-active-feature.sh` и `set-active-stage.sh` из subagents tools;
  - добавить hard‑policy “subagents не меняют .active_*; при несоответствии → BLOCKED + перезапуск команды”.
  **AC:** ни один `agents/*.md` не содержит `set-active-*`; в subagents есть правило BLOCKED при некорректных `.active_*`; reviewer/qa allowlist соответствует edit‑surface (без `Write`).
  **Deps:** W82-5

- [x] W84-7 `tests/repo_tools/lint-prompts.py` (или новый `tests/repo_tools/prompt-references.sh`), `tools/doctor.sh` (optional): prompt ↔ tooling integrity (plugin-aware):
  - проверять, что упомянутые `${CLAUDE_PLUGIN_ROOT}/tools/*.sh` и `hooks/*.sh` реально существуют;
  - проверять критические артефакты в шаблонах (`templates/aidd/**`) и не требовать `aidd/**` до init;
  - добавить правило: нет ссылок на удалённые runbooks‑артефакты (`aidd/runbooks/**`, `templates/aidd/runbooks/**`);
  - проверять `.claude-plugin/plugin.json`: пути только с `./` и без `..`, и не указывают на удалённые runbooks;
  - запрет ссылок вида `${CLAUDE_PLUGIN_ROOT}/../...` и любых `../` для plugin assets;
  - валидировать, что ссылки на plugin‑скрипты используют `${CLAUDE_PLUGIN_ROOT}`.
  **AC:** CI падает при рассинхроне, при ссылках на удалённые runbooks, или при `../` в plugin assets.
  **Deps:** -

- [x] W84-8 `templates/aidd/AGENTS.md`, `templates/aidd/docs/anchors/rlm.md`, `agents/*.md`: сократить дублирование канонических политик:
  - вынести “Context precedence & safety” + “Evidence Read Policy (RLM-first)” в канон;
  - в агентах оставить короткую ссылку на канон + правило STOP при конфликте.
  **AC:** канон в одном месте; агенты ссылаются на него вместо копипасты.
  **Deps:** W82-5

- [x] W84-9 `agents/{reviewer,qa}.md`, `commands/{review,qa}.md`: least‑privilege для review/qa:
  - убрать `Write` из tools/allowed-tools;
  - оставить `Edit` как единственный write‑surface для tasklist.
  **AC:** reviewer/qa не имеют `Write`; edit‑surface соответствует политике; команды review/qa проходят без `Write` на базовом сценарии.
  **Deps:** W82-5

- [x] W84-10 `tools/init.{sh,py}`, `tools/doctor.sh`, `commands/aidd-init.md`: critical artifacts bootstrap:
  - `aidd-init` гарантирует наличие `aidd/AGENTS.md`, `aidd/docs/loops/README.md`, `aidd/docs/sdlc-flow.md`, `aidd/docs/status-machine.md`;
  - `doctor.sh` валидирует наличие и сообщает об ошибках; отсутствие `commands` не блокирует.
  **AC:** init создаёт критические файлы; doctor падает при отсутствии критических; отсутствие `commands` не ломает.
  **Deps:** W84-7

- [x] W84-11 `tools/loop_pack.py`, `templates/aidd/docs/loops/template.loop-pack.md`: loop pack excerpt quality:
  - обязательный excerpt: goal/DoD/boundaries/refs на AC или spec (если есть);
  - без него implementer вынужден читать plan/PRD, что ломает “fresh context”.
  **AC:** loop pack содержит обязательный excerpt и ссылки на DoD/AC.
  **Deps:** W83-2

## Wave 85

_Статус: новый, приоритет 1. Цель — закрыть проблемы AIDD Flow Audit (TST-001): RLM evidence, loop pack дисциплина, review/qa консистентность, tasklist/spec policy._

- [x] W85-1 `tools/research.sh`, `tools/rlm-finalize.sh`, `tools/rlm-verify.sh`, `commands/researcher.md`, `agents/researcher.md`, `templates/aidd/docs/anchors/research.md`, `tests/test_research_check.py`, `tests/test_research_rlm_e2e.py`: гарантировать полный RLM evidence перед `Status: reviewed`:
  - `rlm_status=ready` допустим только если существуют `*-rlm.pack.*`, `*-rlm.nodes.jsonl`, `*-rlm.links.jsonl`;
  - при отсутствии полного пакета команда researcher должна ставить `BLOCKED` и требовать `rlm-finalize`;
  - в prompt команды/агента явно зафиксировать обязательный вызов `rlm-finalize.sh --ticket $1` при `rlm_status=pending` (после subagent), иначе `BLOCKED`;
  - `research-check` блокирует переходы, если status ready без пакета/links/nodes.
  **AC:** RLM pack/nodes/links всегда присутствуют при `Status: reviewed`; без них researcher возвращает BLOCKED.
  **Deps:** -

- [x] W85-2 `commands/review.md`, `commands/qa.md`, `tests/test_context_pack.py`, `tests/repo_tools/lint-prompts.py`: обеспечить обязательное создание context pack для review/qa:
  - review создаёт `aidd/reports/context/<ticket>.review.pack.md` до subagent;
  - qa создаёт `aidd/reports/context/<ticket>.qa.pack.md` до subagent;
  - при неуспешной записи pack → `Status: BLOCKED` + понятный error.
  **AC:** review/qa всегда имеют соответствующий context pack; lint-проверка падает, если pack не указан в prompt.
  **Deps:** W84-7

- [x] W85-3 `tools/loop-pack.sh`, `tools/loop_pack.py`, `commands/implement.md`, `tests/test_loop_pack.py`, `tests/repo_tools/loop-regression.sh`: усилить loop-pack выбор и синхронизацию `.active_work_item`:
  - implement всегда вызывает loop-pack и валидирует существование `aidd/reports/loops/<ticket>/<work_item_key>.loop.pack.md`;
  - при смене итерации (NEXT_3) loop-pack должен обновлять `.active_work_item` и создавать pack для каждого work_item (I2/I3);
  - при отсутствии pack → `Status: BLOCKED` + рекомендация rerun.
  **AC:** на каждом implement итерации создаётся loop pack; `.active_work_item` соответствует последнему pack; регрессия ловит отсутствие pack.
  **Deps:** W83-2, W83-8

- [x] W85-4 `tools/review_report.py`, `tools/review_pack.py`, `tools/review-pack.sh`, `commands/review.md`, `tests/test_review_pack.py`: синхронизация review report и review pack:
  - после `/feature-dev-aidd:review` пересобирается `review.latest.pack.md` из актуального `aidd/reports/reviewer/<ticket>.json`;
  - повторный review перезаписывает pack с новым `updated_at` и verdict;
  - pack должен ссылаться на текущий `work_item_key` из `.active_work_item`.
  **AC:** review pack всегда отражает последний review report; verdict и findings совпадают с report.
  **Deps:** W83-10

- [x] W85-5 `tools/review_report.py`, `tools/qa.py`, `commands/review.md`, `commands/qa.md`, `tests/test_qa_agent.py`: нормализовать статусный словарь для review/qa:
  - допустимые статусы только `READY|WARN|BLOCKED`;
  - любые `PASS|NEEDS_FIXES|FAIL` должны мапиться на канон при записи отчётов;
  - tasklist front‑matter и `AIDD:CONTEXT_PACK Status` синхронизируются с canonical status.
  **AC:** reviewer/qa отчёты содержат только канонические статусы; tasklist и reports не расходятся.
  **Deps:** -

- [x] W85-6 `tools/qa.py`, `tools/qa.sh`, `tools/tasks-derive.sh`, `tests/test_qa_agent.py`, `tests/test_gate_qa.py`: QA report vs tasklist consistency:
  - дедуплицировать findings по id;
  - если QA чеклисты уже закрыты, report не должен оставаться `fail` из‑за stale checklist;
  - при наличии manual-only проверок выставлять `WARN` + явный список “manual required”.
  **AC:** QA report status детерминирован, без дублей; manual gaps дают WARN, не FAIL.
  **Deps:** W85-5

- [x] W85-7 `commands/tasks-new.md`, `agents/tasklist-refiner.md`, `tools/tasklist_check.py`, `templates/aidd/docs/anchors/tasklist.md`, `tests/test_tasklist_check.py`: enforce spec‑required policy для UI/UX изменений:
  - если plan/PRD указывает UI/UX или front-end изменения и spec отсутствует — tasklist status = BLOCKED и требование `/feature-dev-aidd:spec-interview`;
  - `tasklist-check` валидирует, что `AIDD:NEXT_3` не содержит `[x]` элементов.
  **AC:** UI/UX задачи без spec блокируются; NEXT_3 всегда без закрытых чекбоксов.
  **Deps:** W83-6, W84-2

- [x] W85-8 `.claude-plugin/marketplace.json`: устранить несоответствие ref в marketplace манифесте:
  - обновить `plugins[].source.ref` на актуальную ветку/тег (например, `wave-85` или `main`);
  **Deps:** -

- [x] W85-9 `hooks/hooks.json`, `tests/test_context_gc.py` (и/или `tests/test_bootstrap_e2e.py`): расширить matcher PreToolUse:
  - заменить `matcher: "Bash|Read"` на охват `Write|Edit|Glob` (или `.*`), чтобы GC видел все tool-use;
  - добавить/обновить тест, что matcher учитывает `Write`/`Edit`.
  **AC:** контекст‑GC запускается на Write/Edit/Glob; тест фиксирует новую матчинговую политику.
  **Deps:** -

- [x] W85-10 `commands/plan-new.md`, `tools/prd-check.{sh,py}` (или аналог), `tests/test_prd_ready_check.py`: enforce PRD READY перед plan-new:
  - добавить явный чек `Status: READY` в PRD (скрипт/CLI), вызываемый перед planner;
  - план‑new возвращает BLOCKED при draft PRD.
  **AC:** plan-new не стартует planner без READY PRD; есть тест на блокировку.
  **Deps:** -

- [x] W85-11 `tests/repo_tools/lint-prompts.py` (или `prompt-regression.sh`): guard против упоминаний skills:
  - добавить проверку, что нет ссылок на `aidd/skills/**` или `templates/aidd/skills/**` в prompts/docs;
  - оставить нейтральные упоминания слова “skills” без пути допустимыми.
  **AC:** CI падает при появлении ссылок на skills‑директорию.
  **Deps:** -

- [x] W85-12 `hooks/format-and-test.sh`, `tests/test_format_and_test.py`: расследовать расхождения тест‑политики:
  - воспроизвести failures (если актуально), сравнить ожидания тестов с текущим поведением hook;
  - обновить логику/тесты под актуальную политику (`AIDD_TEST_*`, reviewer marker, common patterns);
  - добавить regression кейс на “profile=none/fast/targeted/full”.
  **AC:** `test_format_and_test.py` стабильно проходит; поведение hook задокументировано в тестах.
  **Deps:** -

- [x] W85-13 `hooks/gate-workflow.sh`, `tests/test_gate_workflow.py`, `tools/gate_workflow.py` (если есть): выверить gate‑workflow поведение:
  - воспроизвести reported failures и локализовать drift между gate‑логикой и тестами;
  - поправить gate‑workflow или тесты так, чтобы gate корректно блокировал/разрешал стадии;
  - добавить/обновить edge‑case тесты на ACTIVE markers и missing artifacts.
  **AC:** `test_gate_workflow.py` стабильно проходит; gate‑workflow отражает актуальные правила SDLC.
  **Deps:** -

- [x] W85-14 `AGENTS.md`, `templates/aidd/AGENTS.md`, `README*.md`: устранить путаницу между dev/user AGENTS:
  - явно обозначить назначение каждого файла (Dev guide vs User guide);
  - при необходимости добавить ссылку‑навигацию между файлами или переименовать (с обратной совместимостью).
  **AC:** docs явно объясняют, какой AGENTS.md использовать и когда.
  **Deps:** -

- [x] W85-15 `.claude-plugin/plugin.json`, `tests/repo_tools/*`: стратегия auto‑discovery vs explicit listing:
  - определить, поддерживает ли runtime auto‑discovery без ручных списков;
  - либо перейти на auto‑discovery, либо добавить guard/генератор для sync списков.
  **AC:** добавление новой команды/агента не требует ручной правки без проверки; CI ловит рассинхрон.
  **Deps:** -

- [x] W85-16 `commands/*.md`, `agents/*.md`, `tools/prd-check.{sh,py}`, `tests/*`: интеграция PRD‑ready check:
  - аудит команд, которые используют PRD (plan/review‑spec/tasks/implement);
  - добавить/задокументировать обязательный `prd-check` где нужно;
  - добавить тесты на блокировку при draft PRD.
  **AC:** PRD‑ready проверяется перед критическими стадиями; есть regression‑тест.
  **Deps:** -

- [x] W85-17 `.mcp.json` (decision): MCP интеграция или явная фиксация отсутствия:
  - подтвердить, что отсутствие MCP намеренное;
  - если нужно — добавить `.mcp.json` или заметку в README.
  **AC:** решение задокументировано; отсутствие MCP не выглядит как баг.
  **Deps:** -

- [x] W85-18 `tools/*.sh` (python wrappers): привести shebang/именования к единой политике:
  - зафиксировать правило (например, `.sh` только для shell, `.py` для python);
  - при необходимости переименовать wrappers или добавить README‑объяснение.
  **AC:** нет путаницы между расширением и shebang; политика описана.
  **Deps:** -

- [x] W85-19 `hooks/gate-workflow.sh`, `tools/gate_workflow.py`: снижение размера и сложностей gate‑workflow:
  - вынести логику из shell в python‑модуль;
  - оставить shell как thin wrapper;
  - добавить unit‑тесты на вынесенные функции.
  **AC:** gate‑workflow легче поддерживать; тесты покрывают ключевые ветки.
  **Deps:** -

- [x] W85-20 `tools/qa_agent.py`, `tests/test_qa_agent.py`: корректная дедупликация QA checklist findings:
  - id для checklist включает контент строки, чтобы manual/blocker не схлопывались;
  - добавить тест на сохранение manual+blocker в одном tasklist.
  **AC:** blocker findings не теряются при наличии manual QA строк; regression‑тест покрывает кейс.
  **Deps:** -

- [x] W85-21 `tools/loop_pack.py`, `tests/test_loop_pack.py`: заполнить updated_at в loop pack и payload:
  - записывать `_utc_timestamp()` в front matter для всех сгенерированных pack (selected + prewarm);
  - убедиться, что structured output loop-pack содержит непустой updated_at.
  **AC:** loop pack front matter содержит непустой updated_at; тест валидирует формат/непустое значение.
  **Deps:** -

- [x] W85-22 `tools/loop_pack.py`, `tools/loop_step.py`, `commands/implement.md`, `tests/test_loop_pack.py`, `tests/repo_tools/loop-regression.sh`: REVISE не должен перескакивать на NEXT_3:
  - если `review.latest.pack.md` verdict=REVISE, implement loop-pack выбирает work_item из review pack (work_item_key) или первый handoff id из pack/`AIDD:HANDOFF_INBOX`;
  - не использовать NEXT_3 пока handoff задачи открыты; `.active_work_item` остаётся на review item;
  - добавить регрессионный тест на REVISE -> implement selection (loop-step).
  **AC:** при REVISE следующий implement работает по ревью‑work_item/handoff, а не по следующей итерации.
  **Deps:** W85-3, W85-4

- [x] W85-23 `tools/review_pack.py`, `tools/review_report.py`, `tests/test_review_pack.py`: улучшить содержание review pack и fresh‑guard:
  - в топ‑findings использовать поля `message`/`details` как fallback к `title/summary`;
  - дедуплицировать findings по id/тексту;
  - если review report обновлён позже pack (или verdict не совпадает со статусом), блокировать loop-step или пересобирать pack.
  **AC:** review pack показывает осмысленные findings (без n/a) и verdict всегда соответствует status review report.
  **Deps:** W85-4

- [x] W85-24 `commands/implement.md`, `commands/review.md`, `tools/diff_boundary_check.py`, `tests/repo_tools/loop-regression.sh`: зафиксировать boundary-check evidence:
  - implement/review обязаны выполнять diff-boundary-check и логировать `OK|OUT_OF_SCOPE|FORBIDDEN|NO_BOUNDARIES_DEFINED`;
  - OUT_OF_SCOPE/FORBIDDEN блокирует стадию;
  - добавить регрессионный тест, что boundary-check вызывается и блокирует при нарушении.
  **AC:** out-of-scope файлы блокируют loop; evidence записано в ответе/логах.
  **Deps:** -

- [x] W85-25 `templates/aidd/config/{gates.json,conventions.json,context_gc.json}`, `templates/aidd/conventions.md`, `AGENTS.md`: вычистить неиспользуемые настройки AIDD flow:
  - удалить неиспользуемые поля (например, `gates.tests.reviewerGate`, `context_gc.working_set.max_open_questions`, `conventions.rlm.{enabled,required_for_langs,max_nodes,verification_required}`, `conventions.rlm.slice_budget.max_chars`, `researcher.ast_grep.deprecated`);
  - обновить документацию/гайд по настройкам и примеры, чтобы отражали только поддерживаемые поля;
  - при необходимости добавить notes о несовместимых изменениях.
  **AC:** в шаблонах нет “мертвых” полей; docs описывают только реально используемые настройки.
  **Deps:** -

- [x] W85-26 `tools/feature_ids.py`, `tools/runtime.py`, `tools/tasklist_check.py`, `hooks/gate-*.sh`, `templates/aidd/config/gates.json`: убрать кастомизацию active ticket/slug и унифицировать reviewer marker:
  - удалить `feature_ticket_source`/`feature_slug_hint_source` из `config/gates.json` и документации;
  - инструменты и hooks всегда читают `docs/.active_ticket` и `docs/.active_feature`;
  - `tasklist_check` использует путь marker из `gates.reviewer.tests_marker`;
  - обновить тесты под стандартные пути (без кастомных источников).
  **AC:** отсутствуют кастомные пути в gates.json; hooks и CLI‑инструменты работают только со стандартными маркерами; нет рассинхрона.
  **Deps:** -

- [x] W85-27 `tools/init.py`, `tools/init.sh`, `commands/aidd-init.md`, `AGENTS.md`: удалить флаг `--commit-mode`:
  - убрать аргумент из CLI, help‑текста и документации;
  - очистить все упоминания/пример использования;
  - обновить тесты/сmoke, если проверяют наличие флага.
  **AC:** `aidd-init --help` не содержит `--commit-mode`, docs не ссылаются на него.
  **Deps:** -

## Wave 86

### Runtime refactor: pathing, pack format, shared utils
- [x] W86-1 `tools/runtime.py`, `tools/feature_ids.py`, `tools/resources.py`, `tools/analyst_guard.py`, `tools/prd_review.py`, `tools/qa_agent.py`, `tools/tasklist_check.py`, `tools/researcher_context.py`, `tools/research_guard.py`, `tools/rlm_config.py`, `tests/test_feature_ids_root.py`, `tests/test_cli_paths.py`, `tests/test_resources.py`: унифицировать root‑resolution:
  - ввести единый helper (в `tools/runtime.py` или отдельном модуле) для `workspace_root` + `aidd_root`;
  - deprecate/rename `tools.feature_ids.resolve_project_root`, чтобы исключить двусмысленность;
  - перевести все runtime‑скрипты на новый helper, обновить тесты путей.
  **AC:** все runtime tools работают из workspace и пишут только в `aidd/`; нет дубликатов `resolve_project_root`.
  **Deps:** -

- [x] W86-2 `tools/reports_pack.py`, `tools/reports/loader.py`, `tools/research.py`, `tools/researcher_context.py`, `tools/prd_review.py`, `tools/qa_agent.py`, `tools/index_sync.py`, `tools/status.py`, `AGENTS.md`, `templates/aidd/AGENTS.md`, `tests/test_reports_pack.py`, `tests/test_index_schema.py`: выровнять формат pack/index:
  - определить формат (JSON‑pack с явным расширением, либо реальный YAML);
  - backward‑compat не требуется (проект не в релизе, нет потребителей);
  - привести README/AGENTS к точному описанию формата.
  **AC:** pack/index читаются/пишутся единообразно; документы и тесты отражают формат.
  **Deps:** W86-1

- [x] W86-3 `tools/loop_pack.py`, `tools/loop_step.py`, `tools/loop_run.py`, `tools/review_pack.py`, `tools/context_pack.py`, `tools/rlm_jsonl_compact.py`, `tools/reports/events.py`, `tools/reports/tests_log.py`, `tests/test_loop_pack.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`, `tests/test_review_pack.py`: вынести общие утилиты (JSONL read/write, front‑matter parse, YAML dump, timestamp helpers) в общий модуль:
  - создать `tools/io_utils.py` (или аналог) и перенести дубли;
  - адаптировать импорты и тесты.
  **AC:** дублирующий код удалён; тесты не меняют поведение.
  **Deps:** -

- [x] W86-4 `tools/analyst_guard.py`, `tools/research_guard.py`, `tools/tasklist_check.py`, `tools/prd_review_gate.py`, `tools/plan_review_gate.py`, `tools/progress.py`, `tests/test_analyst_dialog.py`, `tests/test_gate_researcher.py`, `tests/test_tasklist_check.py`, `tests/test_gate_prd_review.py`, `tests/test_plan_review_gate.py`: централизовать gates‑config/branch‑filters:
  - общий helper (`tools/gates.py`) для загрузки `config/gates.json`, matches/skip, нормализации паттернов;
  - заменить локальные реализации в gate‑скриптах.
  **AC:** единая логика веток/skip во всех gate‑скриптах; тесты обновлены.
  **Deps:** W86-1

- [x] W86-5 `tools/runtime.py`, `tools/progress.py`, `tools/qa_agent.py`, `tests/test_progress.py`, `tests/test_qa_agent.py`: единая логика `detect_branch`:
  - оставить один источник truth в `tools/runtime.py`;
  - удалить локальные копии и обновить тесты.
  **AC:** нет дублирования branch‑detector; поведение неизменно.
  **Deps:** W86-1

- [x] W86-6 `tools/qa.py`, `templates/aidd/config/gates.json`, `templates/aidd/AGENTS.md`, `tests/test_gate_qa.py`: ограничить discovery тест‑команд:
  - добавить лимиты/флаги (max_files/max_bytes, allowlist путей) в `gates.json`;
  - обновить discovery logic в `tools/qa.py`;
  - задокументировать и покрыть тестами.
  **AC:** discovery не сканирует весь workspace без лимитов; поведение описано в templates и тестах.
  **Deps:** -

## Wave 87 — Parallel‑ready (без реального параллельного запуска)

_Статус: новый, приоритет 1. Цель — канон промптинга, устранение конфликтов loop/tasklist, машинные gate’ы, проверяемая test‑evidence и готовность артефактов/схем к параллели (per‑work‑item)._

### EPIC A — Канон промптинга + статусы + parallel conventions
- [x] **W87-1** `templates/aidd/docs/prompting/conventions.md`, `templates/aidd/AGENTS.md`, `AGENTS.md`: ввести единый канон промптов:
  - развести сущности: `artifact status` (READY/WARN/BLOCKED/…), `stage result` (blocked|continue|done), `review verdict` (SHIP|REVISE);
  - правила BLOCKED (missing artifacts, out-of-scope, missing test commands/evidence);
  - минимальный output‑контракт (lint‑поддающийся): `Status`, `Work item key`, `Artifacts updated`, `Tests (profile+evidence|profile:none)`, `Blockers/Handoff` при BLOCKED, `Checkbox updated` (optional, stage‑dependent);
  - нормализация ключей: `work_item_key` (логический) vs `scope_key` (sanitized для путей);
  - источник истины для loop‑gating: `stage_result` (остальное = evidence/контекст);
  - parallel‑ready naming conventions (per work_item_key): где лежат stage_result / review_pack / review_report / tests_evidence для implement/review, и что для ticket‑scoped стадий используется `scope_key=ticket` (или `work_item_key=ticket`).
  **AC:** единый документ канона; на него ссылаются `templates/aidd/AGENTS.md` и dev‑гайд; контракт пригоден для линта; описаны пути артефактов per‑work‑item и правила scope_key.
  **Deps:** -

- [x] **W87-2** `templates/aidd/docs/status-machine.md`, `templates/aidd/docs/loops/README.md`: расширить таксономию:
  - добавить `ReviewPack verdict: SHIP|REVISE`;
  - описать `stage result: blocked|continue|done`;
  - добавить mapping по стадиям:
    - implement: `READY → continue`, `BLOCKED → blocked`;
    - review: `SHIP → done`, `REVISE → continue`, `BLOCKED → blocked`;
    - qa (ticket‑scoped): выбрать policy `WARN → done|continue` и зафиксировать;
  - для loop‑mode: `PENDING → blocked` (вопросы = блокер);
  - описать scope: `work_item_scoped` (implement/review) vs `ticket_scoped` (qa).
  **AC:** статусы/вердикты описаны единообразно; термины не конфликтуют; scope описан и согласован с prompts.
  **Deps:** W87-1

### EPIC B — Loop pack vs tasklist/plan/prd/research/spec + mode-aware
- [x] **W87-3** `tools/loop_pack.py`, `templates/aidd/docs/loops/template.loop-pack.md`, `templates/aidd/docs/anchors/implement.md`, `templates/aidd/docs/anchors/review.md`, `agents/implementer.md`, `agents/reviewer.md`, `commands/implement.md`, `commands/review.md`:
  - устранить конфликт “читать/не читать tasklist/plan/prd/research/spec”:
    - заменить “Do not read full …” на “prefer excerpt; read full только если excerpt не содержит Goal/DoD/Boundaries/Expected paths/Size budget/Tests/Acceptance”;
    - закрепить правило чтения в anchors/agents/commands;
    - в loop pack excerpt гарантировать наличие: `work_item_key`, `expected_paths`, `size_budget` (max_files/max_loc), `tests` (или ссылка на TEST_EXECUTION), `allowed_paths`/`forbidden_paths` (если есть).
  **AC:** loop pack читается первым; полный tasklist/PRD/Plan/Research/Spec читается только при неполном excerpt; противоречий в инструкциях нет; excerpt достаточен для работы без “догадок”.
  **Deps:** W87-1

- [x] **W87-4** `tools/loop_run.py`, `tools/loop_step.py`, `agents/implementer.md`, `agents/reviewer.md`, `templates/aidd/docs/anchors/implement.md`, `templates/aidd/docs/anchors/review.md`, `commands/implement.md`, `commands/review.md`, `commands/qa.md`:
  - mode‑aware поведение:
    - если файл `.active_mode` существует и содержит `loop` — не задавать вопросы в чат; писать blocker/handoff + `Status: BLOCKED`;
    - `loop_run` очищает `.active_mode` (или возвращает `manual`) после остановки;
    - (parallel‑ready) не завязываться на “общие” ticket‑артефакты; использовать пути из context/loop pack.
  **AC:** loop‑run/loop‑step останавливаются на блокере без интерактива; `.active_mode` очищается при любом exit‑коде (включая BLOCKED); промпты не требуют ticket‑singleton артефактов.
  **Deps:** -

### EPIC C — Stage result + loop‑gating (per‑work‑item paths)
- [x] **W87-5** `tools/stage_result.py`, `tools/stage-result.sh`, `hooks/format-and-test.sh`, `commands/implement.md`, `commands/review.md`, `commands/qa.md`, `tools/loop_step.py`, `tools/loop_run.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`, `tests/repo_tools/loop-regression.sh`:
  - машинный результат стадии:
    - писать stage result per scope_key:
      `aidd/reports/loops/<ticket>/<scope_key>/stage.<stage>.result.json`
      где `scope_key=<work_item_key>` для implement/review, и `scope_key=ticket` для qa;
    - схема `aidd.stage_result.v1` и поля: `result` (blocked|continue|done), `reason`, `reason_code`, `ticket`, `stage`, `scope_key`, `work_item_key` (optional для ticket), `artifacts`, `evidence_links`, `updated_at`, `producer`;
    - порядок записи: `tests_log → stage_result` (если evidence обязательна);
    - команды implement/review/qa отвечают за запись результата (или hook‑writer, если выбран паттерн A);
    - `loop_step` после команды читает stage result:
      - если отсутствует/битый → `blocked` (`reason_code=stage_result_missing_or_invalid`);
      - `blocked` → завершает с BLOCKED_CODE;
      - `done` → DONE_CODE;
      - `continue` → CONTINUE_CODE;
    - `loop_run` пишет `reason/reason_code/scope_key` в `loop.run.log`.
  **AC:** loop‑gating опирается только на stage_result; loop‑run корректно останавливается на BLOCKED implement/review/qa и missing/invalid stage_result; stage_result содержит evidence_links при обязательных тестах и пишется после tests_log.
  **Deps:** W87-2

### EPIC D — Review pack как операционный вход (per‑work‑item)
- [x] **W87-6** `tools/review_pack.py`, `tools/review_report.py`, `tools/review-report.sh`, `commands/review.md`, `agents/reviewer.md`, `tools/loop_step.py`, `tools/loop_pack.py`, `templates/aidd/config/gates.json`, `tests/test_review_pack.py`, `tests/test_loop_step.py`:
  - усилить review pack:
    - review pack хранить per scope_key:
      `aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md`;
    - review report хранить per scope_key:
      `aidd/reports/reviewer/<ticket>/<scope_key>.json` (или `aidd/reports/loops/<ticket>/<scope_key>/review.report.json`);
    - добавить поля: `blocking_findings_count`, `handoff_ids_added`, `next_recommended_work_item`, `evidence_links`;
    - оформить новую схему `aidd.review_pack.v2` и fallback для v1 (warn по умолчанию, block при strict‑конфиге);
    - задокументировать место конфига и дефолт в `gates.json`;
    - `loop_step` не читает ticket‑singleton `review.latest.pack.md`; берёт verdict/decision либо из stage_result (`evidence_links`), либо из per‑work‑item review pack (по scope_key).
  **AC:** review pack/ report per‑work‑item; loop_step валидирует v2 (или warn для v1) по конфигу; freshness checks используют per‑work‑item report.
  **Deps:** W87-5

### EPIC E — Проверяемая test‑evidence + QA (per‑work‑item, merge‑friendly)
- [x] **W87-7** `hooks/format-and-test.sh`, `tools/reports/tests_log.py`, `commands/implement.md`, `commands/review.md`, `commands/qa.md`, `tools/qa_agent.py`, `tools/qa.py`, `tests/test_qa_agent.py`:
  - детерминированная test‑evidence:
    - hook пишет summary per scope_key:
      `aidd/reports/tests/<ticket>/<scope_key>.jsonl`
      где `scope_key=<work_item_key>` для implement/review, `scope_key=ticket` для qa/общих прогонов;
    - запись включает: `schema=aidd.tests_log.v1`, `ticket`, `stage`, `scope_key`, `work_item_key` (optional), `profile/tasks/filters`, `exit_code`, `log_path`, `updated_at`, `cwd/worktree` (optional);
    - определение ticket: `--ticket`/`.active_ticket` → fallback `slug_hint`/unknown с явной маркировкой (`ticket_guess`, `ticket=unknown`);
    - QA/Review используют последнюю запись по ticket+scope_key как evidence;
    - интеграция с W87-5: implement/review/qa при записи stage_result добавляют `evidence_links` на tests_log (если есть) и/или указывают `reason_code=missing_test_evidence`, если по политике evidence обязателен.
  **AC:** QA/Review не выставляют READY без подтверждённого test‑evidence (кроме profile:none), даже при fresh sessions; если review не запускает тесты — evidence берётся из последнего implement‑прогона по scope_key.
  **Deps:** W87-1, W87-5

### EPIC F — Дедуп промптов + versioning + lint (включая granularity/graph readiness)
- [x] **W87-8** `agents/*.md`, `commands/*.md`, `templates/aidd/AGENTS.md`, `tests/repo_tools/prompt-version`, `tests/repo_tools/lint-prompts.py`:
  - сократить дубли инструкций ссылкой на `docs/prompting/conventions.md`;
  - обновить `prompt_version/source_version`;
  - расширить lint‑prompts проверкой:
    - канон упомянут,
    - правило “loop без вопросов” присутствует,
    - (parallel‑ready) промпты используют per‑work‑item пути (или читают их из context pack), а не ticket‑singleton,
    - (granularity) tasklist‑refiner/anchor tasklist содержит policy по средней гранулярности итераций,
    - stage_result упомянут как обязательный артефакт loop‑gating.
  **AC:** prompts короче, нет рассинхрона, lint/prompts ловит пропуски канона/loop‑policy/parallel‑ready path conventions/granularity policy/stage_result.
  **Deps:** W87-1

### EPIC G — Runner compatibility (критично)
- [x] **W87-9** `tools/loop_step.py`, `tools/loop_run.py`, `templates/aidd/docs/loops/README.md`, `AGENTS.md`, `tests/test_loop_step.py`, `tests/repo_tools/loop-regression.sh`:
  - исправить дефолтный runner:
    - убрать `--no-session-persistence` из дефолта; добавить fallback/детект неподдерживаемого флага;
    - обновить docs по runner и переменным `AIDD_LOOP_RUNNER/--runner`;
    - в логах фиксировать “effective runner”.
  **AC:** loop‑step/loop‑run работают на актуальном Claude Code без ручного override; effective runner + persistence flag видны в логах.
  **Deps:** -

### EPIC H — Tasklist “graph‑ready” + granularity policy (без scheduler)
- [x] **W87-10** `templates/aidd/docs/tasklist/template.md`, `templates/aidd/docs/anchors/tasklist.md`, `agents/tasklist-refiner.md`, *(опц.)* `tools/tasklist-check.sh`:
  - подготовить tasklist к DAG‑модели (пока без реального scheduler):
    - для каждой итерации в `AIDD:ITERATIONS_FULL` добавить опциональные поля:
      - `deps: [<id1>, <id2>]` (по умолчанию пусто),
      - `locks: [<lock1>]` (по умолчанию пусто; для будущего запрета параллели);
      - `priority: <int>` (по умолчанию 100),
      - `blocking: <bool>` (по умолчанию false);
    - обновить tasklist‑refiner:
      - не дробить “в песок”: итерация должна быть в одном окне, но не микро‑задача;
      - эвристики (policy): Steps ~ 3–7, expected_paths 1–3 группы, size_budget по умолчанию (напр. max_files 3–8, max_loc 80–400) с возможностью override;
      - `AIDD:NEXT_3` должен выбирать задачи, у которых deps удовлетворены (deps ссылаются на iteration_id/id);
    - (опц.) `tasklist-check` добавляет WARN (не BLOCK по умолчанию) при явной “слишком мелкой/слишком крупной” итерации; BLOCK — только при strict‑gates (в будущем).
  **AC:** tasklist содержит deps/locks/priority/blocking (опционально) и policy по granularity; tasklist‑refiner не создаёт микро‑итерации; `NEXT_3` не предлагает узлы с незакрытыми deps; пустые expected_paths → WARN (или BLOCK в strict).
  **Deps:** W87-1

### BUGFIXES — Flow audit TST-001
- [x] **W87-11** `tools/stage_result.py`, `tools/stage-result.sh`, `commands/implement.md`, `commands/review.md`, `commands/qa.md`, `tools/loop_step.py`, `tools/loop_run.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`:
  - зафиксировать запись stage_result при manual implement/review/qa (включая BLOCKED/READY/SHIP/WARN);
  - не допускать отсутствия stage_result (fail-fast + понятный reason_code).
  **AC:** после каждой команды implement/review/qa существует `aidd/reports/loops/<ticket>/<scope_key>/stage.<stage>.result.json`; loop_run/loop_step не видят `stage_result_missing_or_invalid` при корректном завершении команды.
  **Deps:** W87-5

- [x] **W87-12** `tools/review_pack.py`, `tools/review_report.py`, `tools/review-pack.sh`, `tools/review-report.sh`, `commands/review.md`, `agents/reviewer.md`, `tests/test_review_pack.py`:
  - гарантировать генерацию per‑work‑item review pack и review report;
  - синхронизировать verdict → stage_result (evidence_links, REVISE→continue, SHIP→done).
  **AC:** появляется `aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md` и `aidd/reports/reviewer/<ticket>/<scope_key>.json` для каждого review; loop_step читает их per‑work‑item без fallback на ticket‑singleton; stage_result соответствует verdict.
  **Deps:** W87-6

- [x] **W87-13** `tools/diff_boundary_check.py`, `tools/diff-boundary-check.sh`, `tools/loop_pack.py`, `commands/implement.md`, `commands/review.md`, `tests/test_diff_boundary_check.py`:
  - ослабить boundary‑check: OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED → WARN (не BLOCKED), FORBIDDEN → BLOCKED;
  - расширить loop pack allowed_paths, когда требуется правка `db.changelog-master.yaml` для включения миграции.
  **AC:** изменения вне allowed_paths дают WARN (и фиксятся в handoff) как в implement, так и в review; NO_BOUNDARIES_DEFINED даёт WARN; FORBIDDEN продолжает блокировать; при миграции loop pack явно разрешает `backend/src/main/resources/db/changelog/db.changelog-master.yaml`.
  **Deps:** W87-3

- [ ] **W87-14** `tools/output_contract_check.py`, `tools/output-contract-check.sh`, `commands/implement.md`, `commands/review.md`, `commands/qa.md`, `tests/test_output_contract_check.py`:
  - DE-SCOPED: удалён линт output‑контракта; автоматическая проверка loop‑step не выполняется.
  **Deps:** W87-1

- [x] **W87-15** `tools/prd_review.py`, `tools/prd-review.sh`, `tools/prd_review_gate.py`, `tools/prd-review-gate.sh`, `tools/index_sync.py`, `tests/test_gate_prd_review.py`:
  - синхронизировать статус PRD‑review между doc/report/index;
  - убрать рассинхрон `Status: READY` в PRD при `reports/prd/*.json = pending`.
  **AC:** PRD review READY отражается в `aidd/reports/prd/<ticket>.json` и `aidd/docs/index/<ticket>.json` без pending.
  **Deps:** W87-1

- [x] **W87-16** `hooks/format-and-test.sh`, `tools/reports/tests_log.py`, `tools/qa_agent.py`, `tests/test_format_and_test.py`, `tests/test_qa_agent.py`:
  - исправить тест‑evidence, когда форматирование/тесты пропущены;
  - синхронизировать tests_log со статусом исполнения hook (profile:none при skip).
  **AC:** `aidd/reports/tests/<ticket>/<scope_key>.jsonl` отражает фактический запуск; при skip — profile:none + reason_code, QA не считает tests pass без evidence.
  **Deps:** W87-7

- [x] **W87-17** `agents/reviewer.md`, `commands/review.md`, `templates/aidd/docs/prompting/conventions.md`, `templates/aidd/docs/status-machine.md`, `tools/review_pack.py`, `tools/stage_result.py`, `tests/test_loop_step.py`, `tests/test_review_pack.py`:
  - политика review‑вердикта: дефекты в рамках итерации → `REVISE` (без BLOCKED), `Status: READY|WARN` по тяжести;
  - `BLOCKED` только для missing artifacts/evidence/commands или `FORBIDDEN` boundary fail; `OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED` → WARN + handoff;
  - stage_result для review: `REVISE → continue`, `SHIP → done`, `BLOCKED → blocked`.
  **AC:** review не блокирует из‑за исправимых дефектов или OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED; loop продолжает итерации при REVISE; BLOCKED используется только для системных стоп‑условий и `FORBIDDEN`.
  **Deps:** W87-1, W87-5, W87-6

- [x] **W87-18** `templates/aidd/docs/prompting/conventions.md`, `templates/aidd/docs/status-machine.md`, `templates/aidd/docs/loops/README.md`, `templates/aidd/AGENTS.md`, `templates/aidd/docs/anchors/implement.md`, `templates/aidd/docs/anchors/review.md`, `AGENTS.md`:
  - синхронизировать канон с мягким out‑of‑scope: `OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED → WARN + handoff`, `FORBIDDEN → BLOCKED`;
  - в каноне явно указать “review не блокирует за исправимые дефекты, а ставит REVISE”.
  **AC:** канон и anchors/loops README не противоречат политике “loop продолжается при REVISE/OUT_OF_SCOPE”.
  **Deps:** W87-1, W87-17

- [x] **W87-19** `tools/stage_result.py`, `tools/loop_step.py`, `tools/loop_run.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`:
  - зафиксировать, что OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED дают `result=continue` с `reason_code=out_of_scope_warn|no_boundaries_defined_warn` (не BLOCKED);
  - loop‑gating считает WARN допустимым для продолжения.
  **AC:** loop продолжает работу при OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED WARN; блокировка остаётся только для FORBIDDEN или системных стоп‑условий.
  **Deps:** W87-11, W87-13, W87-17

- [x] **W87-20** `agents/reviewer.md`, `commands/review.md`, `tools/review_pack.py`, `tests/test_review_pack.py`:
  - review diff‑first: анализирует только изменения итерации; новые требования/работы → handoff в tasklist, не BLOCKED;
  - гарантировать запись handoff для исправимых дефектов (review findings) вместо остановки loop.
  **AC:** review всегда выдаёт handoff для найденных дефектов; loop не останавливается из‑за исправимых замечаний в diff.
  **Deps:** W87-17

- [x] **W87-21** `hooks/format-and-test.sh`, `tools/reports/tests_log.py`, `tools/stage_result.py`, `tools/qa_agent.py`, `templates/aidd/config/gates.json`, `tests/test_format_and_test.py`, `tests/test_qa_agent.py`:
  - мягкий режим отсутствия test‑evidence: по конфигу (например `tests_required=soft`) → WARN + handoff “run tests”, без BLOCKED;
  - для review в soft‑policy: verdict `REVISE` (continue) при missing evidence, чтобы loop продолжился до фикса;
  - строгий режим сохраняет BLOCKED (для `tests_required=hard`).
  **AC:** loop не блокируется на пропущенных тестах при soft‑policy; review выставляет REVISE при missing evidence; BLOCKED остаётся в strict‑policy.
  **Deps:** W87-7, W87-11, W87-17

- [x] **W87-22** `commands/implement.md`, `commands/review.md`, `commands/qa.md`:
  - убрать устаревшие указания “OUT_OF_SCOPE → BLOCKED”; заменить на WARN + handoff, `FORBIDDEN → BLOCKED`, `NO_BOUNDARIES_DEFINED → WARN`;
  - в review‑команде закрепить: дефекты → REVISE (continue), BLOCKED только при missing artifacts/evidence/commands или FORBIDDEN;
  - добавить явное правило diff‑first (review проверяет только изменения итерации) и “loop continues until fixed”.
  **AC:** командные доки соответствуют мягкому out‑of‑scope и ревью‑политике, не противоречат W87-17/19/21.
  **Deps:** W87-17, W87-19, W87-21

- [x] **W87-23** `agents/implementer.md`, `agents/reviewer.md`, `agents/tasklist-refiner.md`:
  - удалить устаревшие формулировки про “остановку” на out‑of‑scope;
  - добавить правило: OUT_OF_SCOPE/NO_BOUNDARIES_DEFINED → WARN + handoff, FORBIDDEN → BLOCKED;
  - добавить WARN в допустимые статусы implementer/reviewer;
  - в reviewer‑агенте закрепить REVISE для исправимых дефектов и diff‑first review.
  **AC:** агент‑промпты согласованы с мягким out‑of‑scope и “loop until fixed”.
  **Deps:** W87-17, W87-19


## Wave 88

### Loop Protocol (REVISE в рамках одного work_item)

- [x] **W88-1** `tools/loop-run.sh`, `tools/loop-step.sh`, `tools/loop-pack.sh`, `commands/implement.md`, `commands/review.md`, `templates/aidd/docs/loops/README.md`, `templates/aidd/docs/prompting/conventions.md`, `tests/repo_tools/*`:
  - Зафиксировать REVISE-loop:
    - на `verdict=REVISE` записывать `aidd/reports/loops/<ticket>/<scope_key>/stage.review.result.json` с `result=continue`;
    - `loop-run/step` при `continue` повторно запускает `/feature-dev-aidd:implement` по тому же `scope_key` (без смены work_item).
  - Гарантировать повтор implement по тому же work_item:
    - при REVISE implement ДОЛЖЕН использовать тот же `work_item_key` из `.active_work_item` (или эквивалентный override),
      а `loop-pack.sh` НЕ должен выбирать новый work_item.
    - допустимые реализации: reuse `.active_work_item`, явный параметр (`--work-item-key/--scope-key`) или ENV‑флаг.
  - Гарантировать, что при `REVISE`:
    - чекбокс в `AIDD:ITERATIONS_FULL` остаётся `[ ]` (не закрывается);
    - `AIDD:NEXT_3` НЕ меняется (ни состав, ни порядок);
    - `.active_work_item` НЕ меняется;
    - `scope_key` НЕ меняется.
  - Документация: явно описать “REVISE не двигает work_item, повторяет implement”.
  - Добавить интеграционный тест на семантику (минимум 2 кейса):
    - Case A: review=REVISE → повтор implement на том же scope_key, чекбокс не закрыт, NEXT_3 не меняется.
    - Case B: review=SHIP   → чекбокс закрыт, NEXT_3 сдвинут, loop-run переходит дальше.
    - Эти тесты на уровне workflow/команд; скриптовый уровень покрывается W88-14.
  **AC:**
  - При `REVISE` повтор запуска implement идёт по тому же `scope_key`, без смены work_item.
  - При `SHIP` чекбокс закрывается `[x]` и `AIDD:NEXT_3` корректно сдвигается.
  - Тесты подтверждают, что `REVISE` не меняет `AIDD:NEXT_3` и чекбоксы.
  **Deps:** W88-2

- [x] **W88-2** `tools/review-pack.sh`, `agents/reviewer.md`, `agents/implementer.md`, `templates/aidd/docs/loops/README.md`:
  - Добавить структурированный **Fix Plan** в `aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md`:
    - Fix Plan должен быть исполнимым и детерминированным (без “починить как-нибудь”).
    - Рекомендуемый формат:
      - `steps:` (нумерованные, краткие)
      - `commands:` (что запускать)
      - `tests:` (профиль + команды/фильтры или ссылка на `AIDD:TEST_EXECUTION`)
      - `expected_paths:` (для diff-boundary и loop-pack boundaries)
      - `acceptance_check:` (что считать “исправлено”)
      - `links:` (на findings/строки/отчёты)
  - Implementer обязан:
    - читать `loop pack → review pack → Fix Plan` (в таком порядке);
    - явно выполнять Fix Plan;
    - в отчёте ссылаться на Fix Plan (например: “выполнены шаги 1,2; шаг 3 не нужен потому что …”).
  - Reviewer обязан:
    - при `verdict=REVISE` всегда включать Fix Plan;
    - делать Fix Plan согласованным с `findings` (каждый blocking finding должен отражаться в плане).
  **AC:**
  - Fix Plan присутствует для всех `verdict=REVISE`.
  - Implementer в отчёте явно ссылается на Fix Plan (минимум: какие шаги выполнены).
  **Deps:** -

### Evidence & Gates

- [x] **W88-3** `hooks/gate-workflow.sh`, `tools/stage-result.sh` (если используется), `commands/implement.md`, `commands/review.md`, `commands/qa.md`, `tools/*`:
  - Гарантировать запись stage_result при раннем выходе/ошибке (fail-fast) для implement/review/qa:
    - `aidd/reports/loops/<ticket>/<scope_key>/stage.implement.result.json`
    - `aidd/reports/loops/<ticket>/<scope_key>/stage.review.result.json`
    - `aidd/reports/loops/<ticket>/<ticket>/stage.qa.result.json` (ticket-scoped, если так задумано)
  - Даже при BLOCKED до запуска агента/хуков stage_result должен создаваться с минимум-полями:
    - `ticket`, `scope_key`, `work_item_key`, `stage`, `result`, `reason_code`, `errors[]` (если есть), `evidence_links{}` (может быть пустым).
    - для stage=review: дополнительно `verdict=SHIP|REVISE|BLOCKED`.
  - Для QA: stage_result ticket-scoped, `scope_key=<ticket>` — зафиксировать в docs и коде.
  - Обновить команды так, чтобы `stage-result.sh` вызывался всегда (в т.ч. при ошибке через trap/обработчик).
  **AC:**
  - stage_result всегда создаётся для implement/review/qa (включая fail-fast/early BLOCKED).
  - gate-workflow не видит “missing stage_result” ни в одном сценарии.
  **Deps:** -

- [x] **W88-4** `hooks/format-and-test.sh`, `hooks/gate-tests.sh`, `tools/loop-run.sh`, `tools/stage-result.sh`, `templates/aidd/docs/loops/README.md`:
  - При пропуске тестов **всегда** писать `aidd/reports/tests/<ticket>/<scope_key>.jsonl`:
    - добавить JSONL запись со `status="skipped"` и полями `reason_code` + `reason`.
    - рекомендованные `reason_code` (минимум):
      - `profile_none`
      - `skip_auto_tests`
      - `format_only`
      - `cadence_checkpoint_not_reached`
      - `no_diff_change_dedup`
      - `manual_skip`
    - `status=skipped` обязателен и при дедупе, cadence/early-exit и ручном skip.
  - `stage_result` должен ссылаться на test-log (evidence_links):
    - `evidence_links.tests_log="aidd/reports/tests/<ticket>/<scope_key>.jsonl"`
    - (опционально) `evidence_links.format_log="aidd/reports/tests/<ticket>/<scope_key>.format.jsonl"` если есть
  - `gate-tests.sh` должен считать “skipped с причиной” как evidence (и не поднимать `missing_test_evidence`).
  **AC:**
  - `missing_test_evidence` больше не возникает при пропуске тестов — вместо этого есть `status=skipped` + причина.
  - stage_result содержит ссылку на tests jsonl.
  **Deps:** W88-3

- [x] **W88-5** `hooks/gate-tests.sh`, `templates/aidd/docs/loops/README.md`, `templates/aidd/docs/prompting/conventions.md`, `tests/repo_tools/*`:
  - Учесть `tests_required=soft|hard` (из `gates.json`):
    - `soft`: отсутствие/skip тестов → НЕ BLOCKED, но должно приводить к `WARN/REVISE` (в зависимости от стадии) + reason_code
    - `hard`: отсутствие/skip тестов → `BLOCKED`
  - Для tests_required=soft при missing/skipped tests:
    - implement → Status: WARN (not BLOCKED)
    - review → verdict=REVISE (not BLOCKED)
    - qa → Status: WARN (not BLOCKED)
  - Явно задокументировать политику:
    - как определяется `tests_required`
    - как это отражается в `stage_result.result` и в CLI статусах
  - Добавить unit/integration тесты на матрицу:
    - soft + skipped → warn/revise (not blocked)
    - hard + skipped → blocked
  **AC:**
  - Политика тестов в loop-mode строго соответствует `gates.json` и тестами подтверждена.
  **Deps:** W88-4

### Pack/QA Consistency

- [x] **W88-6** `tools/review-pack.sh`, `tools/review-report.sh` (если есть), `agents/reviewer.md`, `templates/aidd/docs/loops/README.md`:
  - Синхронизировать `review.latest.pack.md` с `aidd/reports/reviewer/<ticket>/<scope_key>.json`:
    - pack должен генерироваться из JSON отчёта (или наоборот) одним источником истины.
  - Поля должны совпадать:
    - `blocking_findings_count`
    - список `findings` (id/summary/severity/blocking/scope/links)
  - Fix Plan (W88-2) должен ссылаться на конкретные findings (например: `fixes: [finding_id=R-3, R-7]`).
  **AC:**
  - pack и report совпадают по findings/severity/blocking_findings_count (байт-в-байт по смыслу).
  **Deps:** W88-2

- [x] **W88-7** `tools/qa.sh`, `commands/qa.md`, `tools/stage-result.sh`, `templates/aidd/docs/loops/README.md`, `tests/repo_tools/*`:
  - Согласовать статусы и пути:
    - `aidd/reports/qa/<ticket>.json`
    - `aidd/reports/qa/<ticket>.pack.json` (если используется)
    - `aidd/reports/loops/<ticket>/<ticket>/stage.qa.result.json`
    - CLI-вывод должен ссылаться на фактические пути.
  - Зафиксировать, что QA stage_result ticket-scoped и `scope_key=<ticket>`, и отражено в docs/CLI.
  - Запретить невозможное состояние:
    - нельзя получить READY pack при BLOCKED stage_result (или BLOCKED CLI).
  - Явно описать mapping статусов QA:
    - какие значения считаются `done` vs `blocked`
    - как soft missing evidence влияет (`WARN` + handoff vs `BLOCKED`)
  - Добавить тесты на консистентность статусов (минимум 2 кейса).
  **AC:**
  - Нельзя получить READY pack при BLOCKED stage_result/CLI.
  - Пути в выводе команд всегда совпадают с реально созданными файлами.
  **Deps:** W88-3, W88-4, W88-5

### Logging & Lint

- [x] **W88-8** `tools/loop-run.sh`, `tools/loop-step.sh`, `tools/stage-result.sh`, `templates/aidd/docs/loops/README.md`:
  - Писать логи CLI:
    - `aidd/reports/loops/<ticket>/cli.loop-run.<ts>.log`
    - `aidd/reports/loops/<ticket>/cli.loop-step.<ts>.log`
  - Заполнять `runner=` в `loop.run.log`:
    - кто/что запустил (например: `runner=claude_cli`, `runner=ci`, `runner=local`)
    - фиксировать `ticket`, `scope_key`, `stage`, `exit_code`, `result`
  - Обновить docs: где искать логи при разборе инцидента.
  **AC:**
  - Каждый loop-запуск имеет cli-лог и заполненный `runner`.
  **Deps:** -

- [x] **W88-9** `tools/tasklist-check.sh`, `tools/tasklist-normalize.sh`, `tests/`, `templates/aidd/docs/tasklist/template.md`:
  - Исправить “no such group” и дубли секций (root cause + авто-fix).
  - Добавить unit-тесты:
    - на template (валиден из коробки)
    - на normalize `--fix` (устраняет дубли/ошибки)
    - на check (стабилен)
  - Добавить тест на “NEXT_3 не содержит [x]”.
  **AC:**
  - tasklist-check стабильно проходит на template.
  - normalize --fix приводит tasklist к валидному состоянию в типовых кейсах.
  **Deps:** -

### Prompting & Output Contract

- [x] **W88-10** `agents/implementer.md`, `agents/reviewer.md`, `agents/qa.md`, `templates/aidd/docs/loops/README.md`, `templates/aidd/docs/prompting/conventions.md`:
  - Enforce “excerpt-first” (и “pack-first”) как проверяемое правило:
    - Implementer/Reviewer/QA должны начинать с: `loop pack → (review pack, если есть) → excerpt`.
    - Запрет на чтение full PRD/Research/Plan/Tasklist целиком, если excerpt достаточно.
  - Добавить обязательное поле в ответ агента (в рамках output contract):
    - `Context read:` список источников (только имена/пути packs/excerpts), без простыней.
  - Обновить docs: когда допустимо читать full-doc (например, missing DoD/Boundaries/Tests в excerpt).
  **AC:**
  - Транскрипты/ответы агентов содержат `Context read:` и демонстрируют pack/excerpt-first.
  **Deps:** -

- [x] **W88-11** `templates/aidd/docs/prompting/conventions.md`, `commands/*.md`, `agents/*.md`, `tests/repo_tools/lint-prompts.py`:
  - Сделать обязательными поля output-контракта для subagents implement/review/qa:
    - `Status`
    - `Work item key`
    - `Artifacts updated`
    - `Tests` (run/skipped/not-required + кратко)
    - `Blockers/Handoff`
    - `Next actions`
    - `Context read` (из W88-10)
  - Для команд:
    - обязательное ядро без `Context read` (команда может проксировать его из subagent, но это не обязательно).
  - Уточнить допустимые значения:
    - implementer: `READY|WARN|BLOCKED|PENDING`
    - reviewer/qa: `READY|WARN|BLOCKED`
  - Расширить lint-prompts.py (или добавить новый repo_tools тест), чтобы он проверял:
    - наличие этих полей в промптах subagents
    - для команд — наличие ядра, без требования `Context read`
    - отсутствие запрещённых полей/значений
  **AC:**
  - Output-контракт соблюдён для implement/review/qa.
  - Тесты/линтер валят PR при регрессе контракта.
  **Deps:** W88-10

### Versioning & Validation

- [x] **W88-12** `templates/aidd/**`, `tests/repo_tools/*`, `commands/aidd-init.md`:
  - bump `prompt_version` (единым коммитом, согласованно).
  - прогнать `tests/repo_tools/prompt-version` и `tests/repo_tools/lint-prompts.py`.
  - проверить `/feature-dev-aidd:aidd-init` и `tests/repo_tools/smoke-workflow.sh` на чистом workspace/ветке.
  **AC:**
  - smoke проходит на чистом workspace.
  - prompt-version и lint-prompts зелёные.
  **Deps:** W88-1..W88-11

- [x] **W88-15** `tools/loop-step.py`, `tools/loop-run.sh`, `templates/aidd/docs/loops/README.md`, `tests/repo_tools/*`:
  - Исправить runner для loop-step/run: запускать implement/review как `-p "/feature-dev-aidd:<cmd> <ticket>"`.
  - Убрать/нормализовать `-p` из runner override (если передан), логировать notice.
  - Обновить docs и smoke/loop тесты (если есть) под новый формат.
  **AC:**
  - `loop-step` и `loop-run` всегда вызывают `claude -p "/feature-dev-aidd:<cmd> <ticket>"` (или эквивалент runner override).
  - Нет ошибки `Unknown skill: feature-dev-aidd:implement` в loop-run.
  **Deps:** -

- [x] **W88-16** `commands/review.md`, `tools/loop-pack.sh`, `tools/loop-step.py`, `agents/reviewer.md`, `tests/repo_tools/*`:
  - Защититься от рассинхрона work_item в review: review должен использовать текущий `.active_work_item`/loop-pack scope_key.
  - При mismatch (`active_work_item` vs review target) → BLOCKED с явным reason_code.
  - Добавить тест на “review not matching last implement work_item”.
  **AC:**
  - Review не может перейти на другой work_item без явного handoff/смены.
  **Deps:** W88-1

- [x] **W88-17** `hooks/format-and-test.sh`, `tools/reports/tests_log.py`, `tools/qa_agent.py`, `tools/stage_result.py`, `tests/repo_tools/*`:
  - Исправить QA tests evidence: если тесты пропущены, tests_log пишет `status=skipped` + reason_code, а не `pass`.
  - Синхронизировать `aidd/reports/qa/<ticket>-tests.log` и `aidd/reports/tests/<ticket>/<scope_key>.jsonl`.
  **AC:**
  - Нельзя получить `status=pass` при “форматирование/тесты пропущены”.
  **Deps:** W88-4, W88-5

- [x] **W88-18** `tools/qa_agent.py`, `tests/test_qa_agent.py`, `templates/aidd/docs/anchors/qa.md`:
  - Исправить ложный QA блокер для незакрытых задач вне `AIDD:CHECKLIST_QA`:
    - Проверять чеклист ТОЛЬКО внутри секции `AIDD:CHECKLIST_QA` (или QA‑подсекции AIDD:CHECKLIST).
    - Учитывать `(Blocking: true|false)` у QA‑handoff задач, не делать их BLOCKED по умолчанию.
  - Добавить тесты:
    - незакрытая строка с `id: qa:*` вне `AIDD:CHECKLIST_QA` не должна становиться blocker.
    - незакрытая строка внутри `AIDD:CHECKLIST_QA` остаётся blocker.
  - Обновить anchor/доки (если нужно) про область проверки чеклиста QA.
  **AC:**
  - QA не блокирует из‑за QA‑handoff задач (кроме чеклиста QA).
  - BLOCKED остаётся только при незакрытых пунктах `AIDD:CHECKLIST_QA` или критических findings.
  **Deps:** W88-7, W88-17

- [x] **W88-19** `tools/loop-run.sh`, `tools/loop-step.sh`, `tools/loop_step.py`, `tools/loop_pack.py`, `commands/qa.md`:
  - Добавить явный режим “repair from QA”:
    - флаги `--from-qa` (alias `--repair-from-qa`) для loop-run/loop-step;
    - разрешать только если `.active_stage=qa` и `stage.qa.result.json` = `blocked`;
    - без флага поведение не менять (QA blocked → STOP).
  - Auto‑repair (opt‑in):
    - config: `aidd/config/gates.json` → `loop.auto_repair_from_qa=true`;
    - включать только при единственном blocking handoff кандидате.
  - Явный выбор work_item:
    - `--work-item-key <id>` приоритетен;
    - `--select-qa-handoff` — авто‑выбор из `AIDD:HANDOFF_INBOX` (только `handoff:qa`, `Blocking: true`, `scope: iteration_id=...`);
    - если 0 или >1 кандидата → BLOCKED + список кандидатов.
  - Логи/артефакты:
    - loop.run.log: `reason_code=qa_repair`, `chosen_scope_key=<id>`;
    - `aidd/reports/events/<ticket>.jsonl` (если есть) → запись `qa_repair_requested`;
    - `.active_stage` → implement, `.active_work_item` → выбранный id (без изменения `stage.qa.result`).
  **AC:**
  - QA blocked не запускает loop без `--from-qa`.
  - `--from-qa --work-item-key` переводит в implement и запускает loop на этом scope_key.
  - `--from-qa --select-qa-handoff` работает только при единственном Blocking handoff.
  **Deps:** W88-1, W88-3, W88-7

- [x] **W88-20** `templates/aidd/docs/loops/README.md`, `templates/aidd/docs/anchors/qa.md`, `tests/test_loop_step.py`, `tests/repo_tools/*`:
  - Документация режима “repair from QA”:
    - когда допустим, как выбрать work_item, примеры CLI.
  - Тесты:
    - QA blocked + no flag → STOP;
    - `--from-qa --work-item-key` → stage=implement, scope_key=given;
    - `--from-qa --select-qa-handoff` → BLOCKED при 0/2+ кандидатов, OK при 1 кандидате.
  **AC:**
  - Документы описывают флоу и ограничения.
  - Тесты покрывают все ветки выбора work_item.
  **Deps:** W88-19

- [x] **W88-21** `tools/review_report.py`, `tools/review_pack.py`, `commands/review.md`, `templates/aidd/docs/loops/README.md`, `tests/test_review_report.py`, `tests/test_review_pack.py`:
  - Сделать review-report идемпотентным:
    - не обновлять `updated_at`, если payload не изменился;
    - сохранять `generated_at` при повторных запусках.
  - Авто‑синхронизация review pack:
    - если loop‑pack и `.active_work_item` доступны и совпадают с `work_item_key`;
    - пересобирать pack при изменении отчёта или при отсутствии pack.
  - В review pack добавлять `review_report_updated_at` (для диагностики stale).
  - Обновить доки/контракт review (порядок: report → pack, что делать при stale).
  **AC:**
  - Повторный `review-report` с тем же payload не меняет `updated_at`.
  - При изменении review‑report, review pack пересобирается и не считается stale.
  - Pack содержит `review_report_updated_at` и его значение ≥ report.updated_at.
  **Deps:** W88-6, W88-16

- [x] **W88-22** `tools/loop-pack.sh`, `tools/loop_pack.py`, `tools/tasklist_parser.py`, `templates/aidd/docs/loops/README.md`, `tests/repo_tools/*`:
  - Исправить перенос boundaries/expected paths/tests/acceptance из tasklist в loop pack:
    - `allowed_paths` должен заполняться из `Boundaries` текущей итерации (если они есть).
    - `expected_paths`, `tests_required`, `acceptance` должны попадать в excerpt loop pack.
  - Если boundaries отсутствуют в tasklist:
    - loop pack фиксирует `reason_code=no_boundaries_defined_warn`,
    - implement/review обязаны подсказать заполнить boundaries (handoff), но не подменяют их.
  - Добавить тест: tasklist с boundaries → loop pack содержит `allowed_paths` и expected paths.
  **AC:**
  - `allowed_paths` в loop pack не пустой, если boundaries определены в tasklist.
  - Excerpt содержит Expected paths / Tests / Acceptance из tasklist.
  **Deps:** W88-1

- [x] **W88-23** `tools/review_pack.py`, `tools/stage_result.py`, `commands/review.md`, `agents/reviewer.md`, `tests/test_review_pack.py`:
  - Убрать рассинхрон verdict/status между CLI, stage_result и review pack:
    - CLI‑вывод должен брать verdict/status из stage_result или review report (single source of truth).
    - Запретить SHIP в CLI, если stage_result=continue/REVISE.
  - Добавить тест на расхождение: pack=REVISE → CLI тоже REVISE.
  **AC:**
  - CLI/pack/stage_result согласованы по verdict/status.
  **Deps:** W88-6, W88-7

- [x] **W88-24** `tools/loop-run.sh`, `tools/loop-step.sh`, `tools/stage_result.py`, `tests/repo_tools/*`:
  - Нормализовать `scope_key`/`work_item_key`:
    - запретить составные ключи вида `iteration_id=I1,I2,I3`;
    - stage_result создаётся только для реально выполненного шага (если шага нет в loop.run.log → нет stage_result).
  - Добавить тест: loop-run пишет ровно один stage_result на итерацию/стадию.
  **AC:**
  - Нет composite scope_key.
  - Количество stage_result соответствует количеству фактических запусков в loop.run.log.
  **Deps:** W88-1, W88-3

- [x] **W88-25** `tools/context-pack.sh`, `commands/review.md`, `agents/reviewer.md`, `templates/aidd/docs/loops/README.md`:
  - Гарантировать наличие review context pack перед запуском review subagent:
    - создаётся `aidd/reports/context/<ticket>.review.pack.md` или review получает BLOCKED с reason_code.
  - Добавить тест: отсутствие review pack → BLOCKED + stage_result.
  **AC:**
  - Review pack не пропадает и всегда доступен reviewer‑агенту.
  **Deps:** W88-3

- [x] **W88-26** `tools/qa_agent.py`, `tools/qa.sh`, `tools/stage_result.py`, `tests/test_qa_agent.py`:
  - Исправить расхождение QA статусов:
    - `aidd/reports/qa/<ticket>.json` должен совпадать со stage_result и CLI‑статусом.
    - non‑blocking handoff → WARN, не BLOCKED.
  - Добавить тест: QA WARN в CLI → status WARN в отчёте.
  **AC:**
  - QA статус согласован между CLI, stage_result и отчётом.
  **Deps:** W88-7, W88-18

- [x] **W88-27** `tools/researcher.py`, `commands/researcher.md`, `templates/aidd/docs/research/template.md`:
  - Синхронизация overrides в research:
    - после AIDD:ANSWERS/PRD overrides researcher должен отражать итоговые решения (timezone/cost/test‑filtering).
    - запретить устаревшие “resolved” блоки с противоположными решениями.
  - Добавить тест/линт: research содержит значения, соответствующие PRD overrides.
  **AC:**
  - Research и PRD не расходятся по финальным решениям.
  **Deps:** W88-1

## Wave 88.5 — Доп. задачи для “железобетонного” REVISE (NEW)

- [x] **W88-13** `tools/review-pack.sh`, `tools/review-report.sh` (если есть), `tools/loop-step.sh`, `agents/implementer.md`, `templates/aidd/docs/loops/README.md`:
  - Сделать Fix Plan машинно-читаемым (помимо markdown):
    - писать файл `aidd/reports/loops/<ticket>/<scope_key>/review.fix_plan.json`
    - stage_result (review) должен иметь `evidence_links.fix_plan_json=...`
  - Implementer:
    - читает markdown pack, но при наличии `fix_plan.json` использует его как source-of-truth (чтобы не было “вольной трактовки”).
  **AC:**
  - Для REVISE всегда есть `review.fix_plan.json`.
  - В stage_result есть ссылка на fix_plan_json.
  **Deps:** W88-2, W88-6, W88-3

- [x] **W88-14** `tests/repo_tools/*`, `tools/loop-run.sh`, `tools/loop-step.sh`:
  - Добавить интеграционные тесты “loop semantics” на уровне скриптов:
    - REVISE: не меняет NEXT_3/checkbox, повторяет implement на том же scope_key.
    - SHIP: закрывает checkbox, сдвигает NEXT_3.
    - (опционально) BLOCKED: stage_result создаётся, loop-run останавливается.
  **AC:**
  - Регресс семантики REVISE/SHIP ловится тестами.
  **Deps:** W88-1, W88-3

## Wave 89 — Doc consolidation (conventions + architecture + anchors + ast-grep + backlog archive) + Static context + Prompt examples

_Статус: план. Цель — сократить дубли документации, убрать устаревшие файлы, оставить один канон, и добавить “project memory” (CLAUDE.md) + few-shot примеры ответов._

- [ ] **W89-1** `templates/aidd/docs/prompting/conventions.md`, `templates/aidd/conventions.md`, `templates/aidd/AGENTS.md`, `AGENTS.md`, `README.md`, `README.en.md`, `commands/*.md`, `agents/*.md`:
  - перенести все уникальные правила из `templates/aidd/conventions.md` в `templates/aidd/docs/prompting/conventions.md`;
  - полностью удалить `templates/aidd/conventions.md`;
  - обновить все ссылки на канон в командах/агентах/README/AGENTS.
  **AC:** единственный источник конвенций — `templates/aidd/docs/prompting/conventions.md`; в репо нет ссылок на `templates/aidd/conventions.md`.
  **Deps:** -

- [ ] **W89-2** `templates/aidd/docs/architecture/README.md`, `templates/aidd/docs/architecture/profile.md`, `templates/aidd/docs/architecture/customize.md`, `commands/*.md`, `agents/*.md`, `templates/aidd/docs/anchors/*.md`, `README.md`, `README.en.md`:
  - объединить полезные материалы из `customize.md` в `README.md`;
  - оставить `profile.md` как шаблон артефакта (без методических дублей);
  - удалить `templates/aidd/docs/architecture/customize.md`;
  - обновить ссылки на архитектурные документы.
  **AC:** архитектурные документы сведены к двум файлам (`README.md` + `profile.md`); ссылки обновлены; удалённый файл нигде не упоминается.
  **Deps:** W89-1

- [ ] **W89-3** `templates/aidd/docs/anchors/README.md`, `templates/aidd/docs/anchors/*.md`:
  - вынести общий блок “base rules” в `anchors/README.md` (приоритет источников, контекст, общие ограничения);
  - в stage-anchor файлах оставить только stage‑специфику и ссылку на base rules;
  - проверить согласованность с loop/qa/plan policy.
  **AC:** повторяющиеся блоки удалены; anchors ссылаются на base rules; stage‑специфика сохранена.
  **Deps:** W89-1, W89-2

- [ ] **W89-4** `templates/aidd/ast-grep/README.md`, `templates/aidd/ast-grep/rules/*/README.md`:
  - добавить единый `templates/aidd/ast-grep/README.md` с пометкой legacy/disabled и инструкцией включения;
  - удалить per‑rule README или заменить их на короткие stubs с ссылкой на общий README;
  - обновить ссылки (если есть) на старые readme.
  **AC:** есть один канонический README; нет лишних дублирующих README внутри `rules/*`.
  **Deps:** -

- [ ] **W89-5** `backlog.md`:
  - создать секцию “Archive / Legacy”;
  - перенести туда все закрытые/исторические пункты с удалёнными командами/агентами (без влияния на активные волны);
  - добавить заметку, что архив содержит устаревшие ссылки.
  **AC:** активные волны не содержат ссылок на удалённые файлы; архив явно помечен как legacy.
  **Deps:** W89-1, W89-2, W89-4

- [ ] **W89-6** `README.md`, `README.en.md`, `AGENTS.md`, `templates/aidd/AGENTS.md`, `templates/aidd/docs/**/README.md`, `templates/aidd/ast-grep/**/README.md`:
  - корневой `README.md`/`README.en.md` оставить для human‑доки (инсталляция, quick‑start, high‑level);
  - runtime README (в `templates/aidd/**`) привести к agent‑правилам: краткие инструкции, порядок чтения, artefacts, do/don’t, fail‑fast;
  - перенести runtime‑critical правила из root README в `AGENTS.md`/`templates/aidd/AGENTS.md` и/или соответствующие runtime README;
  - добавить явные ссылки “agent rules → AGENTS/anchors/loops” в root README.
  **AC:** root README не содержит agent‑policy; runtime README оформлены как agent‑rules; агент получает инструкции без чтения root README.
  **Deps:** W89-1, W89-2, W89-3, W89-4

- [ ] **W89-7** `tools/init.sh`, `commands/aidd-init.md`, `templates/aidd/**`, `AGENTS.md`, `templates/aidd/AGENTS.md`, `tests/repo_tools/*`:
  - Добавить “static project memory” через `CLAUDE.md` в корне workspace:
    - если `CLAUDE.md` отсутствует → создать из шаблона (рекомендовано добавить `templates/aidd/CLAUDE.md`);
    - если `CLAUDE.md` существует → идемпотентно вставить/обновить секцию `## AIDD` (рекомендовано через маркеры):
      - `<!-- AIDD:BEGIN -->`
      - `<!-- AIDD:END -->`
      - внутри — только управляемый init-контент.
    - если workspace read-only/не writable — вывести предупреждение и не падать.
  - Содержимое `## AIDD` (10–30 строк, без простыней):
    - порядок чтения: anchors-first → pack-first → excerpt-first;
    - канон: `aidd/docs/prompting/conventions.md`, `aidd/docs/anchors/README.md`, `aidd/docs/loops/README.md`;
    - запрет “читать всё подряд”; работать по pack/artefacts;
    - коротко про loop-mode: REVISE не двигает work_item, выполнять Fix Plan из review pack.
  - Обновить `commands/aidd-init.md`, чтобы явно описывалось создание/обновление `CLAUDE.md`.
  - Добавить repo_tools тест:
    - на чистом workspace init создаёт `CLAUDE.md`;
    - повторный init НЕ ломает пользовательский текст вне маркеров.
  **AC:**
  - После `aidd-init` на чистом workspace есть `CLAUDE.md` с секцией `## AIDD`.
  - Повторный init идемпотентен (вне маркеров ничего не меняется).
  **Deps:** W89-1, W89-6

- [ ] **W89-8** `templates/aidd/docs/prompting/conventions.md`, `templates/aidd/docs/prompting/examples/*`, `commands/*.md`, `agents/*.md`:
  - Добавить few-shot “канонические примеры” (минимум 3) и закрепить их как эталон:
    1) implementer: `READY|WARN` + `Tests` + `Context read` + ссылки на `aidd/reports/**`
    2) reviewer: `REVISE` + findings + **Fix Plan** (структурированный) + ссылки
    3) qa: `WARN` (soft missing evidence) + handoff + traceability
  - Требования к примерам:
    - укладываются в budgets (TL;DR/Blockers/NEXT_3 и т.п.);
    - не содержат логов/диффов/стектрейсов, только ссылки;
    - используют обязательные поля output-контракта (из W88-11).
  - В `conventions.md` и/или runtime README добавить ссылку “смотри examples/* как эталон”.
  **AC:**
  - Примеры добавлены и явно указаны как эталон в каноне.
  - Команды/агенты ссылаются на эти примеры (минимум в conventions.md).
  **Deps:** W89-1, W88-11

- [ ] **W89-9** `README.md`, `README.en.md`, `AGENTS.md`, `templates/aidd/AGENTS.md`, `commands/*.md`, `agents/*.md`, `templates/aidd/docs/**`, `CLAUDE.md` (если упоминается в доках):
  - финальный sweep ссылок после консолидации + добавления CLAUDE/examples:
    - проверить, что все упоминания конвенций/архитектуры/anchors/ast-grep/examples ведут в канон;
    - убедиться, что нигде не осталось путей на удалённые файлы;
    - обновить краткие описания/линки (включая упоминание `CLAUDE.md`, если добавлено).
  **AC:** в документации нет устаревших путей; все упоминания ведут на канонические файлы; `CLAUDE.md` и examples интегрированы ссылками.
  **Deps:** W89-1, W89-2, W89-3, W89-4, W89-5, W89-6, W89-7, W89-8

## Wave 100 — Реальная параллелизация (scheduler + claim + parallel loop-run)

_Статус: план. Цель — запуск нескольких implementer/reviewer в параллель по независимым work items, безопасное распределение задач, отсутствие гонок артефактов, консолидация результатов._

### EPIC P — Task Graph (DAG) как источник для планирования
- [ ] **W100-1** `tools/task_graph.py`, `aidd/reports/taskgraph/<ticket>.json` (или `aidd/docs/taskgraph/<ticket>.yaml`):
  - парсер tasklist → DAG:
    - узлы: iterations (`iteration_id`) + handoff (`id: review:* / qa:* / research:* / manual:*`);
    - поля: deps/locks/expected_paths/priority/blocking/state;
    - node id: `iteration_id` или `handoff id`; state выводится из чекбокса + (опционально) stage_result.
  - вычисление `ready/runnable` и топологическая проверка (cycles/missing deps).
  **AC:** из tasklist строится корректный DAG; есть список runnable узлов.

- [ ] **W100-2** `tools/taskgraph-check.sh` (или расширение `tasklist-check.sh`):
  - валидировать: циклы, неизвестные deps, self-deps, пустые expected_paths (если требуется), конфликтующие locks (опционально).
  **AC:** CI/локальный чек ловит некорректные зависимости до запуска параллели.

### EPIC Q — Claim/Lock протокол для work items
- [ ] **W100-3** `tools/work_item_claim.py`, `tools/work-item-claim.sh`, `aidd/reports/locks/<ticket>/<id>.lock.json`:
  - claim/release/renew lock;
  - stale lock policy (ttl, force unlock);
  - в lock хранить `worker_id`, `created_at`, `last_seen`, `scope_key`, `branch/worktree`;
  - shared locks dir (например, `AIDD_LOCKS_DIR`) или orchestrator-only locks; атомарное создание (O_EXCL).
  **AC:** один узел не может быть взят двумя воркерами; stale locks диагностируются и снимаются по правилам; locks общие для всех воркеров.

### EPIC R — Scheduler: выбор runnable узлов под N воркеров
- [ ] **W100-4** `tools/scheduler.py`:
  - выбрать набор runnable узлов на N воркеров:
    - учитывать deps,
    - учитывать `locks`,
    - учитывать пересечения `expected_paths` (конфликт → не запускать параллельно; конфликт = общий top-level group или префикс),
    - сортировка: blocking → priority → plan order.
  **AC:** scheduler отдаёт набор независимых work items; не выдаёт конфликтующие по locks/paths.

- [ ] **W100-5** `tools/loop_pack.py` / `loop-pack.sh`:
  - уметь генерировать loop pack по конкретному work_item_id, а не только “следующий из NEXT_3”;
  - сохранять pack в per‑work‑item пути (Wave 87 уже подготовил).
  **AC:** можно собрать loop pack для любого узла DAG по id; pack содержит deps/locks/expected_paths/size_budget/tests для выбранного узла.

### EPIC S — Parallel loop-run (оркестрация воркеров)
- [ ] **W100-6** `tools/loop_run.py`:
  - добавить режим `--parallel N`:
    - получить runnable узлы от scheduler,
    - claim locks,
    - запустить N воркеров (каждый с явным `--work-item <id>` / `scope_key`),
    - собирать stage results и принимать решения (blocked/done/continue) по каждому узлу.
  **AC:** parallel loop-run запускает N независимых узлов и корректно реагирует на BLOCKED/DONE по каждому; определён контракт artifact root (shared vs per-worktree) и сбор результатов.

- [ ] **W100-7** `tools/worktree_manager.py` (или `tests/repo_tools/worktree.sh`):
  - подготовка isolated рабочих директорий на воркера:
    - `git worktree add` / отдельные ветки,
    - единый шаблон именования веток,
    - cleanup.
  **AC:** каждый воркер работает в изолированном worktree; определён способ записи артефактов (shared root или сбор из worktrees).

### EPIC T — Консолидация результатов обратно в основной tasklist
- [ ] **W100-8** `tools/tasklist_consolidate.py`, `tools/tasklist-normalize.sh`:
  - на основе stage_result + review_pack + tests_log:
    - отметить `[x]` для завершённых узлов,
    - обновить `AIDD:NEXT_3` из DAG runnable,
    - добавить `AIDD:PROGRESS_LOG` записи,
    - перенос/дедуп handoff задач.
  **AC:** после параллельного прогона tasklist обновляется детерминированно; без дублей; NEXT_3 корректен; дедуп handoff по стабильному id.

- [ ] **W100-9** `tools/reports/aggregate.py`:
  - агрегировать evidence в “ticket summary”:
    - ссылки на per‑work‑item tests logs,
    - список stage results,
    - сводка статусов узлов.
  **AC:** есть единый сводный отчёт по тикету и по узлам.

### EPIC U — Документация + регрессии
- [ ] **W100-10** `templates/aidd/docs/loops/README.md`, `templates/aidd/docs/prompting/conventions.md`:
  - задокументировать parallel workflow:
    - deps/locks/expected_paths правила,
    - claim/release,
    - конфликт‑стратегию (paths overlap → serial),
    - policy: воркеры не редактируют tasklist в parallel‑mode (consolidate делает main).
  **AC:** понятная инструкция “как запускать parallel loop-run” + troubleshooting + policy для tasklist/артефактов.

- [ ] **W100-11** `tests/test_scheduler.py`, `tests/test_parallel_loop_run.py`, `tests/repo_tools/parallel-loop-regression.sh`:
  - тесты на DAG, scheduler, claim, параллельный раннер, консолидацию.
  **AC:** регрессии ловят гонки/перетирание артефактов/неверный выбор runnable; включены кейсы conflict paths/lock stale/worker crash.
