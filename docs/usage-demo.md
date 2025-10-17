# Демонстрация использования CLI `claude-workflow`

Этот документ показывает, как развернуть Claude Code workflow через новую CLI-команду `claude-workflow init` на минимальном Gradle-монорепозитории. В примере используется каталог `demo-monorepo`, но те же шаги применимы к любому Java/Kotlin проекту.

## Цель сценария
- развернуть шаблон всего за один запуск скрипта;
- понять, какие файлы и настройки добавляются;
- проверить, что выборочные тесты и хуки работают сразу после установки;
- пройти многошаговый цикл `/idea-new → claude-workflow research → /plan-new → /tasks-new → /implement → /review` и увидеть работу гейтов (workflow, research, миграции, тесты).

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

> Нет `uv`? Замените на `pipx install git+https://github.com/GrinRus/ai_driven_dev.git`. Перед повторной установкой убедитесь, что удалили старый `.claude/` или добавьте `--force` к команде `claude-workflow init`. При обновлениях используйте `claude-workflow upgrade` (с `--force` для перезаписи изменённых файлов). Локальный скрипт по-прежнему доступен как резервный вариант.

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

> Нужно обновить только `.claude/**` без полного `init`? Выполните `claude-workflow sync` (дополнительно можно указать `--include claude-presets`, `--include templates/git-hooks` и т.п.; чтобы забрать payload из GitHub Releases, добавьте `--release latest` или конкретный тег). Для локального dogfooding самого payload в репозитории воспользуйтесь `scripts/bootstrap-local.sh --force`, он развернёт артефакты в `.dev/.claude-example/`.

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
   - Агент начнёт с `Вопрос 1: …`. Отвечайте на каждый пункт строго в формате `Ответ 1: …`, `Ответ 2: …`, пока статус не станет READY и раздел `## Диалог analyst` не заполнится.
   - После генерации PRD выполните `claude-workflow analyst-check --feature demo-checkout`. Если проверка сообщает о пропущенных ответах или статусе BLOCKED, вернитесь к агенту и дополните сведения.
2. Соберите исследование: `claude-workflow research --feature demo-checkout --paths "service-checkout:service-payments"` подготовит `reports/research/demo-checkout-*.json`, после чего запустите `/researcher demo-checkout` и обновите `docs/research/demo-checkout.md` до `Status: reviewed`.
3. Постройте план и чеклисты: `/plan-new demo-checkout` сформирует план, а `/tasks-new demo-checkout` перенесёт его в `docs/tasklist/demo-checkout.md`.
4. При необходимости включите дополнительные гейты в `config/gates.json` и подготовьте связанные артефакты: миграции, OpenAPI-файлы, расширенные тесты.
5. Запустите `/implement demo-checkout` — агент будет идти малыми шагами, а `.claude/hooks/format-and-test.sh` автоматически выполнит форматирование и выборочные тесты (отключаемо `SKIP_AUTO_TESTS=1`).
6. Фиксируйте прогресс в git (`git commit -m "DEMO-1: add rule engine"`), пока `docs/tasklist/demo-checkout.md` не будет закрыт и тесты не станут зелёными.

## Проверка результата в Claude Code
1. Создайте ветку `git checkout -b feature/DEMO-1`, соблюдая выбранную конвенцию.
2. Запустите `/idea-new`, `/plan-new`, `/tasks-new` и убедитесь, что `docs/` и `docs/tasklist/<slug>.md` обновились.
3. Проверьте гейты: `gate-workflow` пропускает правки только после появления PRD/плана/tasklist (`docs/tasklist/<slug>.md`) и отчёта Researcher; при включённых флагах `api_contract`, `db_migration`, `tests_required` появятся подсказки о недостающих артефактах.
4. После правок убедитесь, что `.claude/hooks/format-and-test.sh` запускается автоматически; при необходимости используйте `SKIP_AUTO_TESTS=1` для паузы, `FORMAT_ONLY=1` или `TEST_SCOPE=":module:test"` для точечной настройки и запускайте скрипт вручную при сложных изменениях.
5. Зафиксируйте изменения (`git commit -m "DEMO-1: implement rule engine"`) и вызовите `/review demo-checkout`, чтобы закрыть чеклист и убедиться, что режим коммитов синхронизирован.

## Работа с пресетами фич

После установки в корне появляется каталог `claude-presets/` с YAML-манифестами для каждого шага фичи. Пресеты используются двумя способами:

1. **Через CLI.** Выполните `claude-workflow preset feature-prd --feature checkout-discounts`, чтобы развернуть демо-PRD. По мере необходимости добавляйте `feature-plan` и `feature-impl`, а расширенные пресеты (`feature-design`, `feature-release`) доступны в `claude-presets/advanced/`. CLI автоматически подставит цели из `docs/usage-demo.md` и задачи из `doc/backlog.md (Wave 7)`. Резервный сценарий — `bash init-claude-workflow.sh --preset …`.
2. **Внутри Claude Code.** Добавьте файл пресета в контекст (например, `claude-presets/feature-plan.yaml`) или настройте кнопку в интерфейсе — описание находится в `claude-workflow-extensions.patch`.

Текущее покрытие:

| Пресет | Результат | Файл | Расположение |
| --- | --- | --- | --- |
| `claude-workflow research` | Отчёт Researcher, targets и context JSON | `docs/research/<slug>.md`, `reports/research/<slug>-*.json` | CLI `claude-workflow` |
| `feature-prd` | Черновик PRD и метрики успеха | `docs/prd/<slug>.prd.md` | `claude-presets/` |
| `feature-plan` | План реализации и контрольные точки | `docs/plan/<slug>.md` | `claude-presets/` |
| `feature-impl` | Секция чеклистов в tasklist | `docs/tasklist/<slug>.md` | `claude-presets/` |
| `feature-design` | Архитектура/ADR для фичи | `docs/design/<slug>.md` | `claude-presets/advanced/` |
| `feature-release` | Запись в релизных заметках | `docs/release-notes.md` | `claude-presets/advanced/` |

Скрипт `scripts/smoke-workflow.sh` демонстрирует полный E2E: он разворачивает шаблон, активирует фичу `demo-checkout`, прогоняет базовые пресеты (`feature-prd`, `feature-plan`, `feature-impl`) и проверяет, что гейт `gate-workflow.sh` начинает пропускать правки только после появления PRD/плана/тасклиста.

## Релизный цикл CLI
1. Обновите версию в `pyproject.toml` и соответствующий блок в `CHANGELOG.md`.
2. Запустите `scripts/ci-lint.sh` и `claude-workflow smoke`, зафиксируйте изменения и сделайте `git push` в `main`. Workflow `autotag.yml` создаст тег `v<версия>`, если его ещё нет.
3. Тег запустит `release.yml`: пакет соберётся (`python -m build`), артефакты попадут в GitHub Release и в артефакты workflow.
4. Убедитесь, что релиз появился на GitHub и скачивание wheel/zip работает. Пользователи ставят CLI напрямую через `uv tool install ... --from git+https://github.com/GrinRus/ai_driven_dev.git[@tag]` или `pipx install git+https://github.com/GrinRus/ai_driven_dev.git`.
5. При необходимости повторите сборку, обновив версию и перезапустив цикл (тег → release).

## Частые вопросы
- **Запуск скрипта терпит неудачу:** проверьте вывод проверки зависимостей и убедитесь, что Gradle доступен в PATH.
- **Тесты не стартуют:** убедитесь, что `./gradlew` исполняемый (`chmod +x gradlew`) и что скрипт имеет права на запуск.
- **Файлы уже существуют:** добавьте `--force`, но предварительно сохраните изменения в git или сделайте резервную копию.
- **Нужно повторно прогнать установку:** скрипт безопасно перезаписывает артефакты. Чтобы увидеть только изменения, используйте `git diff`.

Теперь демо-проект готов к работе с Claude Code workflow. Сохраните изменения (`git commit`) или удалите установленную структуру и повторите сценарий для отладки.
