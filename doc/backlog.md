# Product Backlog

## Wave 1

### Документация и коммуникация
- [x] `README.md`: добавить краткое TL;DR, оглавление и визуально разбить разделы, вынести дополнительные детали в отдельные ссылки внутри `/doc`.
- [x] `README.md`: подготовить англоязычную версию (двуязычный формат или отдельный файл), описать процедуру синхронизации с основным текстом.
- [x] `workflow.md`: создать пошаговый пример запуска `init-claude-workflow.sh` на демо‑проекте, включить скриншоты/структуру «до и после», обновить ссылки в README.
- [x] `docs/customization.md`: описать настройку `.claude/settings.json`, `config/conventions.json`, хуков и команд, добавить примеры override для разных команд.
- [x] `LICENSE` и `CONTRIBUTING.md`: добавить базовую лицензию, правила приёма вкладов, список каналов связи и шаблоны issue/PR.

### Скрипты и шаблоны
- [x] `init-claude-workflow.sh`: разбить логику на функции, добавить проверки зависимостей (bash, python3, gradle/ktlint), флаг `--dry-run`, единый логгер и детальные сообщения об ошибках.
- [x] `init-claude-workflow.sh`: реализовать smoke‑тесты (например, через `bats` или `pytest + subprocess`) для сценариев «первая установка», `--force`, повторный запуск без изменений и проверка прав доступа.
- [x] `examples/gradle-demo/`: подготовить минимальный Gradle‑монорепо и скрипт `examples/apply-demo.sh`, демонстрирующий автоматическую интеграцию workflow.
- [x] `.claude/commands/*.md`: расширить описание слэш‑команд примерами входных данных и ожидаемого результата, добавить hints по типовым ошибкам.
- [x] `templates/tasklist.md`: дополнить расширенными чеклистами (QA, релиз, документация) и ссылками на связанные артефакты ADR/PRD.

### Качество и процесс
- [x] `.github/workflows/ci.yml`: настроить CI, запускающий shellcheck, линтеры и тесты скрипта на каждом PR.
- [x] `scripts/ci-lint.sh`: собрать единый entrypoint для локального и CI‑прогонов (shellcheck, markdownlint, yamllint).
- [x] `docs/release-notes.md`: зафиксировать процесс версионирования, формат релизов и чеклист публикации (теги, обновление README и демо).
- [x] `.claude/settings.json`: описать в документации политику доступа к инструментам и добавить автопроверку, что настройки не нарушены (pre-commit или тест).

## Wave 2

### Шаблоны документации
- [x] `docs/prd.template.md`: добавить разделы «Метрики успеха» и «Связанные ADR», примеры заполнения и чеклист для ревью.
- [x] `docs/adr.template.md`: включить блок «Импакт на систему», стандартные критерии принятия и ссылку на соответствующие PRD/таски.
- [x] `docs/tasklist.template.md`: различать этапы (аналитика, разработка, QA, релиз) и предусмотреть ссылку на релизные заметки.

### Шаблоны команд и хуков
- [x] `.claude/commands/*.md`: унифицировать формат (описание, входные параметры, побочные эффекты, примеры), добавить quick-reference таблицу.
- [x] `.claude/hooks/format-and-test.sh`: вынести конфигурацию формата/тестов в `.claude/settings.json` или отдельный yaml, добавить переменные окружения для тонкой настройки.

### Настраиваемые файлы
- [x] `config/conventions.json`: описать все поддерживаемые режимы и поля с пояснениями, добавить пример для смешанных команд.
- [x] `.claude/settings.json`: подготовить «стартовый» и «строгий» пресеты, объяснить, как переключаться между ними.
- [x] `templates/git-hooks/`: собрать каталог примерных Git-хуков (commit-msg, pre-push, prepare-commit-msg) с инструкцией по установке.

## Wave 3

### Многошаговый Claude-процесс
- [x] `init-claude-workflow.sh` / `init-claude-workflow.min.sh`: обновить генерацию каркаса под новый цикл «идея → план → валидация → задачи → реализация → ревью» (агенты analyst/planner/validator/implementer/reviewer, команды `/idea-new`, `/plan-new`, `/tasks-new`, `/implement`, `/review`, хук `gate-workflow.sh`, `docs/plan/.gitkeep`).
- [x] Документация и скрипты: убрать упоминания `init-claude-workflow.min.sh`, если мини-версия больше не распространяется, или заменить на актуальный способ доставки (релизный архив/однострочник).
- [x] `scripts/smoke-workflow.sh`: добавить сценарий, который последовательно вызывает новые команды на демо-фиче, проверяет создание PRD/плана/тасклиста и что хук блокирует правки кода до готовности артефактов.
- [x] `.claude/settings.json`: автоматизировать включение разрешений `SlashCommand:/test-changed:*`, новых гейтов (`gate-tests.sh`) и `gate-workflow.sh` через presets, чтобы пользователь мог переключать режимы без ручного редактирования.
- [x] `init-claude-workflow.sh`: добавить генерацию `config/gates.json`, allowlist зависимостей, новых саб-агентов и команд (`/api-spec-new`, `/tests-generate`), чтобы базовая установка включала весь расширенный флоу.

### Автоматические проверки и выборочные тесты
- [x] `.claude/hooks/gate-workflow.sh`: покрыть unit-/интеграционными тестами (через `bats` или `pytest`) сценарии: нет активной фичи, отсутствует PRD/план/тасклисты, разрешение правок в документации, блокировка `src/**`.
- [x] Новые гейты (`gate-tests.sh`): добавить тесты на позитивные и негативные сценарии (feature ticket отсутствует, тест найден/отсутствует, исправление документации и т.д.).
- [x] `.claude/hooks/format-and-test.sh`: удостовериться, что при наличии активной фичи и изменениях в общих файлах запускается полный набор тестов; добавить логирование затронутых модулей в артефакты команд.
- [x] `/implement`: реализовать автоматический перезапуск `/test-changed` после успешных правок (через embedded slash-команду) и добавить fallback-настройку для отключения автозапуска (env `SKIP_AUTO_TESTS`).

### Документация и практики команды
- [x] `workflow.md`: подробно описать новый цикл, роли агентов, формат вопросов/ответов с пользователем, обязанности перед каждым гейтом, включая новые проверки контрактов/миграций/тестов.
- [x] `README.md` / `README.en.md`: обновить обзор команд с учётом `/api-spec-new`, `/tests-generate`, описать назначение новых саб-агентов и барьеров.
- [x] `docs/tasklist.template.md`: дополнить секцией «Интеграция с автогейтами» с чекбоксами READY/BLOCKED, отсылкой к `docs/.active_feature` (обновляется через `/idea-new`) и указанием, какие артефакты нужны для прохождения контракт/миграция/тест-гейтов.
- [x] `docs/customization.md`: добавить раздел «Как включить/отключить гейты и автотесты», описать `config/gates.json`, allowlist зависимостей и варианты кастомизации для проектов без Gradle и monorepo.
- [x] `workflow.md`: обновить сценарий, чтобы продемонстрировать работу новых команд и барьеров (создание API контракта, добавление миграции, автогенерацию тестов).

## Wave 4

### Playbook агентов и барьеров
- [x] `docs/agents-playbook.md`: описать последовательность работы всех агентов (analyst → planner → validator → implementer → reviewer → api-designer → qa-author), список их команд и ожидаемые входы/выходы.
- [x] `docs/agents-playbook.md`: документировать взаимодействие с барьерами (`gate-workflow`, `gate-tests`, `lint-deps`), условия срабатывания, способы обхода и troubleshooting.
- [x] README / onboarding: добавить ссылку на playbook и краткий чеклист запуска фичи, чтобы новая команда понимала полный цикл действий и проверки.

## Wave 5

### Консистентность артефактов и команд
- [x] `scripts/{branch_new.py,commit_msg.py,conventions_set.py}`: вернуть скрипты в репозиторий, синхронизировать их генерацию с `init-claude-workflow.sh` и описать использование в `workflow.md`; добавить unittest, который проверяет наличие CLI-утилит после установки. _(устарело, отменено в Wave 9)_
- [x] `.claude/gradle/init-print-projects.gradle`: добавить файл в исходники, включить его копирование инсталлятором и обновить раздел про selective tests в `README.md`/`README.en.md`; дополнить smoke-сценарий проверкой, что карта модулей создаётся.
- [x] `docs/intro.md`: в репозитории отсутствует обзорный документ; определить замену для устаревшей `/docs-generate`, согласовать формат с README и зафиксировать способ поддержания синхронизации.

### Документация и коммуникация
- [x] `README.md` / `README.en.md`: синхронизировать структуры разделов, обновить блок «Незакрытые задачи», привести отметку _Last sync_ к фактической дате и добавить явный чеклист перевода в `CONTRIBUTING.md`/CI.
- [x] `docs/customization.md` / `workflow.md`: обновить walkthrough и разделы настройки с учётом новой обзорной документации и сценария синхронизации README.

### CI и тестовый контур
- [x] `init-claude-workflow.sh`: устранить рассинхрон с текущим `.github/workflows/ci.yml` (сейчас генерируется `.github/workflows/gradle.yml`); выбрать единый pipeline и описать его в README и релиз-нотах.
- [x] `tests/test_init_claude_workflow.py`: дополнить проверками на наличие overview-документа, helper-скриптов и актуального CI-файла; добавить негативные сценарии (например, отсутствие doc/intro) и очистку временных артефактов.

## Wave 7

### Claude Code feature presets
- [x] `docs/design/feature-presets.md`: описать архитектуру YAML-пресетов на все стадии фичи (PRD, дизайн, тасклист, реализация, релиз), определить обязательные поля (`workflow_step`, `context`, `output`) и схему интеграции с `workflow.md`.
- [x] `claude-presets/feature-*.yaml`: создать набор манифестов (`feature-prd`, `feature-design`, `feature-plan`, `feature-impl`, `feature-release`) с плейсхолдерами для `{{feature}}`, `{{acceptance_criteria}}` и ссылками на актуальные артефакты.
- [x] `init-claude-workflow.sh`: добавить установку каталога пресетов, CLI-флаг `--preset <name>` и автоматическое заполнение шаблонов из `doc/backlog.md`/`workflow.md`.
- [x] `.claude/commands/`: расширить описание `/idea-new`, `/plan-new`, `/tasks-new`, `/implement`, `/review` инструкциями по запуску соответствующих пресетов и обновить quick-reference таблицу.
- [x] `scripts/smoke-workflow.sh`: включить сценарий end-to-end, который прогоняет пресеты по демо-фиче и проверяет генерацию PRD/ADR/tasklist.
- [x] `workflow.md`: обновить walkthrough с разделом «Работа с пресетами» и чеклистом интеграции для новых команд.

## Wave 8

### Чистка устаревших команд и документации
- [x] `.claude/commands/{feature-new.md,feature-adr.md,feature-tasks.md,docs-generate.md}`: удалить, синхронизировать quick-reference и init-скрипт под флоу `/idea-new → /plan-new → /tasks-new → /implement → /review`.
- [x] `README.md` / `README.en.md`: обновить чеклисты и примеры запуска фичи, оставить только актуальные команды (`/idea-new`, `/plan-new`, `/tasks-new`, `/implement`, `/review`).
- [x] `workflow.md`: переписать walkthrough под новый цикл, добавить шаги `/idea-new → /plan-new → /tasks-new` и детальные проверки гейтов (workflow/API/DB/tests).

### Контроль использования CLI-утилит
- [x] `doc/backlog.md` / `tests/`: закрепить решение — Python-утилиты (`scripts/branch_new.py`, `scripts/commit_msg.py`, `scripts/conventions_set.py`) входят в репозиторий, командные файлы опираются на них; описать в README и убедиться, что init-скрипт и тесты поддерживают сценарий. _(устарело, отменено в Wave 9)_

## Wave 9

### Оптимизация core workflow
- [x] `.claude/commands/idea-new.md`: оставить единственным источником установки `docs/.active_feature`, обновить инструкцию и гайды, чтобы исключить отдельный шаг `/feature-activate`.
- [x] `.claude/commands/feature-activate.md`: удалить или переместить в архив, зафиксировать решение в `README.md` и `workflow.md`.
- [x] `.claude/commands/branch-new.md` / `scripts/branch_new.py`: исключить обёртку над `git checkout -b`, обновить bootstrap (`init-claude-workflow.sh`) и документацию, чтобы допускалось ручное создание веток.
- [x] `.claude/commands/commit.md`, `.claude/commands/commit-validate.md`, `.claude/commands/conventions-set.md`, `.claude/commands/conventions-sync.md`: убрать из основного набора команд, поскольку они дублируют стандартные git-инструменты и не задействованы в процессе `idea → review`.
- [x] `init-claude-workflow.sh`: перестать генерировать удаляемые команды/скрипты (`feature-activate`, `branch-new`, `commit*`, `conventions*`) и их документацию.

### Чистка сопровождающего кода
- [x] `scripts/commit_msg.py`, `scripts/conventions_set.py`: удалить после декомиссии команд; обновить `config/conventions.json` и документацию, описав переход на нативные git-флоу.
- [x] `README.md`, `README.en.md`, `workflow.md`, `docs/agents-playbook.md`: пересобрать разделы «Быстрый старт», «Слэш-команды», чеклист, убрав ссылки на исключённые команды и подчёркивая основной цикл `/idea-new → /plan-new → /tasks-new → /implement → /review`.
- [x] Тесты и хуки: убедиться, что `.claude/hooks/*` и `tests/` не ссылаются на удалённые команды; скорректировать smoke-сценарии (`scripts/smoke-workflow.sh`) и демо (`workflow.md`, `examples/apply-demo.sh`).

## Wave 10

### Чистка лишних слэш-команд
- [x] `.claude/commands/api-spec-new.md`: убрать из шаблона, удалить привязку к /api-spec-new во всех гидах (`README.md`, `README.en.md`, `workflow.md`, `docs/agents-playbook.md`, `workflow.md`) и из чеклистов.
- [x] `.claude/commands/tests-generate.md`: удалить команду и ссылки; описать, как покрывать тестами в рамках `/implement` или прямого вызова агента.
- [x] `.claude/commands/test-changed.md`: исключить документацию команды, скорректировать упоминания в руководствах, разъяснив, что `.claude/hooks/format-and-test.sh` запускается автоматически.

### Сопровождающий код и настройки
- [x] `.claude/agents/api-designer.md`, `.claude/agents/qa-author.md`: перенести в раздел «advanced» или удалить после отказа от связанных команд; обновить `docs/agents-playbook.md`.
- [x] `.claude/hooks/gate-tests.sh`: пересмотреть дефолтное поведение; убираем жёсткую зависимость от удалённых команд и переписываем сообщения об ошибках.
- [x] `config/gates.json`: обновить значения и документацию — описать способ включения расширенного режима и параметры `tests_required`.
- [x] `.claude/settings.json`: очистить разрешения `SlashCommand:/api-spec-new`, `/tests-generate`, `/test-changed`, убедиться, что автохуки продолжают работать без дополнительных команд.

### Документация, пресеты и тесты
- [x] `README.md`, `README.en.md`, `workflow.md`: сфокусировать описание флоу на `/idea-new → /plan-new → /tasks-new → /implement → /review`, убрать секции про необязательные артефакты.
- [x] `docs/agents-playbook.md`, `workflow.md`, `docs/customization.md`: переписать сценарии, заменив вызовы `/api-spec-new` и `/tests-generate` на прямое использование агентов или ручные шаги.
- [x] `claude-presets/feature-*.yaml`: пересмотреть wave-пресеты, убрав обязательные шаги дизайна/API/релиза либо вынеся их в отдельный пакет «advanced».
- [x] `scripts/smoke-workflow.sh`: упростить smoke-тест — проверять только базовый цикл и исключить требования к пресетам `feature-design/feature-release`.
- [x] `docs/api/`, `docs/test/`: очистить или перенести каталоги во вспомогательный пакет, если они не задействованы после чистки.

## Wave 11

### Доочистка наследия `/test-changed`
- [x] `.claude/commands/implement.md`: переписать шаги реализации так, чтобы описывать автозапуск `.claude/hooks/format-and-test.sh`, режимы `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, без требований ручного вызова `/test-changed`.
- [x] `claude-workflow-extensions.patch`: удалить возвращение `/test-changed` (файл команды, разрешения `SlashCommand:/test-changed:*`, инструкции агентов), заменить на ссылки на автохуки и прямые команды (`scripts/ci-lint.sh`, `./gradlew test`) в расширенных сценариях.
- [x] `docs/agents-playbook.md`, `workflow.md`: добавить явное пояснение, как работает авто запуск тестов после записи и как временно отключить/расширить его без использования устаревшей команды.

## Wave 13

### CLI-дистрибуция через `uv`
- [x] Подготовить Python-пакет `claude-workflow-cli`: добавить `pyproject.toml`, каркас `src/claude_workflow_cli/` и entrypoint `claude-workflow`, повторяющий функциональность `init-claude-workflow.sh` (копирование шаблонов, пресеты, smoke).
- [x] Перенести необходимые шаблоны и конфиги в пакетные ресурсы (`templates/`, `claude-presets/`, `.claude/**`, `config/**`, `docs/*.template.md`) и настроить их выдачу через `importlib.resources`; предусмотреть проверку зависимостей и режим `--force`.
- [x] Реализовать команды CLI: `init`, `preset`, `smoke`; обеспечить совместимость с текущим bash-скриптом (вызов из Python либо thin-wrapper) и покрыть ключевую логику тестами.
- [x] Обновить документацию (`README.md`, `README.en.md`, `workflow.md`) — описать установку через `uv tool install claude-workflow-cli --from git+https://github.com/<org>/ai_driven_dev.git` и замену `curl | bash`; дополнить разделы о требованиях и обновлениях.
- [x] Добавить инструкцию для пользователей без `uv` (например, `pipx install git+...`) и секцию troubleshooting; проверить установку на чистой среде и зафиксировать сценарий в `scripts/smoke-workflow.sh`.

## Wave 14

_Статус: активный, приоритет 1. Цель — предсказуемые релизы CLI/payload._

### Автоматизация релизов CLI
- [ ] `.github/workflows/release.yml`: триггер на теги `v*`; шаги — `uv build`/`python -m build`, публикация wheel+sdist в GitHub Release через `softprops/action-gh-release`, загрузка payload zip и manifest checksum; складывать артефакты и в CI.
- [ ] Автотегирование: job на `push` в `main`, читает версию из `pyproject.toml`, сверяет с последним релизом и создаёт аннотированный тег (через `actions/create-release` или `git tag`+`gh`), с защитой от повторов и уведомлением при сбое.
- [ ] Документация (`README.md`, `README.en.md`, `workflow.md`): описать цепочку build → release → установка через `uv`/`pipx`, переменные/токены, troubleshooting для неудачных релизов.
- [ ] `CHANGELOG.md` / `docs/release-notes.md`: добавить шаблон/секцию, которую release workflow подтягивает автоматически (последний раздел или Release Drafter); зафиксировать порядок обновления changelog перед тегом.
- [ ] E2E проверка: прогнать сценарий bump версии → push → автотег → CI build → GitHub Release; задокументировать результат и обновить smoke/CI инструкции.

## Wave 15

### Исправление дистрибутива CLI через uv/pipx
- [x] Добавить `MANIFEST.in` (или явный список в `pyproject.toml`), чтобы в пакет попадали скрытые файлы `.claude/settings.json`, `.claude/hooks/lib.sh` и остальные dot-каталоги payload (`recursive-include src/claude_workflow_cli/data/payload .claude/*`).
- [x] Написать регресcионный тест/скрипт, который собирает wheel и проверяет наличие `.claude/**` в архиве (например, `tests/test_package_payload.py`).
- [x] Исправить обработку ошибок в `src/claude_workflow_cli/cli.py`: убрать ручное создание `CalledProcessError(cwd=...)`, использовать `subprocess.run(..., check=True)` и выводить понятное сообщение при отсутствующем шаблоне.
- [x] После фикса обновить `README.md` / `workflow.md`: отметить, что установка через `uv` теперь не требует ручного вмешательства, и добавить инструкцию по обновлению (`uv tool upgrade`, `pipx upgrade`).
- [x] Прогнать smoke (`scripts/smoke-workflow.sh`) и `uv tool install` на чистой директории, зафиксировать результат в `CHANGELOG.md`.

## Wave 16

### CLI upgrade/sync command
- [x] Реализовать `claude-workflow upgrade` (или флаг `--upgrade`), который сравнивает текущие файлы проекта с шаблонами и обновляет только неизменённые файлы (не трогает пользовательские правки).
- [x] Для конфликта/локальных правок создавать резервную копию (или выводить отчёт) и пропускать обновление, чтобы разработчик смог вручную сравнить изменения.
- [x] Обновлять служебные файлы (`.claude/commands`, `hooks`, пресеты, README-шаблоны) из последней версии payload; предусмотреть опцию `--force`, если нужно переписать даже изменённые файлы.
- [x] Добавить хранение версии шаблона (например, `.claude/.template_version`) и предупреждение, если проект отстаёт от установленной версии CLI (предлагать `claude-workflow upgrade`).
- [x] Обновить документацию (README, workflow.md, CHANGELOG) с описанием нового режима, инструкцией для пользователей и предупреждениями о бэкапах.

## Wave 17

### Рефакторинг структуры payload vs. локальная среда
- [x] Перенести все шаблоны и пресеты, которые должны распространяться с библиотекой, в `src/claude_workflow_cli/payload/`, разбить их по каталогам в стиле spec-kit (`payload/.claude/{commands,agents,hooks}`, `payload/docs`, `payload/templates`, `payload/scripts`) и исключить heredoc-генерацию из `init-claude-workflow.sh`, читая артефакты напрямую.
- [x] Создать git-игнорируемый пример локальной конфигурации (`.dev/.claude-example/` + `scripts/bootstrap-local.sh`), который копирует payload в рабочий каталог для dogfooding.
- [x] Обновить `scripts/` и `templates/` на зеркалирование структуры spec-kit (в `scripts/` оставить только операционные утилиты, в `templates/` — исходники генерируемых файлов) и доработать `init-claude-workflow.sh`/CLI так, чтобы они работали с новой раскладкой.
- [x] Добавить сценарий синхронизации (`claude-workflow sync` или документированное решение), который материализует `.claude/**` из payload и обновляет его по запросу.
- [x] Скорректировать упаковку (`MANIFEST.in`, `pyproject.toml`) и тесты, проверяющие, что в дистрибутив попадают все файлы payload и игнорируются локальные примеры.
- [x] Переписать документацию (README, docs/customization.md, workflow.md) с описанием разделения payload/локальных настроек и инструкцией по запуску bootstrap-скрипта.

## Wave 18

### Доставка payload через релизы
- [x] `src/claude_workflow_cli/cli.py`: добавить загрузку payload из GitHub Releases (с выбором версии, кешированием и fallback на локальный бандл) для команд `sync` и `upgrade`.
- [x] `docs/customization.md`, `workflow.md`, `README.md`: описать новый режим удалённого обновления payload, требования к токенам и офлайн-fallback.

### Манифест и контроль целостности
- [x] `payload/manifest.json`: сгенерировать список всех артефактов (размер, checksum, тип) для использования CLI при `sync`/`upgrade`.
- [x] `src/claude_workflow_cli/cli.py`: показывать diff по манифесту перед синхронизацией, проверять контрольные суммы и логировать пропущенные файлы.

### Расширение релизного пайплайна
- [x] `.github/workflows/release.yml`: публиковать zip-архив payload рядом с wheel и прикладывать manifest checksum.
- [x] `CHANGELOG.md`, `docs/release-notes.md`: задокументировать новые артефакты релиза и процесс отката до конкретной версии payload.

## Wave 19

### QA-агент и его пайплайн
- [x] `.claude/agents/qa.md`: описать компетенции и чеклист QA-агента (регрессии, UX, производительность), формат отчёта (severity, scope, рекомендации) и стандартные входные данные; предусмотреть ссылки на смежных агентов и параметры из `.claude/settings.json`.
- [x] `.claude/hooks/gate-qa.sh`: разработать хук, который вызывает QA-агента, агрегирует результаты, выводит краткую сводку, помечает блокеры как `exit 1`, а не критичные замечания — как предупреждения; добавить поддержку dry-run и конфигурации через env.
- [x] `config/gates.json`: добавить новый гейт `qa`, определить условия запуска (ветки, тип задач), правила эскалации и связи с существующими gate-tests; описать параметры таймаутов и разрешённых исключений.
- [x] `.github/workflows/ci.yml`, `.github/workflows/gate-workflow.yml` (если потребуется) и `.claude/hooks/gate-workflow.sh`: встроить QA-гейт в общий пайплайн (локально + CI), предусмотреть опциональный запуск (`CLAUDE_SKIP_QA`, `--only qa`) и корректную композицию с другими gate-скриптами.
- [x] `docs/qa-playbook.md` и `README.md`: зафиксировать процесс подготовки входных данных для QA-агента, примеры отчётов и интерпретацию статусов; обновить разделы usage/TL;DR с указанием, когда запускать гейт и какие артефакты прикладывать в PR.
- [x] `tests/` и/или `scripts/smoke-workflow.sh`: добавить сценарии, проверяющие вызов QA-агента, обработку блокирующих/некритичных дефектов и корректный вывод логов; использовать фикстуры/моки, чтобы детерминировать ответы агента.
- [x] `CHANGELOG.md`: задокументировать добавление QA-агента и обновление пайплайна, описать влияние на разработчиков и инструкцию по миграции (настройка переменных, локальный запуск).

## Wave 20

### Агент ревью PRD и его интеграция в процесс
- [x] `.claude/agents/prd-reviewer.md`: сформулировать мандат агента (структурный аудит PRD, оценка рисков, проверка метрик/гипотез), перечислить входные данные (slug, `docs/prd/<ticket>.prd.md`, связанные ADR/план) и формат отчёта (summary, критичность, замечания по разделам, список открытых вопросов).
- [x] `.claude/commands/review-prd.md`: описать сценарий вызова агента ревью PRD из IDE/CLI; зафиксировать, что результат ревью добавляется в раздел `## PRD Review` внутри `docs/prd/<ticket>.prd.md` и чеклист в `docs/tasklist/<ticket>.md`.
- [x] `.claude/commands/plan-new.md` и `.claude/commands/tasks-new.md`: дополнить инструкциями по обязательной ссылке на результаты PRD-ревью (обновление статуса READY/BLOCKED, перенос критичных замечаний в план и чеклист).
- [x] `.claude/hooks/gate-workflow.sh`: расширить проверку, чтобы перед правками в `src/**` подтверждалось наличие раздела `## PRD Review` с меткой `Status: approved` и отсутствием блокирующих пунктов; предусмотреть bypass через конфиг/slug для прототипов.
- [x] `.claude/hooks/gate-prd-review.sh` (новый): реализовать изолированный хук, который запускает `review-prd` при изменении PRD и блокирует merge при наличии незакрытых blockers; вынести таймаут/уровни серьёзности в `config/gates.json`.
- [x] `config/gates.json`: добавить конфигурацию `prd_review` (ветки, требования, `allow_missing_report`, блокирующие severity, `report_path`) и интеграцию с существующим QA/Tests контуром.
- [x] `docs/agents-playbook.md`, `docs/workflow.md`, `docs/customization.md`: обновить флоу с шагом PRD Review, описать, когда вызывать агента, как интерпретировать вывод и какие поля нужно обновить в PRD/плане; привести пример output.
- [x] `docs/prd.template.md`: добавить шаблонный раздел `## PRD Review` и чеклист статусов (`Status: pending|approved|blocked`, список action items).
- [x] `tests/`: внедрить автотесты `tests/test_gate_prd_review.py` и `tests/test_prd_review_agent.py`, эмулирующие разные статусы ревью, парсинг отчёта, конфигурацию гейта и поведение при блокерах/варнингах.
- [x] `scripts/smoke-workflow.sh` и `README.md`: обновить энд-ту-энд сценарий, показывая этап PRD review (вызов команды, фиксация статуса, переход к планированию); зафиксировать влияние на developer experience и требования к артефактам.

## Wave 21

### Мандат агента Researcher и артефакты
- [x] `.claude/agents/researcher.md`: описать миссию агента «Researcher» — поиск существующей логики, принятых подходов и практик для интеграции новой фичи; перечислить обязательные входные данные (slug фичи, предполагаемый scope изменений, список целевых модулей/директорий, ключевые требования) и формат отчёта (обзор найденных модулей, reuse-возможности, найденные риски, список рекомендаций и open questions).
- [x] `.claude/commands/researcher.md`: задать сценарий вызова агента (когда запускать, какие артефакты приложить, куда сохранять результат), предусмотреть автоматический экспорт отчёта в `docs/research/<ticket>.md` и ссылку на него внутри `docs/tasklist/<ticket>.md` / `docs/prd/<ticket>.prd.md`.
- [x] `docs/templates/research-summary.md`: подготовить шаблон, куда агент будет помещать результаты (структурированные секции «Где встроить», «Повторное использование», «Принятые практики», «Gap-анализ», «Следующие шаги»), и документировать обязательные поля/формат для гейтов.

### Сбор контекста и инструменты для агента
- [x] `src/claude_workflow_cli/tools/researcher_context.py` (новый): реализовать сборщик контекста, который по slug/ключевым словам/путям собирает релевантные участки кода (`rg`-сниппеты, AST/импорт-графы), вытаскивает связанные MD-документы и отдаёт их агенту в виде свернутого prompt-пакета.
- [x] `claude_workflow_cli/data/payload/tools/set_active_feature.py`: расширить, чтобы при активации фичи генерировался список ключевых модулей/директорий для Researcher (по тегам в backlog/conventions), и передавать его в новый сборщик контекста.
- [x] `claude-workflow` CLI: добавить команду `research` (или флаг к `plan-new`), которая запускает сбор контекста, инициирует диалог с агентом и сохраняет отчёт; предусмотреть dry-run и возможность ограничить анализ по каталогам/языкам.

### Интеграция Researcher в флоу и гейты
- [x] `claude-presets/advanced/feature-design.yaml`, `claude-presets/advanced/feature-release.yaml`: встроить шаг Researcher до `plan-new`, описать ожидаемый output и ссылки на отчёт в последующих стадиях (план, тасклист, QA).
- [x] `.claude/hooks/gate-workflow.sh`, `.claude/hooks/gate-tests.sh`: добавить проверку, что для активной фичи существует актуальный `docs/research/<ticket>.md` со статусом `Status: reviewed`, а план/тасклист ссылается на найденные модули; предусмотреть bypass для hotfix/прототипов через `config/gates.json`.
- [x] `config/gates.json`: добавить секцию `researcher` с настройками (требование свежести отчёта, минимальный список проверенных директорий, уровни предупреждений) и связать её с новым хуком/CLI.

### Документация, обучение и контроль качества
- [x] `docs/agents-playbook.md`, `docs/workflow.md`, `docs/feature-cookbook.md`: обновить флоу — описать, какую информацию приносит Researcher, как читать отчёт и каким образом разработчик подтверждает, что рекомендации применены.
- [x] `workflow.md`, `docs/qa-playbook.md`: добавить walkthrough с вызовом Researcher на демо-фиче, демонстрацией найденных участков кода и тем, как отчёт используется в QA/код-ревью.
- [x] `tests/test_researcher_context.py`, `tests/test_gate_researcher.py`: наметить автотесты, которые проверяют сбор контекста, корректность генерации отчёта и работу гейтов (включая edge-case: нет совпадений, конфликтующие рекомендации).
- [x] `scripts/smoke-workflow.sh`, `scripts/ci-lint.sh`: включить Researcher в smoke-сценарий (generate context → вызвать агента → проверить наличие отчёта) и покрыть линтером структуру новых шаблонов.

## Wave 22

### Итеративный диалог analyst
- [x] `.claude/agents/analyst.md`: усилить мандат — прописать, что первые действия агента всегда сбор уточняющих вопросов в формате «Вопрос N», ожидание ответов «Ответ N» и повтор цикла, пока все блокеры не закрыты; зафиксировать, что без подтверждения READY агент завершает с `Status: BLOCKED`.
- [x] `.claude/commands/idea-new.md`: обновить сценарий, чтобы оператор видел явные инструкции отвечать в формате `Ответ N:` и чтобы генерация PRD откладывалась, пока не получены ответы на все вопросы.
- [x] `src/claude_workflow_cli/cli.py`: добавить подсказки/валидацию при запуске `/idea-new`, напоминающие о необходимости отвечать на вопросы и возвращающие к циклу, если ответы пропущены.

### Документация и обучение
- [x] `docs/agents-playbook.md`, `docs/workflow.md`: расширить описание роли analyst с пошаговым Q&A-циклом, критерия READY и форматом фиксации ответов.
- [x] `workflow.md`, `docs/feature-cookbook.md`: включить пример диалога (вопрос → ответ → уточнение) и подчеркнуть, что без закрытия вопросов фича остаётся BLOCKED.
- [x] `README.md`, `README.en.md`: обновить quick start/TL;DR, упомянув обязательные ответы на вопросы analyst перед переходом к планированию.

### Контроль качества
- [x] `scripts/smoke-workflow.sh`, `tests/test_analyst_dialog.py`: внедрить проверку, что первый вывод агента содержит «Вопрос 1», PRD не получает статус READY до явного набора ответов и что формат ответов соблюдён.
- [x] `config/gates.json`, `.claude/hooks/gate-workflow.sh`: добавить правило, блокирующее переход к плану, пока в PRD есть незакрытые вопросы или отсутствуют ответы в требуемом формате.
- [x] `CHANGELOG.md`: описать новые требования к взаимодействию с analyst и влияние на команду (обязательные ответы, обновлённые подсказки CLI).

## Wave 23

### Перенос tasklist в контур фичи
- [x] `docs/tasklist/<ticket>.md`, `docs/tasklist.template.md`: перенести tasklist в каталог `docs/tasklist/`, сформировать ticket-ориентированную структуру (аналогично `docs/prd/<ticket>.prd.md`), добавить front-matter с `Feature:` и ссылками на PRD/plan/research.
- [x] `templates/tasklist.md`, `src/claude_workflow_cli/data/payload/templates/tasklist.md`: обновить шаблон и генерацию, чтобы `init-claude-workflow.sh` и CLI создавали `docs/tasklist/<ticket>.md` вместо корневого `tasklist.md`, учитывая payload-артефакты.
- [x] `scripts/migrate-tasklist.py` (новый), `src/claude_workflow_cli/tools/set_active_feature.py`: подготовить миграцию, которая переносит legacy `tasklist.md` в новую директорию и обновляет ссылки в `.active_feature`.

### Обновление CLI, команд и гейтов
- [x] `src/claude_workflow_cli/cli.py`, `src/claude_workflow_cli/data/payload/.claude/commands/tasks-new.md`, `.claude/commands/tasks-new.md`: научить команды работать с slug-ориентированным tasklist, синхронизировать инструкции и вывод.
- [x] `.claude/hooks/gate-workflow.sh`, `.claude/hooks/gate-tests.sh`, `.claude/hooks/gate-qa.sh`: обновить проверки чеклистов и путь к tasklist; синхронизировать payload-версии хуков.
- [x] `config/gates.json`, `claude-presets/advanced/feature-release.yaml`, `claude-presets/feature-plan.yaml`: скорректировать конфиг и пресеты, чтобы агенты и гейты ссылались на `docs/tasklist/<ticket>.md`.

### Документация, тесты и UX
- [x] `docs/workflow.md`, `docs/agents-playbook.md`, `workflow.md`, `README.md`, `README.en.md`: обновить схемы и walkthrough, подчёркивая, что tasklist теперь хранится в `docs/tasklist/<ticket>.md`.
- [x] `tests/test_gate_workflow.py`, `tests/test_qa_agent.py`, `tests/test_gate_researcher.py`, `scripts/smoke-workflow.sh`: адаптировать тесты и smoke-сценарий под новую структуру tasklist, покрыть миграцию и параллельные slug'и.
- [x] `CHANGELOG.md`, `docs/release-notes.md`, `docs/feature-cookbook.md`: зафиксировать переход на feature-ориентированный tasklist и обновить примеры использования.

## Wave 24

### Управление запуском тестов по запросу reviewer
- [x] `.claude/agents/reviewer.md`: описать протокол, в котором агент reviewer помечает необходимость прогона тестов (например, статус `Tests: required`) и передаёт его в пайплайн.
- [x] `.claude/hooks/format-and-test.sh`, `.claude/hooks/gate-tests.sh`, `.claude/hooks/gate-workflow.sh`: встроить проверку маркера reviewer так, чтобы тесты запускались только по требованию агента, с fallback для ручного запуска (`STRICT_TESTS`, `TEST_SCOPE`).
- [x] `config/gates.json`, `.claude/settings.json`, `src/claude_workflow_cli/cli.py`: добавить настройки и CLI-флаги, позволяющие прокидывать запросы reviewer, включать/выключать обязательный тест-ран и сохранять обратную совместимость.
- [x] `docs/workflow.md`, `docs/agents-playbook.md`, `tests/test_gate_tests_hook.py`, `scripts/smoke-workflow.sh`: зафиксировать новый порядок действий, обновить чеклисты и покрыть сценарий запуска тестов по запросу reviewer/ручному override.

## Wave 25

### Итеративное отмечание прогресса
- [x] `.claude/agents/implementer.md`, `.claude/agents/qa.md`, `.claude/agents/reviewer.md`: усилить инструкции, требуя после каждого инкремента работы фиксировать, какие пункты `docs/tasklist/<ticket>.md` закрыты, и явно указывать номер/название чекбокса, который был отмечен.
- [x] `.claude/commands/implement.md`, `.claude/commands/review.md`, `.claude/commands/tasks-new.md`, `src/claude_workflow_cli/data/payload/.claude/commands/{implement.md,review.md,tasks-new.md}`: добавить шаги с обязательным подтверждением «checkbox updated» и подсказками, как обновлять `- [ ] → - [x]` в текущей ветке перед завершением ответа агента.
- [x] `docs/tasklist.template.md`, `src/claude_workflow_cli/data/payload/docs/tasklist.template.md`: вшить блок «Как отмечать прогресс», описать формат указания времени/итерации рядом с чекбоксом и требования к ссылкам на выполнение.

### Автоматические проверки и UX
- [x] `src/claude_workflow_cli/cli.py`, `src/claude_workflow_cli/progress.py` (новый): реализовать проверку, что каждый вызов `/implement` или `/qa` после изменения кода приводит к появлению новых `- [x]` в активном tasklist; при отсутствии прогресса CLI возвращает подсказку и предлагает вернуться к доработке.
- [x] `.claude/hooks/gate-workflow.sh`, `config/gates.json`: добавить правило, которое блокирует merge, если в diff задач feature нет обновлённых чекбоксов при изменениях в `src/**`; предусмотреть override для технических задач без tasklist.
- [x] `tests/test_gate_workflow.py`, `tests/test_qa_agent.py`, `scripts/smoke-workflow.sh`: расширить тесты, проверяющие, что новый прогресс-чек применяется, и зафиксировать сценарии с несколькими итерациями и отсутствием обновления чекбоксов.

### Документация и обучение команды
- [x] `docs/workflow.md`, `docs/agents-playbook.md`, `docs/qa-playbook.md`: переписать walkthrough, подчёркивая итеративное отмечание прогресса и необходимость ссылаться на обновлённые чекбоксы в ответах агентов.
- [x] `README.md`, `README.en.md`, `CHANGELOG.md`: зафиксировать новое требование и обновить разделы quick start / release notes с описанием обязательной синхронизации tasklist.

## Wave 26

### Переход на идентификатор TICKET
- [x] `src/claude_workflow_cli/cli.py`, `src/claude_workflow_cli/progress.py`, `src/claude_workflow_cli/data/payload/tools/set_active_feature.py`: перевести CLI и хранение состояния на TICKET как основной идентификатор (`--ticket`, `docs/.active_ticket`), мигрировать legacy slug и оставить slug-хинт в качестве дополнительного контекста (`--slug-note`) для агентов.
- [x] `config/gates.json`, `.claude/hooks/format-and-test.sh`, `.claude/hooks/gate-workflow.sh`, `.claude/hooks/gate-tests.sh`, `scripts/smoke-workflow.sh`: обновить проверки и отчёты на использование `{ticket}` вместо `{slug}`, прокидывая slug только как дополнительную подсказку в логах и отчётах.

### Команды и шаблоны
- [x] `.claude/commands/*.md`, `.claude/agents/*.md`, `src/claude_workflow_cli/data/payload/.claude/**`: переписать сигнатуры команд и инструкции агентов под обязательный `<TICKET>` с опциональным блоком `slug`, синхронизировать payload-версии.
- [x] `docs/tasklist.template.md`, `src/claude_workflow_cli/data/payload/docs/tasklist.template.md`, `docs/tasklist/*.md`: внедрить фронт-маттер `Ticket:` и `Slug hint:`, обновить генерацию tasklist/PRD и ссылки на артефакты.

### Документация и миграция
- [x] `README.md`, `README.en.md`, `workflow.md`, `docs/workflow.md`, `docs/agents-playbook.md`, `docs/qa-playbook.md`: переписать walkthrough и примеры команд под модель TICKET-first, описать роль slug-хинта как пользовательского ориентира.
- [x] `CHANGELOG.md`, `docs/release-notes.md`, `docs/feature-cookbook.md`, `tools/migrate_ticket.py` (новый), `tests/test_gate_workflow.py`, `tests/test_qa_agent.py`: подготовить миграцию Wave 26 (скрипт преобразования slug → ticket-first), обновить релизные заметки и покрыть сценарии тестами.

## Wave 27

_Статус: активный, приоритет 1. Объединено с Wave 46. Цель — установка в поддиректорию `aidd/` с полным payload и официальным плагином/хуками Claude Code._
Прогресс: init/sync/smoke/tests под `aidd/` готовы; остаются задачи по документации и оформлению плагина.

### Установка в поддиректорию `aidd/` и упаковка payload (в процессе)
- [x] `doc/design/install-subdir.md`: зафиксировать новую структуру установки (дефолт `./aidd/`), сценарии `--workspace-root`/`--target`, влияние на DX и совместимость; описать, что все артефакты плагина (`aidd/.claude`, `aidd/docs`, `aidd/tools`, `aidd/prompts`, `aidd/scripts`, `aidd/config`, `aidd/claude-presets`, `aidd/templates`, `aidd/reports`, `aidd/etc`) живут внутри поддиректории.
- [x] `doc/adr/install-subdir-decision.md`: сравнить варианты (авто-перенос, генерация поверх `--target`, шаблонный репозиторий) и выбрать целевой подход для `aidd/`.
- [x] `src/claude_workflow_cli/cli.py` / `init.py`: добавить поддержку установки в `aidd/` по умолчанию, опцию переопределения пути, защиту от конфликтов и автоматический перенос payload при `claude-workflow init --target .` (после `uv tool install --force "git+https://github.com/GrinRus/ai_driven_dev.git#egg=claude-workflow-cli[call-graph]"`).
- [x] `src/claude_workflow_cli/resources.py` (новый): единый слой копирования payload/плагина в выбранный корень с учётом manifest, прав и дотфайлов.
- [x] `init-claude-workflow.sh`, `scripts/smoke-workflow.sh`: синхронизировать bash-обёртку с новой структурой, покрыть пустую/существующую директорию, гарантировать идентичную логику с CLI и новой раскладкой `aidd/`. _Сделано: init + smoke работают с поддиректорией, тесты зелёные._
- [x] Обновить manifest/payload так, чтобы все каталоги (`docs/tools/prompts/scripts/config/claude-presets/templates/reports/etc`) жили под `aidd/`; обеспечить sync-скрипты/проверки на новую вложенность и гарантировать, что после `claude-workflow init --target . --commit-mode ticket-prefix --enable-ci --force` доступны команды, агенты и скрипты без ручных шагов. _Сделано: payload переложен в `aidd/`, manifest пересобран под префикс; sync-check обновлён._
- [x] Перенести системные файлы в древовидную структуру `aidd/` (исключить корневые `.claude`/`.dev` и прочие артефакты, которые разворачиваются при установке); разложить корневые шаблоны/скрипты/README, относящиеся к payload, в подпапки. _Сделано: корневые снапшоты удалены, игнор добавлен._
- [x] Покрыть установку в `aidd/` тестами/smoke: CLI init в целевой каталог, проверка доступности всех команд/агентов/скриптов и прав доступа через `claude-workflow` без ручных шагов. _pytest + smoke проходят._

- Оставшиеся открытые задачи по плагину/командам/агентам/хукам и документации перенесены в Wave 46.

## Wave 28

### Интеграция Researcher в `/idea-new`
- [x] `.claude/commands/idea-new.md`: встроить шаг `claude-workflow research --ticket "$1"` перед запуском саб-агента analyst, описать опции `--paths/--keywords`, обработать сценарий «новый проект» (создаём отчёт со статусом `Status: pending` и пометкой «контекст пуст, требуется первичный baseline»).
- [x] `.claude/agents/analyst.md`: требовать актуальный `docs/research/<ticket>.md`, использовать вывод Researcher как источник вопросов, фиксировать в `## Диалог analyst` ссылку на отчёт и отмечать, если исследование выявило готовые паттерны или подтвердило «нет данных».
- [x] `.claude/commands/researcher.md`, `docs/templates/research-summary.md`: добавить блок «Отсутствие паттернов» и обязательную секцию `## Паттерны/анти-паттерны`, описать, как оформлять вывод для пустого проекта.

### CLI и сбор контекста
- [x] `src/claude_workflow_cli/cli.py`: добавить опцию `--auto` для `research` (запуск из `/idea-new` без дополнительных вопросов), возвращать явное уведомление, если найдено 0 матчей, и прокидывать флаг в шаблон.
- [x] `tools/researcher_context.py`: реализовать эвристики поиска актуальных паттернов (детектирование тестов, конфигураций, слоёв `src/*`, шаблонов логирования); при отсутствии совпадений генерировать блок «проект новый» и список рекомендаций на основе `config/conventions.json`.
- [x] `tools/set_active_feature.py`: после установки фичи автоматически запускать `claude-workflow research --targets-only` для подготовки путей ещё до `/idea-new`.

### Автоматические проверки
- [x] `src/claude_workflow_cli/tools/analyst_guard.py`: убедиться, что при Status: READY в PRD присутствует ссылка на исследование и метка статуса из `docs/research/<ticket>.md`; для статуса `Status:.pending` указывать, что research нужно довести до reviewed.
- [x] `.claude/hooks/gate-workflow.sh`, `config/gates.json`: синхронизировать новые статусы research, разрешить merge с пометкой «контекст пуст» только если зафиксирован baseline после `/idea-new`.

### Документация и тесты
- [x] `docs/agents-playbook.md`, `workflow.md`, `README.md`: описать обновлённый порядок `/idea-new → claude-workflow research → analyst`, правила для пустых репозиториев и требования к паттернам.
- [x] `tests/test_gate_researcher.py`, `tests/test_gate_workflow.py`: добавить сценарии для «project new» (нулевые совпадения) и для кейса с найденными паттернами, проверять, что гейт отрабатывает предупреждение.
- [x] `scripts/smoke-workflow.sh`, `examples/gradle-demo/`: показать новую последовательность и пример отчёта Researcher с перечислением найденных паттернов.

## Wave 30

### Автосоздание PRD в `/idea-new`
- [x] `.claude/commands/idea-new.md`: перед запуском аналитика добавить шаг, который гарантированно создаёт `docs/prd/$1.prd.md` из `docs/prd.template.md` (если файл отсутствует), записывает `Status: draft` и ссылку на `docs/research/$1.md`; описать, что повторный запуск не перезаписывает уже заполненный PRD.
- [x] `tools/set_active_feature.py`, `src/claude_workflow_cli/feature_ids.py`: после фиксации тикета автоматически scaffold'ить PRD и директорию `docs/prd/`, чтобы хуки и гейты всегда находили файл до начала диалога; предусмотреть флаг `--skip-prd-scaffold` для редких ручных сценариев.
- [x] `docs/prd.template.md`: обновить шаблон — пометить раздел `## Диалог analyst` статусом `Status: draft`, добавить комментарий о том, что файл создан автоматически и должен быть заполнен агентом до READY.

### Гейты и проверки
- [x] `scripts/prd_review_gate.py`: заменить сообщение «нет PRD → /idea-new» на «PRD в статусе draft, заполните диалог/ревью»; считать `Status: draft` валидным индикатором незавершённого PRD и выдавать понятную инструкцию вместо совета повторно запускать `/idea-new`.
- [x] `src/claude_workflow_cli/tools/analyst_guard.py`: добавить проверку для `Status: draft` с сообщением о необходимости довести диалог до READY, а также убедиться, что наличие автошаблона не обходит требования по вопросам/ответам.
- [x] `tests/test_gate_prd_review.py`, `tests/test_analyst_guard.py`, `scripts/smoke-workflow.sh`: покрыть сценарий автосозданного PRD (файл есть, но статус draft) и убедиться, что гейты выключают ошибку «нет PRD» и переходят к содержательной проверке.

### Документация и обучение
- [x] `README.md`, `README.en.md`, `workflow.md`, `docs/feature-cookbook.md`, `docs/agents-playbook.md`: описать, что `/idea-new` сразу создаёт PRD-шаблон, поэтому гейты больше не просят перезапуск; выделить обязанности агента (заполнить `## Диалог analyst`, снять статус draft).
- [x] `docs/release-notes.md`, `CHANGELOG.md`: зафиксировать Wave 30 как обновление UX аналитики, перечислить шаги автосоздания PRD и обновлённые сообщения гейтов.

## Wave 31

### Единый источник payload + автоматическая синхронизация
- [x] `scripts/sync-payload.sh`: добавить утилиту синхронизации между `src/claude_workflow_cli/data/payload` и корнем. Поддержать режимы `--direction=to-root` (разворачиваем payload в репозитории для dogfooding) и `--direction=from-root` (зеркалим обратно при подготовке релиза); предусмотреть инвариант, что список копируемых директорий задаётся явно (`.claude`, `docs`, `templates`, `scripts/init-claude-workflow.sh` и т.д.), и выводим diff по ключевым файлам.
- [x] `tools/check_payload_sync.py` + CI/pre-commit: написать проверку, которая сравнивает контрольные суммы payload-контента и корневых «runtime snapshot» файлов. Если обнаружены расхождения без фиксации `sync --direction=from-root`, тест/CI должен падать. Добавить запуск в `.github/workflows/ci.yml` и как pre-commit hook.
- [x] Документация и процессы: в `docs/customization.md`, `CONTRIBUTING.md`, `workflow.md` описать правило «редактируем только payload → синхронизуем скриптом». В release checklist добавить обязательный шаг `scripts/sync-payload.sh --direction=from-root && pytest tests/test_init_hook_paths.py` перед `uv publish`. Упомянуть, что для локальной проверки нужно использовать `scripts/bootstrap-local.sh --payload src/.../payload`, а не трогать `.claude` вручную.
- [x] Тесты: расширить `tests/test_init_hook_paths.py` и/или создать `tests/test_payload_sync.py`, который проходит по списку критичных файлов (хуки, `init-claude-workflow.sh`, шаблоны docs) и проверяет, что payload и root синхронизированы. Тест должен использовать общий helper для расчёта хэшей и работать от `src/claude_workflow_cli/data/payload`.
- [x] CI/tooling: обновить `scripts/ci-lint.sh` и `Makefile` (если появится) так, чтобы новые проверки запускались локально командой `scripts/sync-payload.sh --direction=from-root && python tools/check_payload_sync.py`. Зафиксировать рекомендацию в `doc/backlog.md` для последующих волн.

## Wave 32

- [x] `docs/prompt-playbook.md` (новый), `README.md`, `docs/agents-playbook.md`: зафиксировать обязательные секции для агентов/команд (Контекст, Входы, Автоматизация, Формат ответа, Fail-fast), описать требования к строке `Checkbox updated`, ссылкам на `docs/prd|plan|tasklist`, правилам эскалации блокеров и матрицу «роль → артефакты/хуки`.
- [x] `templates/prompt-agent.md`, `templates/prompt-command.md`, `claude-presets/advanced/prompt-governance.yaml` (новый): добавить шаблоны фронт-маттера (`name/description/tools/inputs/outputs/hooks`) и готовые заголовки, а также preset/скрипт развёртывания (`scripts/scaffold_prompt.py` или Make target) с примерами использования в CLI.

### Обновление агентов
- [x] `.claude/agents/{analyst,planner,implementer,reviewer,qa,researcher,validator,prd-reviewer}.md`: переписать на новый шаблон, явно прописать входные артефакты, чеклисты, статусы READY/BLOCKED/WARN и единый формат вывода; удалить дубли описания «Checkbox updated», заменив ссылкой на playbook.

### Обновление команд
- [x] `.claude/commands/{idea-new,plan-new,tasks-new,implement,review-prd,review,reviewer,researcher}.md`: структурировать инструкции блоками «Когда запускать», «Автоматические хуки/переменные», «Что редактируется», «Ожидаемый вывод», «Примеры CLI»; убедиться, что каждая команда ссылается на соответствующего агента и актуальные документы через `@docs/...` нотацию.

### Автоматизация и проверки
- [x] `scripts/lint-prompts.py`, `scripts/ci-lint.sh`, `.github/workflows/ci.yml`, `tests/test_prompt_lint.py`: добавить линтер промптов, который валидирует фронт-маттер, наличие обязательных секций, консистентность между парами агент↔команда (например, implementer/implement), и включить его в CI/pre-commit.

### Мультиязычные промпты и версионирование
- [x] `.claude/agents/**`, `.claude/commands/**`: ввести структуру `prompts/<lang>/...` (RU/EN) или дубликаты `.ru.md`/`.en.md`; в каждом фронт-маттере добавить поля `lang`, `prompt_version`, `source_version` и ссылку на базовый шаблон. Обеспечить, чтобы RU и EN варианты содержали одинаковые блоки (через lint).
- [x] `docs/prompt-playbook.md`, `docs/prompt-versioning.md` (новый): описать политику двух языков, правила синхронизации (когда менять обе версии, как обозначать отличия), формулу версионирования (`major.minor.patch`, где major — изменение структуры, minor — правки текста, patch — правки примечаний), и процедуру ревью (обновление changelog/prompts.json).
- [x] `scripts/lint-prompts.py`, `tools/prompt_diff.py` (новый), `.claude/hooks/gate-workflow.sh`: добавить проверку парности RU/EN (одинаковый `prompt_version`, diff без пропусков блоков), авто-репорт отличий и запрет мержить, если обновлена только одна локаль. В gate выводить подсказку «обновите обе локали или добавьте `Lang-Parity: skip` в фронт-маттер».
- [x] `docs/release-notes.md`, `CHANGELOG.md`: задокументировать запуск двуязычных промптов и версионирования, включая инструкцию «как откатиться к предыдущей версии промпта» (git tag/manifest), и добавить пример записи в release checklist (`scripts/prompt-version bump --lang ru,en`).

### Тесты и проверка качества
- [x] `tests/test_prompt_lint.py`, `tests/test_prompt_diff.py`, `tests/test_prompt_versioning.py` (новый): покрыть сценарии линтера и diff-инструмента (валидация фронт-маттера, парность RU/EN, проверка `prompt_version`), падение на рассинхронизацию и корректное сообщение об обходе `Lang-Parity: skip`.
- [x] `scripts/smoke-workflow.sh`, `tests/test_gate_workflow.py`: добавить smoke-тест на gate, который редактирует только один язык и убеждается, что gate блокирует merge; предусмотреть позитивный сценарий, где обе локали обновлены и gate пропускает изменения.
- [x] `scripts/ci-lint.sh`: включить новые тесты и эмулировать минимум один прогон `scripts/prompt-version bump --lang ru,en` для проверки версионирования.

- [x] `tests/test_prompt_lint.py`, `tests/test_prompt_diff.py`: добавить проверки для команд (а не только агентов) и сценария `Lang-Parity: skip` (позитивный/негативный случаи), убедиться, что линтер корректно пропускает и блокирует файлы с этим маркером.
- [x] `tests/test_prompt_versioning.py`: добавить тесты `scripts/prompt-version` для команд и ситуаций с частичным bump (например, только ru, только en, skip), проверить обновление `source_version`.
- [x] `scripts/smoke-workflow.sh`, `tests/test_gate_workflow.py`: расширить сценарии gate для команд и `Lang-Parity: skip`, включить проверку, что после удаления skip гейт снова требует синхронное обновление.
- [x] `init-claude-workflow.sh`, `claude_workflow_cli` (`cli.py`, payload settings): добавить CLI-переключатель (например, `--prompt-locale en`) или конфиг, который копирует `prompts/en/**` в `.claude/` при установке; обновить документацию и smoke-тест.
- [x] `scripts/prompt-version`, `tools/prompt_diff.py`, release pipeline: автоматизировать шаг «обновить payload → bump версию → проверить lint» (например, make-таргет или GitHub Actions job, который запускает `scripts/prompt-version bump --prompts all --lang ru,en`, lint и проверку gate).

## Wave 33

_Статус: активный, приоритет 3. Цель — zero-touch вызов CLI через shim/helper._

### Zero-touch запуск CLI после установки
- [ ] `tools/run_cli.py` (новый), `tools/set_active_feature.py`, `.claude/hooks/gate-workflow.sh`, `.claude/hooks/format-and-test.sh`, `scripts/smoke-workflow.sh`, `scripts/qa-agent.py`: внедрить helper `run_cli(command: list[str])`, который ищет бинарь `claude-workflow` в PATH (поддержка uv/pipx шима), умеет читать `CLAUDE_WORKFLOW_BIN`/`CLAUDE_WORKFLOW_PYTHON`, а при отсутствии печатает инструкцию «установите CLI командой …»; все скрипты должны использовать helper вместо прямого `python3 -m claude_workflow_cli`, чтобы пользователю хватало шагов установки из README.
  - добавляем в `.claude/hooks/lib_cli.sh` функции `require_cli` и `run_cli_or_hint`, которые:
    1. подключают `tools/run_cli.py` через `python3` и автоматически наследуют `.claude/hooks/_vendor` в `PYTHONPATH`, если helper переключается в режим `python -m`;
    2. умеют печатать INSTALL_HINT и возвращать код 127, если CLI не найден (тот же текст, что в helper);
    3. предоставляют единый API для `gate-workflow.sh`, `gate-qa.sh`, `gate-tests.sh`, `format-and-test.sh` и всех будущих хуков (все вызовы CLI заменяются на `run_cli_or_hint claude-workflow <command>`).
  - `scripts/qa-agent.py` переносим в CLI как `claude-workflow qa-agent`: логика агента живёт в модуле `claude_workflow_cli.commands.qa_agent`, а скрипт в `scripts/` становится тонким шорткатом (или удаляется). `gate-qa.sh` и документация (playbook/QA) вызывают только CLI-команду, без `sys.path` и `python3 scripts/*.py`.
  - `tools/set_active_feature.py`, smoke-скрипт и тестовые helper'ы полностью отказываются от ручных манипуляций с `sys.path`, используют только `run_cli`/`CLAUDE_WORKFLOW_BIN|CLAUDE_WORKFLOW_PYTHON`. В payload добавляем те же `lib_cli.sh`/`tools/run_cli.py` (и, при необходимости, `scripts/run-cli.sh`), чтобы проекты из `claude-workflow init` сразу получали zero-touch UX.
- [ ] `src/claude_workflow_cli/data/payload/scripts/*.sh`, `src/claude_workflow_cli/data/payload/tools/*.py`, `.claude/hooks/*.sh`: зеркалировать helper в payload (например, через `scripts/run-cli.sh`), чтобы артефакты, которые копирует `claude-workflow init`, автоматически вызывают CLI из установленного пакета без ручного PYTHONPATH.
  - payload получает те же `lib_cli.sh`/`run_cli.py`; `manifest.json`, `scripts/sync-payload.sh` и `tools/check_payload_sync.py` обновляются, чтобы helper не выпадал из релиза;
  - smoke-тест из payload и preset'ы прогоняют сценарий без dev-src, подтверждая, что init-проект сразу вызывает CLI через shim.
- [ ] `README.md`, `README.en.md`, `workflow.md`, `docs/agents-playbook.md`: обновить инструкции по установке/требованиям окружения — явно указать, что `claude-workflow` попадает в PATH после `uv tool install`/`pipx install`, удалить рекомендации импортировать модуль напрямую и добавить troubleshooting-блок «CLI не найден» с подсказками `uv tool install …`/`pipx install …`.
  - добавляем раздел «CLI не найден»: `uv tool install …`, `pipx install …`, проверка `which claude-workflow`, использование `CLAUDE_WORKFLOW_BIN`/`CLAUDE_WORKFLOW_PYTHON`;
  - подчёркиваем в workflow/playbook'ах, что все агенты и хуки запускают CLI через helper, поэтому отдельный `pip install` или `PYTHONPATH=src` больше не требуется.
- [ ] `tests/test_cli_entrypoint.py` (новый), `scripts/smoke-workflow.sh`, `scripts/ci-lint.sh`: добавить проверки, эмулирующие чистую систему (`PYTHONPATH` без `src`, только бинарь `claude-workflow`), и убедиться, что helper корректно находит CLI; при отсутствии бинаря тесты должны давать понятное сообщение и ссылку на команды установки.
  - новый тест мокаeт `shutil.which`/`subprocess.run`, проверяет порядок fallback'ов (`CLAUDE_WORKFLOW_BIN → shim claude-workflow → sys.executable -m`), очищает `PYTHONPATH`, и убеждается, что при отсутствии CLI helper печатает INSTALL_HINT и возвращает 127;
  - `scripts/smoke-workflow.sh` перед вызовом helper сбрасывает `PYTHONPATH`, временно скрывает `src` (например, запускается в подпапке без dev-src) и использует `run_cli` для всех команд, чтобы подтвердить zero-touch E2E;
  - `scripts/ci-lint.sh` явно добавляет `python3 -m unittest tests.test_cli_entrypoint.py` (помимо общего `unittest` прогона), чтобы регрессии shim падали до merge.
## Wave 34
### Agent-first промпты и гайды
- [x] `docs/prompt-playbook.md`, `docs/agents-playbook.md`, `workflow.md`, `doc/backlog.md`: переписать правила с упором на «agent-first» модель (агент сам читает файлы и запускает скрипты, вопросы пользователю — крайняя мера), убрать упоминания человеческих ресурсных ограничений и добавить примеры автоматических источников данных.
- [x] `README.md`, `README.en.md`, `docs/release-notes.md`, `CHANGELOG.md`: задокументировать переход на «agent-first» (новый раздел в README, запись в релизных заметках, чеклист миграции существующих проектов).

### Обновление шаблонов документов
- [x] `docs/prd.template.md`, `src/claude_workflow_cli/data/payload/docs/prd.template.md`: заменить поля «Владелец/Команда/Оценка ресурсов» на разделы «Автоматизация/Системные интеграции», добавить подсказки по фиксации CLI/скриптов, которые должен запускать агент.
- [x] `docs/tasklist.template.md`, `src/claude_workflow_cli/data/payload/docs/tasklist.template.md`: переписать чеклисты так, чтобы пункты ссылались на артефакты (диффы, логи тестов, отчёты), а не на коммуникацию со стейкхолдерами; уточнить формат отметок (`путь → дата → ссылка`).
- [x] `docs/templates/research-summary.md`, `src/claude_workflow_cli/data/payload/docs/templates/research-summary.md`: убрать поля `Prepared by`/«Связанные команды», добавить секции «Как запускать окружение», «Обязательные проверки», «Точки вставки кода» с примерами CLI-команд.

### Перепаковка агентов и команд
- [x] `.claude/agents/{analyst,researcher,implementer}.md`, `prompts/en/agents/{analyst,researcher,implementer}.md`, `src/claude_workflow_cli/data/payload/{.claude,prompts/en}/agents/{analyst,researcher,implementer}.md`: переписать контекст и план действий так, чтобы агенты собирали данные из репозитория (backlog, tests, reports) и записывали результаты напрямую. Q&A с пользователем оставляем только у аналитика для заполнения PRD, когда автоматический разбор не отвечает на все вопросы. Обязательно подсветить, какие команды запускать (`rg`, `pytest`, `claude-workflow progress`), какие права/инструменты есть у агента (чтение, запись, доступные Bash-команды) и как фиксировать результаты в артефактах.
- [x] `.claude/commands/idea-new.md`, `prompts/en/commands/idea-new.md`, `src/claude_workflow_cli/data/payload/{.claude,prompts/en}/commands/idea-new.md`: синхронизировать с новой ролью аналитика (автоматическое заполнение PRD, fallback без пользователя), убрать требования ручного подтверждения `--paths/--keywords`.
- [x] `templates/prompt-agent.md`, `templates/prompt-command.md`, `src/claude_workflow_cli/data/payload/templates/{prompt-agent.md,prompt-command.md}`: обновить подсказки — вместо «задавайте вопросы» прописать обязательные блоки по чтению артефактов, запуску утилит и фиксации артефактов в ответе.

### Синхронизация payload и тесты
- [x] `scripts/sync-payload.sh`, `tools/check_payload_sync.py`: убедиться, что новые промпты/шаблоны корректно копируются между корнем и payload, добавить smoke-проверки для agent-first разделов.
- [x] `tests/test_cli_sync.py`, `src/claude_workflow_cli/data/payload/tests/test_payload_sync.py`: расширить тесты синхронизации на новые файлы (обновлённые шаблоны и промпты), чтобы не потерять «agent-first» инструкции в дистрибутиве.
- [x] `scripts/ci-lint.sh`, `.github/workflows/ci.yml`: подключить новые проверки (например, `rg 'Answer [0-9]'` → провал, если в промпте остались упоминания ручного Q&A), прогонять их в CI.

### Коммуникация и миграция
- [x] `docs/feature-cookbook.md`, `docs/customization.md`, `workflow.md`: добавить раздел «Как мигрировать существующие проекты на agent-first» (шаги обновления шаблонов, прогон sync+tests, чеклист по обновлению `.claude/agents`).
- [x] `examples/` (demo проект), `init-claude-workflow.sh`, `claude-presets/**`: обновить демонстрационные артефакты и preset'ы, чтобы они разворачивали уже «agent-first» версии промптов и документов.

## Wave 35

### Команда /qa и UX
- [x] `.claude/commands/qa.md`, `prompts/en/commands/qa.md` (новые): оформить `/qa` как отдельную стадию после `/review`; входы — активный ticket/slug-hint, diff, QA‑раздел tasklist, логи гейтов; автоматизация — обязательный вызов агента `qa` + `gate-qa.sh`, CLI-обёртка `claude-workflow qa --gate` (паттерн остальных команд), `claude-workflow progress --source qa`; формат ответа — `Checkbox updated`, статус READY/WARN/BLOCKED + ссылка на обязательный отчёт `reports/qa/<ticket>.json`; примеры запуска (CLI/палитра).
- [x] `.claude/agents/qa.md`, `prompts/en/agents/qa.md`: обновить под новую команду и agent-first: обязательность перед релизом, фиксация `Checkbox updated`, создание/обновление `reports/qa/<ticket>.json`, ссылки на логи и tasklist.

### Встраивание в процесс
- [x] `workflow.md`, `docs/agents-playbook.md`, `docs/qa-playbook.md`, `README.md`, `README.en.md`: включить обязательный шаг `/qa` (после `/review`) в walkthrough/quick-start, перечислить входы (diff, tasklist QA, логи гейтов), параметры гейта (`CLAUDE_SKIP_QA`, `--only qa`, dry-run), формат отчёта и прогресс-маркеры.
- [x] `docs/tasklist.template.md`: усилить QA-блок — что проверяется, куда писать лог/отчёт, примеры `Checkbox updated` для регрессий/UX/перф с ссылками на `reports/qa/<ticket>.json`.

### Гейты и конфигурация
- [x] `.claude/hooks/gate-qa.sh`, `config/gates.json`: переключить дефолтную команду на `claude-workflow qa --gate` (через helper `run_cli_or_hint`), требовать отчёт `reports/qa/{ticket}.json` (привязка к ticket, allow_missing_report=false), уважать `skip_branches`/`CLAUDE_SKIP_QA`, поддерживать dry-run/`--only qa`, печатать подсказку «запустите /qa».
- [x] `scripts/qa-agent.py`: синхронизировать опции/формат JSON с CLI (`--ticket/--slug-hint/--branch/--report/--block-on/--warn-on/--dry-run`), описать режимы `--gate` и интерактив в `docs/qa-playbook.md`.

### Тесты и payload
- [x] `tests/test_gate_qa.py`, `scripts/smoke-workflow.sh`: unit + полный дымовой сценарий: READY/WARN/BLOCKED, отсутствие отчёта (должно падать), `--only qa`, dry-run (не падает на блокерах), обновление tasklist/`Checkbox updated`; включить в CI.
- [x] `src/claude_workflow_cli/data/payload/**`: отзеркалить новую команду/агента, обновлённые гайды, гейт и smoke-сценарии; обновить `manifest.json` и проверить `tools/check_payload_sync.py`.

## Wave 36

_Статус: активный, приоритет 4. Автоаналитика в `/idea-new` поверх zero-touch CLI._

### Усиление agent-first для `/idea-new` и аналитика
- [ ] `init-claude-workflow.sh`, `claude_workflow_cli/cli.py`: жёсткий автозапуск `claude-workflow analyst --ticket <ticket> --auto` сразу после `research --auto`, graceful fallback с INSTALL_HINT, обновлённые smoke/tests.
- [ ] `.claude/agents/analyst.md`, `prompts/en/agents/analyst.md`: логирование повторных research (paths/keywords), обязательный `analyst-check` при смене статуса READY, fail-fast при отсутствии `.active_ticket`/PRD.
- [ ] `.claude/commands/idea-new.md`, `prompts/en/commands/idea-new.md`: синхронизация с автозапуском аналитика и правилами повторного research; обновить payload-копии и примеры.
- [ ] Тесты и smoke: добавить сценарий `/idea-new` → auto-analyst → repeat research → PRD READY; убедиться, что payload-sync/manifest покрывают новые артефакты.
- [ ] Документация: README/workflow.md/agents-playbook — кратко зафиксировать автозапуск аналитика, логи повторного research и требование `analyst-check` после READY.

## Wave 37

### Удаление внутреннего backlog из дистрибутива
- [x] `doc/backlog.md`: оставить файл только для разработки (dev-only), исключив его из устанавливаемого payload; при необходимости перенести в `docs/dev-backlog.md` или пометить как ignore для sync.
- [x] `src/claude_workflow_cli/data/payload/manifest.json`, `tools/check_payload_sync.py`, `tests/test_payload_manifest.py`, `tests/test_package_payload.py`: удалить запись о `doc/backlog.md`, обновить проверку состава payload и убедиться, что сборка wheel/zip не тянет файл.
- [x] `scripts/sync-payload.sh`, `src/claude_workflow_cli/data/payload/tests/test_payload_sync.py`: скорректировать списки путей, чтобы sync не требовал `doc/backlog.md`; добавить тест, который гарантирует отсутствие dev-only файлов в payload.
- [x] Документация (`docs/prompt-playbook.md`, `docs/release-notes.md`, `CHANGELOG.md`): отметить, что backlog не поставляется конечным пользователям, добавить запись в release checklist и guidance по ведению roadmap в репо без включения в payload.
- [x] Проверка и smoke: прогнать `scripts/ci-lint.sh`, `tools/check_payload_sync.py`, smoke-сценарии сборки дистрибутива, удостовериться в корректной установке через `uv/pipx` без `doc/backlog.md` в артефактах.

## Wave 38

-### Researcher: глубокий анализ кода и переиспользование
- [x] `.claude/agents/researcher.md`, `prompts/en/agents/researcher.md`, `src/claude_workflow_cli/data/payload/{.claude,prompts/en}/agents/researcher.md`: усилить мандат агента — обязательное чтение кода (функции/классы/тесты), поиск точек встраивания и reuse-кандидатов (shared utils, сервисы, API-клиенты), ссылки на конкретные файлы/символы, вывод в разделе «Что переиспользуем» с приоритетами.
- [x] `.claude/commands/researcher.md`, `src/claude_workflow_cli/data/payload/.claude/commands/researcher.md`, `prompts/en/commands/researcher.md`: обновить сценарий запуска с режимом глубокого разбора кода (флаги глубины, фильтр директорий/языков), требовать в отчёте разделы «Паттерны/антипаттерны», «Готовые модули к переиспользованию» и checklist применения; добавить пример вызова с `--deep`/`--reuse` и явную инструкцию строить call/import graph на стороне Claude Code.
- [x] `docs/templates/research-summary.md`, `src/claude_workflow_cli/data/payload/docs/templates/research-summary.md`: расширить шаблон секциями для переиспользования (модуль/файл → как использовать → риски), перечнем найденных паттернов и обязательными ссылками на тесты/контракты, куда агент должен писать результаты.
- [x] `src/claude_workflow_cli/tools/researcher_context.py`, `tools/researcher_context.py`, `src/claude_workflow_cli/data/payload/tools/researcher_context.py`: добавить deep-mode сборки кода (нарезка функций/классов, импорт-листы, соседние тесты, поисковая выдача похожих модулей/утилит без построения графа), агрегировать reuse-кандидатов с метрикой релевантности и отдавать агенту markdown+JSON пакет для промпта; подсветить, что построение call/import graph выполняет агент.
- [ ] `src/claude_workflow_cli/cli.py`, `claude_workflow_cli/data/payload/.claude/hooks/lib_cli.sh`: прокинуть новые параметры контекст-сборки (`--deep-code`, `--reuse-only`, списки директорий/языков) в команду `research`, логировать путь к сгенерированному отчёту и подсвечивать найденные reuse-точки перед запуском агента.
- [x] `tests/test_researcher_context.py`, `tests/test_gate_researcher.py`, `scripts/smoke-workflow.sh`: покрыть глубокий режим (поиск функций/классов, reuse-кандидаты, ссылки на тесты), негативные сценарии без совпадений и проверку, что отчёт содержит обязательные секции; убедиться, что payload-копии проходят sync/manifest проверки и что call graph делегирован агенту.
- [x] `docs/agents-playbook.md`, `docs/workflow.md`, `docs/feature-cookbook.md`, `README.md`, `README.en.md`: описать новый формат работы Researcher (deep-code + reuse), обязательные поля отчёта, примеры интерпретации и как применять рекомендации в план/тасклист; добавить guidance по запуску с фильтрами директорий/языков и явным шагом построения графа на стороне Claude Code.

### Planner: архитектурные принципы и паттерны
- [x] `.claude/agents/planner.md`, `prompts/en/agents/planner.md`, `src/claude_workflow_cli/data/payload/{.claude,prompts/en}/agents/planner.md`: усилить мандат — план обязан опираться на текущую архитектуру (слои/границы модулей), уважать KISS/YAGNI/DRY/SOLID, явно указывать применяемые паттерны (ports/adapters, service layer, CQRS/ES при необходимости) и reuse-точки от Researcher; добавить явные запреты на over-engineering и дублирование.
- [x] `.claude/commands/plan-new.md`, `src/claude_workflow_cli/data/payload/.claude/commands/plan-new.md`, `prompts/en/commands/plan-new.md`: добавить чеклист «Architecture & Patterns» (границы, зависимости, место для кода, выбранные паттерны, ссылки на reuse), требовать компактный вариант реализации (минимальный жизнеспособный план) и fallback при отсутствии подходящих паттернов.
- [x] `docs/feature-cookbook.md`, `docs/workflow.md`, `README.md`, `README.en.md`: описать рекомендуемый вариант реализации планов — базовый сервисный слой + адаптеры к внешним системам, reuse существующих утилит/клиентов, явное ограничение областей (domain/application/infra), ссылки на паттерны и тестовые стратегии.
- [x] `tests/test_planner_agent.py`, `scripts/smoke-workflow.sh`: добавить проверки, что план содержит секцию про архитектурные решения и KISS/YAGNI/DRY, перечисляет reuse-точки и не предлагает избыточных компонентов; обновить smoke-сценарий с примером плана, использующего рекомендованный паттерн (service-layer + adapters).

### Координация выполнения
- [x] Researcher — контекст/CLI: внедрить флаги `--deep-code/--reuse-only/--langs/--paths/--keywords`, вывод топ reuse в stdout, экспорт символов/импортов/тестов в JSON/MD (без call graph), синхронизировать core/tools/payload.
- [x] Researcher — промпты/шаблоны: обновить агента, команду и `research-summary` (RU/EN/payload) с обязательными секциями reuse/паттерны/антипаттерны, шагом построения графа в Claude Code и чеклистом применения.
- [x] Researcher — проверки: дополнить `tests/test_researcher_context.py`, добавить `test_gate_researcher.py`, обновить smoke для deep-скана и статуса; убедиться, что sync/manifest учитывают новые артефакты.
- [x] Planner — промпты/команда: усилить мандат KISS/YAGNI/DRY/SOLID, паттерны service-layer + adapters, reuse-точки, чеклист «Architecture & Patterns», запрет over-engineering; обновить RU/EN/payload.
- [x] Planner — тесты/доки: добавить `tests/test_planner_agent.py`, обновить smoke, задокументировать рекомендованную структуру (domain/app/infra) и применение паттернов в `workflow.md`/cookbook/README.
- [x] Payload/релизы: прогнать sync (`scripts/sync-payload.sh`, `tools/check_payload_sync.py`), обновить manifest/tests, удостовериться в корректной сборке CLI/zip без dev-only файлов.

## Wave 39

### Researcher: построение call/import graph
- [x] `src/claude_workflow_cli/tools/researcher_context.py`, `tools/researcher_context.py`, `src/claude_workflow_cli/data/payload/tools/researcher_context.py`: опциональное построение графа вызовов/импортов. Флаги CLI `--call-graph`/`--graph-engine {auto,none,ts}`, сбор ребёр `caller → callee` (file:line, symbol) и импорт-графа; fallback на текущую эвристику, WARN при отсутствии движка.
- [x] `src/claude_workflow_cli/cli.py`: прокинуть флаги call graph в команду `research`, логировать выбранный движок и выводить количество узлов/ребер в stdout; добавить поля `call_graph`/`import_graph` в JSON.
- [x] Опциональный движок tree-sitter: авто-режим только для Java/Kotlin (kt/kts/java); остальные языки анализируются без графа. Fallback при отсутствии зависимости; graceful degrade в офлайне и явное ограничение языков.
- [x] Тесты: `tests/test_researcher_context.py` + фикстур на call graph (kt/java), `tests/test_researcher_call_graph.py` — проверка рёбер, fallback без tree-sitter, негативные кейсы; e2e `tests/test_researcher_call_graph_e2e.py` на реальных `.java/.kt`; обновлён smoke, чтобы проверять наличие `call_graph` в JSON.
- [x] Шаблоны/промпты: обновить `.claude/agents/researcher.md`, `prompts/en/agents/researcher.md`, `docs/templates/research-summary.md` (и payload-копии) с разделом «Граф вызовов/импортов»: как строить, что включать (узлы/рёбра, источник engine, ограничение на Java/Kotlin), как интерпретировать риски и reuse.
- [x] Документация: `docs/agents-playbook.md`, `workflow.md`, `README.md`, `README.en.md`, `docs/feature-cookbook.md` — описать опцию call graph (когда использовать, параметры CLI, ограничения на языки), примеры вывода и влияние на гейты/планирование.
- [x] Payload/manifest: синхронизировать новые файлы/изменения (tools, шаблоны, промпты, docs), обновить `manifest.json`, `tools/check_payload_sync.py`, smoke в payload.
- [x] Зависимости: добавить optional extra `call-graph` в `pyproject.toml` с `tree-sitter`/`tree-sitter-language-pack`, описать установку через `uv tool install "git+...#egg=claude-workflow-cli[call-graph]"`/`pip install ...[call-graph]`, предусмотреть e2e тест под extra.
- [x] Оптимизация графа: добавить фильтры/лимиты (`--graph-filter <regex>`, `--graph-limit <N>`), auto-focus по ticket/keywords и разделение `call_graph_full`/`call_graph` (focus). Обновить CLI, сборщик, промпты/доки, payload и тесты (юнит + e2e) с учётом монорепы, чтобы контекст не раздувался.
  - [x] В контексте сохранять две версии: full (отдельный файл) и focus (фильтрованный по ticket/keywords и лимиту); в `*-context.json` класть только focus.
  - [x] Фильтр/лимит по умолчанию (например, 300 рёбер) с авто-regex `(<ticket>|<keywords>)`; `--graph-filter/--graph-limit/--force-call-graph` для override.
  - [x] Улучшить идентификаторы рёбер: добавлять package/class (FQN) в `caller`/`callee` для Java/Kotlin, чтобы Claude Code мог однозначно интерпретировать graph.
  - [x] Промпты researcher/шаблон отчёта: указать, что используется focus-граф; full брать только при необходимости; описать флаги filter/limit и типовые пресеты для монорепы.
  - [x] Тесты: юнит на фильтрацию/лимит, e2e c tree-sitter + фильтр (проверить, что focus урезан, full сохранён), smoke — что context не превышает лимит и предупреждение выводится при тримминге.

## Wave 40

_Статус: активный, приоритет 3. Цель — после успешного отчёта автоматически формировать задачи для `/implement` и агента implementer._

### Handoff после отчётов (CLI/агенты)
- [x] `claude_workflow_cli/cli.py`: команда `tasks-derive` (или `handoff`) — читает `reports/qa/{ticket}.json`/`reports/review/{ticket}.json`/`reports/research/{ticket}-context.json`, превращает findings в кандидаты `- [ ]` для `docs/tasklist/<ticket>.md`, поддерживает `--source qa|review|research`, `--dry-run`, `--append` и выводит дифф/сводку затронутых секций.
- [x] `.claude/agents/qa.md`, `prompts/en/agents/qa.md`: добавить секцию «Actionable tasks for implementer» с маппингом finding → чекбокс (scope, severity, ссылка на отчёт), требовать запуск `tasks-derive --source qa` после READY/WARN и фиксацию `Checkbox updated: …`.
- [x] `.claude/agents/researcher.md`, `.claude/commands/researcher.md`, RU/EN payload: включить мандат формировать список доработок (reuse/risks) для implementer и подсказку на автозапуск `tasks-derive --source research` после успешного отчёта.
- [x] `.claude/agents/implementer.md`: описать, что входом служат задачи, сгенерированные из отчётов; требовать ссылку на источник (`reports/qa/...` или research) и обновление `Checkbox updated` по этим пунктам.

### Хуки и гейты
- [x] `.claude/hooks/gate-qa.sh`: опциональный шаг (config `qa.handoff: true`) — после успешного запуска вызывать `tasks-derive --source qa --append`, выводить, какие чекбоксы добавлены; поддержать `CLAUDE_SKIP_QA_HANDOFF`.
- [x] `.claude/hooks/gate-workflow.sh`, `config/gates.json`: расширить `tasklist_progress.sources` новым `handoff`, добавить проверку, что после handoff появились новые `- [x]` либо свежие `- [ ]` с ссылкой на отчёт.
- [x] `claude_workflow_cli/tools` + bash helper: общий хелпер для вызова `tasks-derive` с подсказкой установки (`run_cli_or_hint`), подключить в хуки/скрипты.

### Тесты, payload, документация
- [x] Тесты: `tests/test_tasks_derive.py` — генерация чекбоксов из QA/Review/Research отчётов (ok/warn/block), idempotent append, dry-run; e2e в `scripts/smoke-workflow.sh` (готовый отчёт → handoff → implement).
- [x] Payload-sync: обновить `src/claude_workflow_cli/data/payload/**`, `manifest.json`, `tools/check_payload_sync.py`, убедиться, что `tasks-derive` и обновлённые промпты/хуки включены.
- [x] Документация: `README.md`, `README.en.md`, `workflow.md`, `docs/agents-playbook.md`, `docs/tasklist.template.md` — добавить шаг handoff после отчётов, пример вызова `tasks-derive`, формат маппинга finding → чекбокс и роль implementer в закрытии этих пунктов.

## Wave 41

- [x] Implementer — в промпте/гайдах добавить требование фиксировать изменённые файлы в git: перечислять затронутые пути и выполнять `git add` на каждый модуль перед итоговым ответом/итерацией (связь с `Checkbox updated: …`). Обновить RU/EN + payload.
- [ ] `.claude/agents/implementer.md`, `prompts/en/agents/implementer.md`, payload: дополнить мандат требованием никогда не включать внутренние служебные файлы из самого ai_driven_dev (payload/шаблоны/хуки/вендорные скрипты) в коммит целевого проекта; перед ответом агент проверяет `git status` и явно подтверждает отсутствие таких путей.
- [ ] `.claude/hooks/gate-workflow.sh`, `.claude/hooks/lib_cli.sh`, `config/conventions.json`: добавить проверку/блокировку стейджа/диффа с внутренними служебными файлами ai_driven_dev, выводить подсказку удалить/игнорировать, синхронизировать payload/manifest и автотесты.
- [ ] `src/claude_workflow_cli/cli.py`, `init-claude-workflow.sh`, `README.md`: вшить защиту от включения служебных файлов ai_driven_dev в дефолтную установку (`uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git` → `claude-workflow init --target . --commit-mode ticket-prefix --enable-ci`), обновить smoke/CLI тесты, чтобы после init `git status` не содержал этих путей.

## Wave 42

- [x] QA агент и команда `/qa`: обязать запускать все необходимые тесты (по конфигу/диффу), фиксировать результаты/логи и метки READY/WARN/BLOCKED в `docs/tasklist/<ticket>.md` c ссылкой на отчёт `reports/qa/<ticket>.json`, чтобы имплементер мог подобрать следующие задачи.
- [x] Формат отчёта QA: добавить поля `tests_executed` (команда → статус → лог/URL) и `tests_summary` (pass/fail), чтобы `tasks-derive` мог создавать чекбоксы «QA tests».
- [x] `scripts/qa-agent.py`: эвристика «тесты не запускались/нет логов» → WARN/BLOCKED, чтобы гейт не пропускал пустой QA; учитывать новые поля отчёта.
- [x] `.claude/hooks/gate-qa.sh`, `config/gates.json`, `src/claude_workflow_cli/cli.py`: enforce автозапуск тестов в QA-стадии (reuse `.claude/hooks/format-and-test.sh` или отдельный блок `qa.tests`), писать команды/логи в отчёт, проверять наличие записей в tasklist после проверки, включить подсказку и автоматический handoff (`tasks-derive --source qa --append`) в вывод CLI/гейта.
- [x] `.claude/agents/qa.md`, `prompts/en/agents/qa.md`, payload: обновить мандат/формат ответа — перечислять прогнанные тесты (команда → результат → лог), фиксировать READY/WARN/BLOCKED и новые чекбоксы/ссылки на `reports/qa/<ticket>.json` в tasklist; sync RU/EN, добавить автотесты.
- [x] CLI/гейты: `claude_workflow_cli/cli.py`, `.claude/hooks/gate-qa.sh`, `config/gates.json` — добавить поддержку `progress --source handoff`, блокировку QA, если handoff/tasklist не обновлены, и флаги override (`CLAUDE_SKIP_QA_HANDOFF`, `CLAUDE_QA_ALLOW_NO_TESTS`) с понятными подсказками.
- [x] Тесты/доки: дополнить `tests/test_gate_qa.py`, `tests/test_qa_agent.py`, `tests/test_tasks_derive.py`, `scripts/smoke-workflow.sh` сценариями «QA запускает тесты, пишет логи, handoff обновляет tasklist, progress проходит/проваливается без `[x]`»; обновить `docs/qa-playbook.md`/`README`/`workflow.md` с примерами команд, формата отчёта и минимальным чеклистом логов.

## Wave 43

- [ ] CLI `analyst` (обёртка для агента, auto-mode по дефолту)
  - [ ] `src/claude_workflow_cli/cli.py`: добавить subcommand `analyst` (поля: `--ticket/--feature`, `--slug-hint`, `--target`, `--auto`, `--note`, проброс в аналитический агент или скрипт); graceful ошибка с INSTALL_HINT при отсутствии payload/скрипта.
  - [ ] `prompts/en/commands/idea-new.md`, `.claude/commands/idea-new.md`: синхронизировать инструкции (автозапуск analyst после research, пример CLI).
  - [ ] Документация: README/README.en/workflow/docs/agents-playbook — обновить разделы quick-start/commands, убрать устаревшие предупреждения; отметить auto-mode и связь с `analyst-check`.
  - [ ] Тесты/смоук: добавить сценарий `claude-workflow analyst --ticket demo --auto` (использует demo payload) в `scripts/smoke-workflow.sh` и/или unit на парсер; убедиться, что `invalid choice: 'analyst'` больше не воспроизводится.

- [ ] CLI `tasks-new` (создание tasklist из шаблона/пресета, упоминания устранить)
  - [ ] `src/claude_workflow_cli/cli.py`: добавить subcommand `tasks-new` (опции: `--ticket/--feature`, `--slug-hint`, `--target`, `--force`, `--template/docs/tasklist.template.md`, опционально `--preset feature-plan/impl`), генерировать `docs/tasklist/<ticket>.md` с заполнением placeholders; при конфликте — бэкап/skip и понятное сообщение.
  - [ ] Обновить `.claude/commands/tasks-new.md`, `prompts/en/commands/tasks-new.md` под фактический CLI (аргументы, побочные эффекты, примеры), синхронизировать payload-копии/manifest.
  - [ ] Документация: README/README.en/workflow/docs/agents-playbook — заменить упоминания ручного копирования tasklist на вызов `tasks-new`, добавить troubleshooting (если файл уже есть/отредактирован).
  - [ ] Тесты/смоук: e2e сценарий `claude-workflow tasks-new --ticket demo` → файл создан из шаблона, повторный запуск с `--force`/без — ожидаемое поведение; unit на парсер/конфликты; проверить, что `invalid choice: 'tasks-new'` устранён.

## Wave 44

_Статус: активный, приоритет 2. Цель — устойчивые идентификаторы фичи/тикета и гейты, не падающие из-за длинных/многострочных названий._

### Идентификаторы и CLI
- [ ] `src/claude_workflow_cli/feature_ids.py`, `src/claude_workflow_cli/cli.py`: добавить `safe_identifier/slug` (обрезка до безопасной длины, одна строка, замена пробелов/переводов строк на `-`, короткий хэш при усечении); применять при `write_identifiers`, `resolve_identifiers`, init/idea-new flow, чтобы `.active_ticket/.active_feature` всегда были валидными для путей.
- [ ] Сохранять исходный запрос пользователя (raw ticket/slug) рядом с оптимизированным: писать raw в отдельный файл/поле (`.active_ticket_raw` или metadata) для агентов/LLM, а во все путевые подстановки использовать только сжатый `safe_slug`; в логах/ответах подсвечивать маппинг raw → compressed.
- [ ] `.claude/hooks/format-and-test.sh` и гейты (`gate-qa/tests/workflow`): нормализовать `{ticket}/{slug}` перед подстановкой в пути (`reports/reviewer/...`, `reports/qa/...`), добавлять fallback-хэш и понятный WARN, если исходный идентификатор слишком длинный/многострочный; перехватывать OSError при работе с путями и выводить инструкцию, как поправить ticket.
- [ ] CLI/скрипты: добавить флаг/команду `--sanitize-identifiers` или авто-фиксацию при запуске хуков, которая переписывает существующие `.active_ticket/.active_feature` в безопасный вариант и выводит маппинг `original → safe`.
- [ ] Зафиксировать единые правила sanitize (лимиты длины, допустимые символы, алгоритм хэша, поведение при коллизиях) и применять их для ticket/slug во всех точках (tasklist/PRD/reports/smoke), чтобы вывод/логи показывали raw, а файловые пути — safe.
- [ ] Обновить промпты/CLI help для команд/агентов (`idea-new`, `implementer`, и т.п.), чтобы LLM читала raw идентификатор из metadata и подставляла safe в пути/команды; описать это в payload-копиях.
- [ ] Добавить миграцию: скрипт или авто-rename старых артефактов (`reports/reviewer/<long>.json` и др.) в safe-пути; предусмотреть идемпотентность и подсказку пользователю.

### Документация и инструкции
- [ ] `.claude/commands/idea-new.md`, `prompts/en/commands/idea-new.md`, `README.md`/`workflow.md`: явно требовать короткий ticket/slug (1 строка, до 80 символов, латиница/цифры/`-`), описать auto-sanitize и что длинные описания должны идти в PRD/idea, а не в идентификатор.
- [ ] Troubleshooting: добавить раздел «File name too long / OSError в reviewerGate» с шагами (sanitize, переустановить slug, удалить проблемный отчёт), обновить payload-копии.
- [ ] Уточнить формат хранения raw (путь/JSON-метаданные), кто его читает (агенты/CLI), и как обновляется при переактивации фичи.
- [ ] UX/валидаторы: при вводе тикета предупреждать о многострочности/UTF/длине, показывать превью safe-slug до записи, чтобы избежать сюрпризов.
- [ ] Обратимость: описать rollback на сырой ticket/slug (CLI `set-feature --ticket RAW --keep-safe` или вручную) и сохранять историю переименований в `reports/identifier_migrations.json` для сопоставления артефактов/отчётов.

### Тесты и смоук
- [ ] `tests/test_feature_ids.py`, `tests/test_format_and_test_hook.py` (или новый): кейсы с длинным/многострочным тикетом → safe slug + хэш, отсутствие OSError, корректный путь к `reports/reviewer/...`.
- [ ] `scripts/smoke-workflow.sh`: сценарий с намеренно длинным описанием тикета → auto-sanitize, успешный запуск хуков/тестов; убедиться, что логи содержат подсказку и что отчёты создаются по safe-имени.
- [ ] Тесты на идемпотентность sanitize и на корректный вывод маппинга raw → safe в логах/контексте агентов; e2e миграцию существующего проблемного тикета/репортов.

## Wave 45

_Статус: новый, приоритет 2. Цель — оптимизировать Researcher CLI/агента с явными правилами call graph и baseline-скана._

- [ ] `src/claude_workflow_cli/cli.py`: пересмотреть `research --auto` — по умолчанию включать `--deep-code` и `--call-graph`, если в scope есть kt/kts/java; для остальных языков оставлять лёгкий скан. Добавить эвристику «0 совпадений → предложить graph-only/reuse-only сужение путей/keywords» и понятные WARN в выводе.
- [ ] `src/claude_workflow_cli/tools/researcher_context.py`: разнести fast-scan и graph-scan; если tree-sitter недоступен, писать INSTALL_HINT и сохранять state в контекст. Поддержать авто-выбор фильтра (`ticket|keywords`), флаг `--graph-mode auto|focus|full`, ограничение рёбер и сохранение полного графа отдельным файлом.
- [ ] `.claude/agents/researcher.md`, `prompts/en/agents/researcher.md`: обновить инструкции — когда агент требует call graph, когда достаточно keyword/deep-code; добавить чеклист «если 0 совпадений → baseline + перечень уже выполненных команд и какие ещё запустить».
- [ ] `.claude/commands/researcher.md`, `prompts/en/commands/researcher.md`, `/idea-new`: синхронизировать дефолтные параметры (JVM → call graph+deep-code, non-JVM → fast scan), описать эскалацию дополнительных `--paths/--keywords` и повторный запуск с graph-focus.
- [ ] Документация: `docs/agents-playbook.md`, `docs/feature-cookbook.md`, `workflow.md` — добавить таблицу «когда запускать graph vs обычный ресерч», примеры WARN/INSTALL_HINT, troubleshooting для пустого контекста.
- [ ] Тесты/смоук: кейсы `claude-workflow research --auto` в JVM-репо (строится граф, сохраняется полный JSON), в non-JVM (граф не строится, WARN), и «0 matches → baseline note». Обновить `tests/test_researcher_context.py`, `tests/test_gate_researcher.py`, `scripts/smoke-workflow.sh`.

## Wave 46

_Статус: активный, приоритет 1. Перенос из Wave 27 — плагин AIDD, нормализация команд/агентов, официальные хуки и обновление документации._

### Официальные команды/агенты и плагин AIDD
- [x] Нормализовать `/idea /researcher /plan /review-prd /tasks /implement /review /qa` в плагинном каталоге `.claude-plugin/commands/` с единым фронтматтером (`description/argument-hint/allowed-tools/model/disable-model-invocation`, позиционные `$1/$2`, ссылки `@docs/...`), убрать кастомные поля, обновить quick-reference, prompt-lint и `manifest.json`/sync-проверки под новые пути.
- [x] Переписать `.claude/agents/*.md` и EN-копии в формат плагина (`description/capabilities`, блоки «Роль/Когда вызывать/Как работать с файлами/Правила», статусы READY/BLOCKED/WARN, ссылки на артефакты validator/qa/prd-reviewer), синхронизировать версии RU/EN и линтеры.
- [x] Собрать плагин `feature-dev-aidd` (`.claude-plugin/plugin.json`, `commands/`, `agents/`, `hooks/hooks.json`, при необходимости `.mcp.json`), включить его в payload/manifest, обновить init/sync/upgrade и тесты/CI, чтобы плагин разворачивался вместе с `aidd/`.
- [x] Привести фронтматтер команд/агентов к требованиям Claude Code (обязательные `description/argument-hint/name/tools/model/permissionMode`, позиционные `$1/$ARGUMENTS`, минимальные `allowed-tools`), зашить проверки в prompt-lint и quick-reference с короткими шаблонами.
- [x] Обновить README/README.en/quick-reference под плагин `feature-dev-aidd`: таблица команд с аргументами и @docs артефактами, упоминание `.claude-plugin`, обновить sync-даты.

### Хуки и гейты (официальные события)
- [x] Спроектировать плагинные hook events (PreToolUse/PostToolUse/UserPromptSubmit/Stop/SubagentStop) через `hooks.json`: workflow-gate (PRD/plan/tasklist), tests/format, anti-vibe prompt-gate, QA, post-write `tasks-derive`/`progress`, учесть `config/gates.json` и dry-run.
- [x] Переписать bash-хуки под новый конфиг (убрать/заменить отсутствующие `gate-api-contract.sh`/`gate-db-migration.sh` либо добавить stubs), подключить общий helper и новые события; синхронизировать payload/manifest и sync-проверки.
- [x] Обновить unit/smoke проверки хуков (`tests/test_gate_workflow.py`, `tests/test_gate_tests_hook.py`, `tests/test_gate_qa.py`, `scripts/smoke-workflow.sh`) под плагинные пути и сценарии PostToolUse/PostWrite.

### Документация и CLAUDE.md
- [x] Обновить гайды (`aidd/workflow.md`, `docs/prompt-playbook.md`, `docs/agents-playbook.md`, текущая статья) с примерами `$1/$ARGUMENTS`, `argument-hint`, `@docs/...`, схемой hook events и установкой плагина в поддиректорию `aidd/`.
- [x] Добавить ссылки на `workflow.md` и `config/conventions.md` в `aidd/CLAUDE.md`, вписав в существующий текст без перетирания содержимого.
- [x] Пересобрать quick-start/quick-reference (RU/EN) под плагинную раскладку и новые пути, синхронизировать с README/workflow и manifest/payload тестами.
- [x] Включить в prompt/agents playbook краткие шаблоны команды и агента (по официальной доке: фронтматтер, positional args, allowed-tools), дать ссылки на slash-commands/subagents и community-примеры для копипасты.

### Тестирование и фиксация Wave 46
- [x] После обновления хуков/смоука прогнать `python -m pytest tests/test_gate_workflow.py tests/test_gate_tests_hook.py tests/test_gate_qa.py` и `scripts/smoke-workflow.sh`; зафиксировать результаты.
- [x] При изменениях в payload/хуках обновить `src/claude_workflow_cli/data/payload/manifest.json` (payload sync) и отметить чекбокс Wave 46.
