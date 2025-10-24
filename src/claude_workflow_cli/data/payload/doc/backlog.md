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
- [x] `.claude/settings.json`: автоматизировать включение разрешений `SlashCommand:/test-changed:*`, новых гейтов (`gate-api-contract.sh`, `gate-db-migration.sh`, `gate-tests.sh`) и `gate-workflow.sh` через presets, чтобы пользователь мог переключать режимы без ручного редактирования.
- [x] `init-claude-workflow.sh`: добавить генерацию `config/gates.json`, allowlist зависимостей, новых саб-агентов и команд (`/api-spec-new`, `/tests-generate`), чтобы базовая установка включала весь расширенный флоу.

### Автоматические проверки и выборочные тесты
- [x] `.claude/hooks/gate-workflow.sh`: покрыть unit-/интеграционными тестами (через `bats` или `pytest`) сценарии: нет активной фичи, отсутствует PRD/план/тасклисты, разрешение правок в документации, блокировка `src/**`.
- [x] Новые гейты (`gate-api-contract.sh`, `gate-db-migration.sh`, `gate-tests.sh`): добавить тесты на позитивные и негативные сценарии (feature ticket отсутствует, контракт/миграция/тест найден, исправление документации и т.д.).
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
- [x] `docs/agents-playbook.md`: описать последовательность работы всех агентов (analyst → planner → validator → implementer → reviewer → api-designer → contract-checker → db-migrator → qa-author), список их команд и ожидаемые входы/выходы.
- [x] `docs/agents-playbook.md`: документировать взаимодействие с барьерами (`gate-workflow`, `gate-api-contract`, `gate-db-migration`, `gate-tests`, `lint-deps`), условия срабатывания, способы обхода и troubleshooting.
- [x] README / onboarding: добавить ссылку на playbook и краткий чеклист запуска фичи, чтобы новая команда понимала полный цикл действий и проверки.

## Wave 5 _(закрыто как неактуальное)_

Статус: задачи сняты с планирования и более не актуальны.

### Консистентность артефактов и команд
- [x] `scripts/{branch_new.py,commit_msg.py,conventions_set.py}`: вернуть скрипты в репозиторий, синхронизировать их генерацию с `init-claude-workflow.sh` и описать использование в `workflow.md`; добавить unittest, который проверяет наличие CLI-утилит после установки. _(устарело, отменено в Wave 9)_
- [x] `.claude/gradle/init-print-projects.gradle`: добавить файл в исходники, включить его копирование инсталлятором и обновить раздел про selective tests в `README.md`/`README.en.md`; дополнить smoke-сценарий проверкой, что карта модулей создаётся.
- [x] `docs/intro.md`: в репозитории отсутствует обзорный документ; определить замену для устаревшей `/docs-generate`, согласовать формат с README и зафиксировать способ поддержания синхронизации. _(закрыто как неактуальное)_

### Документация и коммуникация
- [x] `README.md` / `README.en.md`: синхронизировать структуры разделов, обновить блок «Незакрытые задачи», привести отметку _Last sync_ к фактической дате и добавить явный чеклист перевода в `CONTRIBUTING.md`/CI. _(закрыто как неактуальное)_
- [x] `docs/customization.md` / `workflow.md`: обновить walkthrough и разделы настройки с учётом новой обзорной документации и сценария синхронизации README. _(закрыто как неактуальное)_

### CI и тестовый контур
- [x] `init-claude-workflow.sh`: устранить рассинхрон с текущим `.github/workflows/ci.yml` (сейчас генерируется `.github/workflows/gradle.yml`); выбрать единый pipeline и описать его в README и релиз-нотах. _(закрыто как неактуальное)_
- [x] `tests/test_init_claude_workflow.py`: дополнить проверками на наличие overview-документа, helper-скриптов и актуального CI-файла; добавить негативные сценарии (например, отсутствие doc/intro) и очистку временных артефактов. _(закрыто как неактуальное)_

## Wave 6 _(закрыто как неактуальное)_

Статус: задачи сняты с планирования и более не актуальны.

### Расширяемость автоматизации и стеков
- [x] `.claude/hooks/format-and-test.sh`: добавить поддержку нескольких раннеров (Gradle/NPM/Pytest) и расширить `moduleMatrix`, сохранив совместимость с существующим `scripts/ci-lint.sh`. _(закрыто как неактуальное)_
- [x] `init-claude-workflow.sh`: выпустить пресет `polyglot`, генерирующий конфигурации для Gradle/Node/Python (automation.format/tests, moduleMatrix, инструкции зависимостей). _(закрыто как неактуальное)_
- [x] `tests/test_format_and_test.py`: покрыть переключение раннеров, `TEST_SCOPE` и `STRICT_TESTS` в мульти-стековых проектах; добавить временные npm/pytest заглушки. _(закрыто как неактуальное)_

### Наблюдаемость и аналитика
- [x] `scripts/ci-lint.sh`: добавить `--json-report` с длительностью и статусом шагов (`ci-report.json`) и описать экспорт артефактов в CI. _(закрыто как неактуальное)_
- [x] `.claude/hooks/format-and-test.sh`: логировать запуски в `.claude/cache/test-runs.json` (timestamp, runner, задачи, exit-code) и реализовать ротацию логов; задокументировать формат. _(закрыто как неактуальное)_
- [x] `workflow.md`: дополнить troubleshooting инструкциями по анализу `ci-report.json` и `test-runs.json` и чеклистом «что делать, если тесты не стартуют». _(закрыто как неактуальное)_

### Enterprise-безопасность и процессы
- [x] `docs/security-hardening.md`: оформить гайд по профилям защиты, secret-scanning и GitHub Advanced Security; добавить перекрёстные ссылки в README. _(закрыто как неактуальное)_
- [x] `.github/workflows/ci.yml`: расширить pipeline матрицей ОС (ubuntu, macos), шагом `secret-detection` (gitleaks/gh secret scan) и описанием кастомизации в `docs/customization.md`. _(закрыто как неактуальное)_

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
- [x] `.claude/hooks/gate-api-contract.sh`, `.claude/hooks/gate-db-migration.sh`, `.claude/hooks/gate-tests.sh`: пересмотреть дефолтное поведение; убираем жёсткую зависимость от удалённых команд и переписываем сообщения об ошибках.
- [x] `config/gates.json`: обновить значения и документацию — отключить `api_contract`, ослабить `db_migration`/`tests_required` по умолчанию, описать способ включения расширенного режима.
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

## Wave 12

### Автоматизация хуков
- [ ] `.claude/settings.json`: заполнить `automation.format.commands` реальными командами форматирования (Spotless/Ktlint) и сменить `automation.tests.runner` с `bash scripts/ci-lint.sh` на соответствующие Gradle-задачи, чтобы автозапуск хуков отражал целевой стек; синхронизировать обновление в `docs/customization.md`.
- [ ] `.claude/settings.json`: описать `automation.tests.moduleMatrix` для сопоставления путей модулей Gradle и конкретных тестовых задач, обновить `tests/test_format_and_test.py`, чтобы зафиксировать выборочный прогон.

### Усиление гейтов
- [ ] `.claude/hooks/gate-workflow.sh`: вынести список защищаемых путей из жестко заданного `src/**` в конфигурацию (например, `config/gates.json`) и задокументировать расширение для монорепо с альтернативными каталогами исходников.
- [ ] `.claude/hooks/gate-tests.sh`: расширить проверку наличия тестов анализом diff/соседних тестовых файлов и запуском релевантных Gradle-задач; дополнить `tests/test_gate_tests_hook.py` покрытием новых сценариев.

## Wave 13

### CLI-дистрибуция через `uv`
- [x] Подготовить Python-пакет `claude-workflow-cli`: добавить `pyproject.toml`, каркас `src/claude_workflow_cli/` и entrypoint `claude-workflow`, повторяющий функциональность `init-claude-workflow.sh` (копирование шаблонов, пресеты, smoke).
- [x] Перенести необходимые шаблоны и конфиги в пакетные ресурсы (`templates/`, `claude-presets/`, `.claude/**`, `config/**`, `docs/*.template.md`) и настроить их выдачу через `importlib.resources`; предусмотреть проверку зависимостей и режим `--force`.
- [x] Реализовать команды CLI: `init`, `preset`, `smoke`; обеспечить совместимость с текущим bash-скриптом (вызов из Python либо thin-wrapper) и покрыть ключевую логику тестами.
- [x] Обновить документацию (`README.md`, `README.en.md`, `workflow.md`) — описать установку через `uv tool install claude-workflow-cli --from git+https://github.com/<org>/ai_driven_dev.git` и замену `curl | bash`; дополнить разделы о требованиях и обновлениях.
- [x] Добавить инструкцию для пользователей без `uv` (например, `pipx install git+...`) и секцию troubleshooting; проверить установку на чистой среде и зафиксировать сценарий в `scripts/smoke-workflow.sh`.

## Wave 14

### Автоматизация релизов CLI
- [ ] Создать workflow `.github/workflows/release.yml`, который реагирует на тег `v*`, собирает пакет (`python -m build` или `uv build`), прикрепляет `wheel` и `sdist` к GitHub Release через `softprops/action-gh-release`, а также сохраняет артефакты в CI.
- [ ] Продумать авто-тегирование: job на `push` в `main`, который считывает версию из `pyproject.toml`, сверяет с последним релизом и при изменении создаёт аннотированный тег (через `actions/create-release` или `git tag` + `gh`), с защитой от повторов и уведомлением при сбое.
- [ ] Обновить `README.md`, `README.en.md`, `workflow.md` с описанием релизной цепочки (build → release → установка через `uv`/`pipx`), добавить раздел troubleshooting.
- [ ] Завести `CHANGELOG.md` или шаблон релизных заметок; интегрировать с релизным workflow (автоподхват последнего раздела или использование Release Drafter).
- [ ] Протестировать полный путь: инкремент версии → push → авто-тег → CI сборка → GitHub Release; зафиксировать результаты и при необходимости обновить smoke/CI инструкции.

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
- [x] `config/gates.json`: добавить новый гейт `qa`, определить условия запуска (ветки, тип задач), правила эскалации и связи с существующими gate-tests / gate-api-contract; описать параметры таймаутов и разрешённых исключений.
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
- [x] `.claude/agents/reviewer.md`, `.claude/commands/reviewer.md`: описать протокол, в котором агент reviewer помечает необходимость прогона тестов (например, статус `Tests: required`) и передаёт его в пайплайн.
- [x] `.claude/hooks/format-and-test.sh`, `.claude/hooks/gate-tests.sh`, `.claude/hooks/gate-workflow.sh`: встроить проверку маркера reviewer так, чтобы тесты запускались только по требованию агента, с fallback для ручного запуска (`STRICT_TESTS`, `TEST_SCOPE`).
- [x] `config/gates.json`, `.claude/settings.json`, `src/claude_workflow_cli/cli.py`: добавить настройки и CLI-флаги, позволяющие прокидывать запросы reviewer, включать/выключать обязательный тест-ран и сохранять обратную совместимость.
- [x] `docs/workflow.md`, `docs/agents-playbook.md`, `tests/test_gate_tests_hook.py`, `scripts/smoke-workflow.sh`: зафиксировать новый порядок действий, обновить чеклисты и покрыть сценарий запуска тестов по запросу reviewer/ручному override.
