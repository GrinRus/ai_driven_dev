# Product Backlog

## Wave 1

### Документация и коммуникация
- [x] `README.md`: добавить краткое TL;DR, оглавление и визуально разбить разделы, вынести дополнительные детали в отдельные ссылки внутри `/doc`.
- [x] `README.md`: подготовить англоязычную версию (двуязычный формат или отдельный файл), описать процедуру синхронизации с основным текстом.
- [x] `docs/usage-demo.md`: создать пошаговый пример запуска `init-claude-workflow.sh` на демо‑проекте, включить скриншоты/структуру «до и после», обновить ссылки в README.
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
- [x] `.claude/hooks/protect-prod.sh`: расширить шаблон списком исключений и документацией по добавлению дополнительных правил.

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
- [x] Новые гейты (`gate-api-contract.sh`, `gate-db-migration.sh`, `gate-tests.sh`): добавить тесты на позитивные и негативные сценарии (feature slug отсутствует, контракт/миграция/тест найден, исправление документации и т.д.).
- [x] `.claude/hooks/format-and-test.sh`: удостовериться, что при наличии активной фичи и изменениях в общих файлах запускается полный набор тестов; добавить логирование затронутых модулей в артефакты команд.
- [x] `/implement`: реализовать автоматический перезапуск `/test-changed` после успешных правок (через embedded slash-команду) и добавить fallback-настройку для отключения автозапуска (env `SKIP_AUTO_TESTS`).

### Документация и практики команды
- [x] `workflow.md`: подробно описать новый цикл, роли агентов, формат вопросов/ответов с пользователем, обязанности перед каждым гейтом, включая новые проверки контрактов/миграций/тестов.
- [x] `README.md` / `README.en.md`: обновить обзор команд с учётом `/api-spec-new`, `/tests-generate`, описать назначение новых саб-агентов и барьеров.
- [x] `docs/tasklist.template.md`: дополнить секцией «Интеграция с автогейтами» с чекбоксами READY/BLOCKED, отсылкой к `docs/.active_feature` (обновляется через `/idea-new`) и указанием, какие артефакты нужны для прохождения контракт/миграция/тест-гейтов.
- [x] `docs/customization.md`: добавить раздел «Как включить/отключить гейты и автотесты», описать `config/gates.json`, allowlist зависимостей и варианты кастомизации для проектов без Gradle и monorepo.
- [x] `docs/usage-demo.md`: обновить сценарий, чтобы продемонстрировать работу новых команд и барьеров (создание API контракта, добавление миграции, автогенерацию тестов).

## Wave 4

### Playbook агентов и барьеров
- [x] `docs/agents-playbook.md`: описать последовательность работы всех агентов (analyst → planner → validator → implementer → reviewer → api-designer → contract-checker → db-migrator → qa-author), список их команд и ожидаемые входы/выходы.
- [x] `docs/agents-playbook.md`: документировать взаимодействие с барьерами (`gate-workflow`, `gate-api-contract`, `gate-db-migration`, `gate-tests`, `lint-deps`), условия срабатывания, способы обхода и troubleshooting.
- [x] README / onboarding: добавить ссылку на playbook и краткий чеклист запуска фичи, чтобы новая команда понимала полный цикл действий и проверки.

## Wave 5

### Консистентность артефактов и команд
- [x] `scripts/{branch_new.py,commit_msg.py,conventions_set.py}`: вернуть скрипты в репозиторий, синхронизировать их генерацию с `init-claude-workflow.sh` и описать использование в `docs/usage-demo.md`; добавить unittest, который проверяет наличие CLI-утилит после установки. _(устарело, отменено в Wave 9)_
- [x] `.claude/gradle/init-print-projects.gradle`: добавить файл в исходники, включить его копирование инсталлятором и обновить раздел про selective tests в `README.md`/`README.en.md`; дополнить smoke-сценарий проверкой, что карта модулей создаётся.
- [ ] `docs/intro.md`: в репозитории отсутствует обзорный документ; определить замену для устаревшей `/docs-generate`, согласовать формат с README и зафиксировать способ поддержания синхронизации.

### Документация и коммуникация
- [ ] `README.md` / `README.en.md`: синхронизировать структуры разделов, обновить блок «Незакрытые задачи», привести отметку _Last sync_ к фактической дате и добавить явный чеклист перевода в `CONTRIBUTING.md`/CI.
- [ ] `docs/customization.md` / `docs/usage-demo.md`: обновить walkthrough и разделы настройки с учётом новой обзорной документации и сценария синхронизации README.

### CI и тестовый контур
- [ ] `init-claude-workflow.sh`: устранить рассинхрон с текущим `.github/workflows/ci.yml` (сейчас генерируется `.github/workflows/gradle.yml`); выбрать единый pipeline и описать его в README и релиз-нотах.
- [ ] `tests/test_init_claude_workflow.py`: дополнить проверками на наличие overview-документа, helper-скриптов и актуального CI-файла; добавить негативные сценарии (например, отсутствие doc/intro) и очистку временных артефактов.

## Wave 6

### Расширяемость автоматизации и стеков
- [ ] `.claude/hooks/format-and-test.sh`: добавить поддержку нескольких раннеров (Gradle/NPM/Pytest) и расширить `moduleMatrix`, сохранив совместимость с существующим `scripts/ci-lint.sh`.
- [ ] `init-claude-workflow.sh`: выпустить пресет `polyglot`, генерирующий конфигурации для Gradle/Node/Python (automation.format/tests, moduleMatrix, инструкции зависимостей).
- [ ] `tests/test_format_and_test.py`: покрыть переключение раннеров, `TEST_SCOPE` и `STRICT_TESTS` в мульти-стековых проектах; добавить временные npm/pytest заглушки.

### Наблюдаемость и аналитика
- [ ] `scripts/ci-lint.sh`: добавить `--json-report` с длительностью и статусом шагов (`ci-report.json`) и описать экспорт артефактов в CI.
- [ ] `.claude/hooks/format-and-test.sh`: логировать запуски в `.claude/cache/test-runs.json` (timestamp, runner, задачи, exit-code) и реализовать ротацию логов; задокументировать формат.
- [ ] `docs/usage-demo.md`: дополнить troubleshooting инструкциями по анализу `ci-report.json` и `test-runs.json` и чеклистом «что делать, если тесты не стартуют».

### Enterprise-безопасность и процессы
- [ ] `.claude/hooks/protect-prod.sh`: внедрить профили `protection.profiles[]` с режимом `log-only` и предоставить CLI (`scripts/protection_profile.py`) для переключения.
- [ ] `docs/security-hardening.md`: оформить гайд по профилям защиты, secret-scanning и GitHub Advanced Security; добавить перекрёстные ссылки в README.
- [ ] `.github/workflows/ci.yml`: расширить pipeline матрицей ОС (ubuntu, macos), шагом `secret-detection` (gitleaks/gh secret scan) и описанием кастомизации в `docs/customization.md`.

## Wave 7

### Claude Code feature presets
- [x] `docs/design/feature-presets.md`: описать архитектуру YAML-пресетов на все стадии фичи (PRD, дизайн, тасклист, реализация, релиз), определить обязательные поля (`workflow_step`, `context`, `output`) и схему интеграции с `workflow.md`.
- [x] `claude-presets/feature-*.yaml`: создать набор манифестов (`feature-prd`, `feature-design`, `feature-plan`, `feature-impl`, `feature-release`) с плейсхолдерами для `{{feature}}`, `{{acceptance_criteria}}` и ссылками на актуальные артефакты.
- [x] `init-claude-workflow.sh`: добавить установку каталога пресетов, CLI-флаг `--preset <name>` и автоматическое заполнение шаблонов из `doc/backlog.md`/`docs/usage-demo.md`.
- [x] `.claude/commands/`: расширить описание `/idea-new`, `/plan-new`, `/tasks-new`, `/implement`, `/review` инструкциями по запуску соответствующих пресетов и обновить quick-reference таблицу.
- [x] `scripts/smoke-workflow.sh`: включить сценарий end-to-end, который прогоняет пресеты по демо-фиче и проверяет генерацию PRD/ADR/tasklist.
- [x] `docs/usage-demo.md`: обновить walkthrough с разделом «Работа с пресетами» и чеклистом интеграции для новых команд.

## Wave 8

### Чистка устаревших команд и документации
- [x] `.claude/commands/{feature-new.md,feature-adr.md,feature-tasks.md,docs-generate.md}`: удалить, синхронизировать quick-reference и init-скрипт под флоу `/idea-new → /plan-new → /tasks-new → /implement → /review`.
- [x] `README.md` / `README.en.md`: обновить чеклисты и примеры запуска фичи, оставить только актуальные команды (`/idea-new`, `/plan-new`, `/tasks-new`, `/implement`, `/review`).
- [x] `docs/usage-demo.md`: переписать walkthrough под новый цикл, добавить шаги `/idea-new → /plan-new → /tasks-new` и детальные проверки гейтов (workflow/API/DB/tests).

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
- [x] Тесты и хуки: убедиться, что `.claude/hooks/*` и `tests/` не ссылаются на удалённые команды; скорректировать smoke-сценарии (`scripts/smoke-workflow.sh`) и демо (`docs/usage-demo.md`, `examples/apply-demo.sh`).

## Wave 10

### Чистка лишних слэш-команд
- [x] `.claude/commands/api-spec-new.md`: убрать из шаблона, удалить привязку к /api-spec-new во всех гидах (`README.md`, `README.en.md`, `workflow.md`, `docs/agents-playbook.md`, `docs/usage-demo.md`) и из чеклистов.
- [x] `.claude/commands/tests-generate.md`: удалить команду и ссылки; описать, как покрывать тестами в рамках `/implement` или прямого вызова агента.
- [x] `.claude/commands/test-changed.md`: исключить документацию команды, скорректировать упоминания в руководствах, разъяснив, что `.claude/hooks/format-and-test.sh` запускается автоматически.

### Сопровождающий код и настройки
- [x] `.claude/agents/api-designer.md`, `.claude/agents/qa-author.md`: перенести в раздел «advanced» или удалить после отказа от связанных команд; обновить `docs/agents-playbook.md`.
- [x] `.claude/hooks/gate-api-contract.sh`, `.claude/hooks/gate-db-migration.sh`, `.claude/hooks/gate-tests.sh`: пересмотреть дефолтное поведение; убираем жёсткую зависимость от удалённых команд и переписываем сообщения об ошибках.
- [x] `config/gates.json`: обновить значения и документацию — отключить `api_contract`, ослабить `db_migration`/`tests_required` по умолчанию, описать способ включения расширенного режима.
- [x] `.claude/settings.json`: очистить разрешения `SlashCommand:/api-spec-new`, `/tests-generate`, `/test-changed`, убедиться, что автохуки продолжают работать без дополнительных команд.

### Документация, пресеты и тесты
- [x] `README.md`, `README.en.md`, `workflow.md`: сфокусировать описание флоу на `/idea-new → /plan-new → /tasks-new → /implement → /review`, убрать секции про необязательные артефакты.
- [x] `docs/agents-playbook.md`, `docs/usage-demo.md`, `docs/customization.md`: переписать сценарии, заменив вызовы `/api-spec-new` и `/tests-generate` на прямое использование агентов или ручные шаги.
- [x] `claude-presets/feature-*.yaml`: пересмотреть wave-пресеты, убрав обязательные шаги дизайна/API/релиза либо вынеся их в отдельный пакет «advanced».
- [x] `scripts/smoke-workflow.sh`: упростить smoke-тест — проверять только базовый цикл и исключить требования к пресетам `feature-design/feature-release`.
- [x] `docs/api/`, `docs/test/`: очистить или перенести каталоги во вспомогательный пакет, если они не задействованы после чистки.

## Wave 11

### Доочистка наследия `/test-changed`
- [x] `.claude/commands/implement.md`: переписать шаги реализации так, чтобы описывать автозапуск `.claude/hooks/format-and-test.sh`, режимы `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, без требований ручного вызова `/test-changed`.
- [x] `claude-workflow-extensions.patch`: удалить возвращение `/test-changed` (файл команды, разрешения `SlashCommand:/test-changed:*`, инструкции агентов), заменить на ссылки на автохуки и прямые команды (`scripts/ci-lint.sh`, `./gradlew test`) в расширенных сценариях.
- [x] `docs/agents-playbook.md`, `docs/usage-demo.md`: добавить явное пояснение, как работает авто запуск тестов после записи и как временно отключить/расширить его без использования устаревшей команды.

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
- [x] Обновить документацию (`README.md`, `README.en.md`, `docs/usage-demo.md`) — описать установку через `uv tool install claude-workflow-cli --from git+https://github.com/<org>/ai_driven_dev.git` и замену `curl | bash`; дополнить разделы о требованиях и обновлениях.
- [x] Добавить инструкцию для пользователей без `uv` (например, `pipx install git+...`) и секцию troubleshooting; проверить установку на чистой среде и зафиксировать сценарий в `scripts/smoke-workflow.sh`.

## Wave 14

### Автоматизация релизов CLI
- [ ] Создать workflow `.github/workflows/release.yml`, который реагирует на тег `v*`, собирает пакет (`python -m build` или `uv build`), прикрепляет `wheel` и `sdist` к GitHub Release через `softprops/action-gh-release`, а также сохраняет артефакты в CI.
- [ ] Добавить workflow `publish.yml` (ручной `workflow_dispatch` или по тегу) для публикации в PyPI через `pypa/gh-action-pypi-publish`, оформить требования к секретам (`PYPI_API_TOKEN`) и расписать порядок действий в документации.
- [ ] Продумать авто-тегирование: job на `push` в `main`, который считывает версию из `pyproject.toml`, сверяет с последним релизом и при изменении создаёт аннотированный тег (через `actions/create-release` или `git tag` + `gh`), с защитой от повторов и уведомлением при сбое.
- [ ] Обновить `README.md`, `README.en.md`, `docs/usage-demo.md` с описанием релизной цепочки (build → release → PyPI), добавить раздел troubleshooting (например, восстановление при провале загрузки).
- [ ] Завести `CHANGELOG.md` или шаблон релизных заметок; интегрировать с релизным workflow (автоподхват последнего раздела или использование Release Drafter).
- [ ] Протестировать весь путь: инкремент версии → push → авто-тег → CI сборка → GitHub Release → публикация на TestPyPI/PyPI; зафиксировать результаты и при необходимости обновить smoke/CI инструкции.
