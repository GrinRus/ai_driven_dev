# Демонстрация использования CLI `claude-workflow`

Этот документ показывает, как развернуть Claude Code workflow через новую CLI-команду `claude-workflow init` на минимальном Gradle-монорепозитории. В примере используется каталог `demo-monorepo`, но те же шаги применимы к любому Java/Kotlin проекту.

## Цель сценария
- развернуть шаблон всего за один запуск скрипта;
- понять, какие файлы и настройки добавляются;
- проверить, что выборочные тесты и хуки работают сразу после установки;
- пройти многошаговый цикл `/idea-new → /plan-new → /tasks-new → /implement → /review` и увидеть работу гейтов (workflow, миграции, тесты).

## Требования
- установленный `bash`, `git`, `python3`;
- Gradle wrapper (`./gradlew`) в корне демо-проекта;
- установленный CLI: `uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git` (альтернатива — `pipx`);
- опционально: `ktlint` или Spotless, чтобы увидеть работу автоформатирования.

> Если CLI недоступна, используйте локальный скрипт `init-claude-workflow.sh` (поставляется в репозитории и повторяет команды `claude-workflow init`/`claude-workflow preset`).

## Структура до запуска

```text
demo-monorepo/
├── build.gradle.kts
├── settings.gradle.kts
├── gradle/
│   └── wrapper/…
├── service-checkout/
│   ├── build.gradle.kts
│   └── src/main/kotlin/CheckoutService.kt
└── service-payments/
    ├── build.gradle.kts
    └── src/main/kotlin/PaymentsService.kt
```

## Пошаговый walkthrough

### 1. Подготовьте окружение

```bash
uv tool install claude-workflow-cli --from git+https://github.com/GrinRus/ai_driven_dev.git
git clone git@github.com:your-org/demo-monorepo.git
cd demo-monorepo
```

> Нет `uv`? Замените на `pipx install git+https://github.com/GrinRus/ai_driven_dev.git`. Локальный скрипт по-прежнему доступен как резервный вариант.

### 2. Запустите установку

```bash
claude-workflow init \
  --target . \
  --commit-mode ticket-prefix \
  --enable-ci \
  --force
```

- `--target .` явно указывает каталог проекта (можно опустить);
- `--commit-mode` задаёт стартовый режим сообщений коммитов;
- `--enable-ci` добавляет workflow GitHub Actions;
- `--force` перезаписывает существующие файлы (удобно при повторном запуске на демо).

Ожидаемые лог-сообщения (сокращённо):

```text
[INFO] Checking prerequisites: bash ✅ python3 ✅ gradle ✅
[INFO] Generating Claude Code structure…
[INFO] Installing git hooks to .claude/hooks
[INFO] Writing config/conventions.json (mode=ticket-prefix)
[INFO] CI workflow enabled → .github/workflows/gradle.yml
[DONE] Claude Code workflow is ready to use 🎉
```

### 3. Проверьте git-статус и содержимое

```bash
git status -sb
```

```text
## main
A  .claude/settings.json
A  .claude/hooks/format-and-test.sh
A  config/conventions.json
…
```

При желании сделайте `git diff` по любому файлу, чтобы посмотреть значения по умолчанию.

### 4. Запустите выборочные тесты вручную (опционально)

```bash
.claude/hooks/format-and-test.sh
```

Проверьте, что скрипт определил Gradle-модули и запустил тесты только для них.

> Полезно знать: `SKIP_AUTO_TESTS=1` временно отключает автозапуск после правок, `FORMAT_ONLY=1` ограничивает шаг форматированием, `TEST_SCOPE=":app:test"` или `TEST_CHANGED_ONLY=0` позволяют управлять набором задач, `STRICT_TESTS=1` превращает предупреждения об упавших тестах в ошибку.

## Структура после запуска

```text
demo-monorepo/
├── .claude/
│   ├── agents/
│   ├── commands/
│   ├── gradle/init-print-projects.gradle
│   ├── hooks/{format-and-test.sh,protect-prod.sh}
│   ├── settings.json
│   └── cache/project-dirs.txt
├── config/conventions.json
├── docs/
│   ├── adr.template.md
│   ├── prd.template.md
│   └── tasklist.template.md
├── scripts/
│   ├── ci-lint.sh
│   └── smoke-workflow.sh
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/gradle.yml
└── README.md (обновлён)
```

> Снимок «после» удобно зафиксировать командой `tree -L 2` или встроенным предпросмотром IDE. Для презентаций добавьте изображения каталога до/после в `docs/images/`.

### 5. Запустите многошаговый процесс

1. В Claude Code выполните `/idea-new demo-checkout DEMO-1` — команда зафиксирует slug в `docs/.active_feature`, соберёт PRD и список уточнений.
2. Постройте план и чеклисты: `/plan-new demo-checkout` сформирует план, а `/tasks-new demo-checkout` перенесёт его в `tasklist.md`.
3. При необходимости включите дополнительные гейты в `config/gates.json` и подготовьте связанные артефакты: миграции, OpenAPI-файлы, расширенные тесты.
4. Запустите `/implement demo-checkout` — агент будет идти малыми шагами, а `.claude/hooks/format-and-test.sh` автоматически выполнит форматирование и выборочные тесты (отключаемо `SKIP_AUTO_TESTS=1`).
5. Фиксируйте прогресс в git (`git commit -m "DEMO-1: add rule engine"`), пока tasklist не будет закрыт и тесты не станут зелёными.

## Проверка результата в Claude Code
1. Создайте ветку `git checkout -b feature/DEMO-1`, соблюдая выбранную конвенцию.
2. Запустите `/idea-new`, `/plan-new`, `/tasks-new` и убедитесь, что `docs/` и `tasklist.md` обновились.
3. Проверьте гейты: `gate-workflow` пропускает правки только после появления PRD/плана/tasklist; при включённых флагах `api_contract`, `db_migration`, `tests_required` появятся подсказки о недостающих артефактах.
4. После правок убедитесь, что `.claude/hooks/format-and-test.sh` запускается автоматически; при необходимости используйте `SKIP_AUTO_TESTS=1` для паузы, `FORMAT_ONLY=1` или `TEST_SCOPE=":module:test"` для точечной настройки и запускайте скрипт вручную при сложных изменениях.
5. Зафиксируйте изменения (`git commit -m "DEMO-1: implement rule engine"`) и вызовите `/review demo-checkout`, чтобы закрыть чеклист и убедиться, что режим коммитов синхронизирован.

## Работа с пресетами фич

После установки в корне появляется каталог `claude-presets/` с YAML-манифестами для каждого шага фичи. Пресеты используются двумя способами:

1. **Через CLI.** Выполните `claude-workflow preset feature-prd --feature checkout-discounts`, чтобы развернуть демо-PRD. По мере необходимости добавляйте `feature-plan` и `feature-impl`, а расширенные пресеты (`feature-design`, `feature-release`) доступны в `claude-presets/advanced/`. CLI автоматически подставит цели из `docs/usage-demo.md` и задачи из `doc/backlog.md (Wave 7)`. Резервный сценарий — `bash init-claude-workflow.sh --preset …`.
2. **Внутри Claude Code.** Добавьте файл пресета в контекст (например, `claude-presets/feature-plan.yaml`) или настройте кнопку в интерфейсе — описание находится в `claude-workflow-extensions.patch`.

Текущее покрытие:

| Пресет | Результат | Файл | Расположение |
| --- | --- | --- | --- |
| `feature-prd` | Черновик PRD и метрики успеха | `docs/prd/<slug>.prd.md` | `claude-presets/` |
| `feature-plan` | План реализации и контрольные точки | `docs/plan/<slug>.md` | `claude-presets/` |
| `feature-impl` | Секция чеклистов в tasklist | `tasklist.md` | `claude-presets/` |
| `feature-design` | Архитектура/ADR для фичи | `docs/design/<slug>.md` | `claude-presets/advanced/` |
| `feature-release` | Запись в релизных заметках | `docs/release-notes.md` | `claude-presets/advanced/` |

Скрипт `scripts/smoke-workflow.sh` демонстрирует полный E2E: он разворачивает шаблон, активирует фичу `demo-checkout`, прогоняет базовые пресеты (`feature-prd`, `feature-plan`, `feature-impl`) и проверяет, что гейт `gate-workflow.sh` начинает пропускать правки только после появления PRD/плана/тасклиста.

## Релизный цикл CLI
1. Обновите версию в `pyproject.toml` и соответствующий блок в `CHANGELOG.md`.
2. Запустите `scripts/ci-lint.sh` и `claude-workflow smoke`, зафиксируйте изменения и сделайте `git push` в `main`. Workflow `autotag.yml` создаст тег `v<версия>`, если его ещё нет.
3. Тег запустит `release.yml`: пакет соберётся (`python -m build`), артефакты попадут в GitHub Release и в артефакты workflow.
4. После проверки релиза запустите workflow `Publish` (автоматически от события Release или вручную). Опции:
   - `pypi` (по умолчанию) — требуется секрет `PYPI_API_TOKEN`.
   - `testpypi` — используйте ручной запуск и секрет `TEST_PYPI_API_TOKEN`.
5. Убедитесь, что релиз появился на GitHub и что дистрибутив доступен в соответствующем реестре. При ошибках переопубликовать можно, повторно запустив `Publish` с флагом `skip-existing`.

## Частые вопросы
- **Запуск скрипта терпит неудачу:** проверьте вывод проверки зависимостей и убедитесь, что Gradle доступен в PATH.
- **Тесты не стартуют:** убедитесь, что `./gradlew` исполняемый (`chmod +x gradlew`) и что скрипт имеет права на запуск.
- **Файлы уже существуют:** добавьте `--force`, но предварительно сохраните изменения в git или сделайте резервную копию.
- **Нужно повторно прогнать установку:** скрипт безопасно перезаписывает артефакты. Чтобы увидеть только изменения, используйте `git diff`.

Теперь демо-проект готов к работе с Claude Code workflow. Сохраните изменения (`git commit`) или удалите установленную структуру и повторите сценарий для отладки.
