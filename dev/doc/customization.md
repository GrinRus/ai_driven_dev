# Кастомизация Claude Code workflow

Документ описывает, как адаптировать настройки Claude Code workflow под процессы команды: от политик доступа и конвенций до поведения git-хуков и слэш-команд.

> Канонические файлы плагина лежат в `commands/`, `agents/`, `hooks/`, а шаблоны workspace — в `templates/aidd/`. Они разворачиваются командой `/feature-dev-aidd:aidd-init` и не перезаписывают пользовательские правки.
>
> Ticket — основной идентификатор фичи; при необходимости указывайте slug-hint (сохраняется в `aidd/docs/.active_feature`).

## Обновление шаблонов workspace

1. **Правим канонические шаблоны.** Изменения в PRD/plan/tasklist/research и конфигурации делайте в `templates/aidd/**`.
2. **Проверяем идемпотентность.** Запустите `/feature-dev-aidd:aidd-init` в тестовом workspace и убедитесь, что новые файлы появились, а существующие не перезаписались.
3. **Обновляем документацию и тесты.** Проверьте `README*`, `dev/doc/workflow.md`, smoke и unit-тесты, если менялось поведение.

## Содержание
- [.claude/settings.json](#claudesettingsjson)
- [aidd/config/conventions.json](#aiddconfigconventionsjson)
- [Git-хуки](#git-хуки)
- [Переопределение слэш-команд и шаблонов](#переопределение-слэш-команд-и-шаблонов)

## `.claude/settings.json`

Файл управляет доступом инструментов Claude Code (CLI-команды, git, shell). Пример:

```json
{
  "model": "sonnet",
  "permissions": {
    "allow": ["Read", "Write", "Edit", "Grep", "Glob", "Bash(git status:*)", "..."],
    "ask": ["Bash(git add:*)", "Bash(git commit:*)", "Bash(git push:*)"],
    "deny": ["Bash(curl:*)", "Read(./secrets/**)", "Write(./infra/prod/**)"]
  }
}
```

Рекомендации:
- `allow` оставляйте только для безопасных операций (например, чтение файлов). Для действий с побочными эффектами (`git commit`, `rm`) используйте `ask`.
- Для временного расширения прав создайте отдельный профиль в `presets.list` и переключитесь на него, обновив поле `presets.active` в `.claude/settings.json`.
- Автопроверка (`dev/tests/test_settings_policy.py`) гарантирует, что критические команды находятся в `ask/deny`. Запускается в CI (job `ci-lint`) или локально из репозитория.
- Хуки описаны в `hooks/hooks.json`, поэтому секцию `hooks` в `.claude/settings.json` оставляйте пустой, если не переопределяете поведение вручную.
- Скрипты в `hooks/*.sh` и `tools/*.sh` реализованы на Python, имеют shebang и запускаются напрямую; `CLAUDE_PLUGIN_ROOT` обязателен.
- Вернуть исходные настройки и хуки можно, сверив `.claude/settings.json` с примерами из `dev/doc/workflow.md` и текущими значениями в `hooks/hooks.json`.

Проверить корректность настроек можно тестом `python -m pytest dev/tests/test_settings_policy.py` (в репозитории) или общим прогоном CI lint.

## `aidd/config/conventions.json`

Формат файла:

```json
{
  "mode": "ticket-prefix",
  "ticket-prefix": {
    "branch": "feature/{ticket}",
    "commit": "{ticket}: {summary}"
  },
  "conventional": {
    "branch": "{type}/{scope}",
    "commit": "{type}({scope}): {summary}"
  },
  "mixed": {
    "branch": "feature/{ticket}/{type}/{scope}",
    "commit": "{ticket} {type}({scope}): {summary}"
  }
}
```

Как переключаться:
- Отредактируйте поле `commit.mode` в `aidd/config/conventions.json` (допустимые значения: `ticket-prefix`, `conventional`, `mixed`).

Для кастомизации добавьте собственное поле, например:

```json
  "ticket-prefix": {
    "branch": "feature/{ticket}-{workstream}",
    "commit": "{ticket}({workstream}): {summary}",
    "defaults": {
      "workstream": "core"
    }
  }
```

Значения из `defaults` будут автоматически подставлены, если пользователь не указал аргументы.

## Контекст и anchors

- Для короткого контекста используйте секцию `AIDD:CONTEXT_PACK` в tasklist (<= 20 lines / <= 1200 chars).
- Политика чтения: если есть `*.pack.yaml` — читать pack; иначе начинать с anchor‑секций.
- Рабочий набор хранится в `aidd/reports/context/latest_working_set.md` и читается первым, если файл существует.
- CLI‑вариант для компактного контекста: `${CLAUDE_PLUGIN_ROOT}/tools/context-pack.sh --ticket <TICKET> --agent <agent>` → `aidd/reports/context/<ticket>-<agent>.md`.

## Git-хуки

### `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh`

- Включает автоформатирование и выборочные тесты под ваш тест-раннер.
- Экспортируйте переменную `STRICT_TESTS=1`, чтобы падение тестов блокировало коммит:

```bash
export STRICT_TESTS=1
${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh
```

- Для пропуска форматирования используйте `SKIP_FORMAT=1`.
- Полный лог тестов пишется в `aidd/.cache/logs/format-and-test.<timestamp>.log`; режим вывода — `AIDD_TEST_LOG=summary|full`, хвост при падении — `AIDD_TEST_LOG_TAIL_LINES`.
- Для выбора профиля тестов создайте `aidd/.cache/test-policy.env`:

```bash
AIDD_TEST_PROFILE=fast   # fast|targeted|full|none
AIDD_TEST_TASKS=:checkout:test
AIDD_TEST_FILTERS=com.acme.CheckoutServiceTest
```

- Для повторного прогона при неизменном diff используйте `AIDD_TEST_FORCE=1`.
- Дефолтный профиль для автоматического запуска можно задать через `AIDD_TEST_PROFILE_DEFAULT` (например, fast на SubagentStop и targeted на Stop).
- Автозапуск по cadence: `.claude/settings.json → automation.tests.cadence` (`on_stop|checkpoint|manual`), `checkpointTrigger=progress`.

### Установка git-хуков

```bash
mkdir -p .git/hooks
cat > .git/hooks/commit-msg <<'HOOK'
#!/usr/bin/env bash
python3 - <<'PY' "$1"
import json
import re
import sys
from pathlib import Path

message = Path(sys.argv[1]).read_text(encoding="utf-8").strip()
mode = json.loads(Path("aidd/config/conventions.json").read_text(encoding="utf-8"))["commit"]["mode"]
patterns = {
    "ticket-prefix": r"^[A-Z]+\-\d+: .+",
    "conventional": r"^(feat|fix|chore|docs|test|refactor|perf|build|ci|revert)(\([\w\-\*]+\))?: .+",
    "mixed": r"^[A-Z]+\-\d+ (feat|fix|chore|docs|refactor|perf)(\([\w\-\*]+\))?: .+",
}
if not re.match(patterns.get(mode, r"^.+$"), message):
    print(f"Commit message не соответствует режиму {mode}", file=sys.stderr)
    sys.exit(1)
PY
HOOK
chmod +x .git/hooks/commit-msg
```

Hook проверит сообщение коммита на соответствие активной конвенции. Добавьте аналогичные обёртки для `pre-commit` или `pre-push`, если нужно. В репозитории `pre-commit` запускает `dev/repo_tools/ci-lint.sh`.

## Гейты и автотесты

### `aidd/config/gates.json`
- `feature_ticket_source` — путь к файлу с активным ticket (по умолчанию `aidd/docs/.active_ticket`); `feature_slug_hint_source` указывает, где хранить slug-хинт (`aidd/docs/.active_feature`).
- `prd_review` — описывает, как проверяется раздел `## PRD Review`: ветки, допустимые (`READY`) и блокирующие (`BLOCKED`) статусы, `allow_missing_report` (разрешить отсутствие отчёта `aidd/reports/prd/{ticket}.json`), `blocking_severities` (уровни findings, которые блокируют), `report_path` для кастомизации расположения отчёта.
- `tests_required` — режим проверки тестов: `disabled`, `soft` (только предупреждение), `hard` (блокирующая ошибка).
- `tests_gate` — правила сопоставления исходников и тестов (`source_roots`, `source_extensions`, `test_patterns`, `test_extensions`, `exclude_dirs`). `exclude_dirs` исключает тестовые директории (например, `test`, `tests`, `spec`, `__tests__`, `androidTest`), чтобы обновление тестов не требовало «тестов для тестов».
- `deps_allowlist` — включает предупреждения `lint-deps.sh` о зависимостях, отсутствующих в `aidd/config/allowed-deps.txt`.
- `qa.debounce_minutes` — минимальный интервал между запусками QA-гейта (0 — без debounce), полезно для снижения нагрузки на Stop/SubagentStop.

Комбинируйте настройки: например, для прототипов оставьте `tests_required="soft"`.

### Allowlist зависимостей
- Список хранится в `aidd/config/allowed-deps.txt`. Формат: один `group:artifact` на строку, поддерживаются комментарии (`#`).
- При `deps_allowlist=true` хук `lint-deps.sh` выводит `WARN`, если новая зависимость не в списке.
- Для монорепо можно хранить несколько списков и переключать их копированием (`cp aidd/config/allowed-deps.mobile.txt aidd/config/allowed-deps.txt`).

### Автотесты и альтернативные раннеры
- Автоматический запуск `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` можно временно отключить через `SKIP_AUTO_TESTS=1` (например, для длительных миграций).
- Для проектов с другим тест-раннером измените `automation.tests.runner` в `.claude/settings.json` (например, на `["npm", "test"]`, `["pytest"]`, `["go", "test"]`) и обновите `defaultTasks`.
- Если в монорепо разные стекы, заполните `moduleMatrix` (см. пример в `settings.json`), чтобы сопоставлять пути и команды тестов.
- Профили тестов управляются ключами `automation.tests.fastTasks`, `fullTasks`, `targetedTask` (по умолчанию `fullTasks` = `defaultTasks`).
- `aidd/.cache/test-policy.env` отключает reviewer gate для тестов и включает выбранный профиль; `AIDD_TEST_FORCE=1` заставляет запускать тесты несмотря на dedupe.

## Переопределение слэш-команд и шаблонов

- Файлы команд находятся в `commands/*.md`. Добавьте блоки `## Примеры` и `## Типичные ошибки`, чтобы ускорить onboarding команды.
- Шаблоны документации (`templates/aidd/docs/*/template.md`) поддерживают маркеры `${placeholder}`. Новые плейсхолдеры опишите в `dev/doc/customization.md`, чтобы пользователи знали, откуда берутся значения.
- Для кастомной логики напишите Python/ shell-скрипты и свяжите их в командах через раздел «Command pipeline».

## Миграция на agent-first
1. **Обновите промпты плагина.** Сверьте `agents/` и `commands/` с новыми требованиями (логирование команд, ссылки на артефакты).
2. **Обновите шаблоны документов.** Сравните свои `aidd/docs/prd/template.md`, `aidd/docs/tasklist/template.md`, `aidd/docs/research/template.md` с текущими версиями из `templates/aidd/docs/` и перенесите секции «Исходные артефакты», «Автоматизация и проверки», «Commands/Reports`. Это гарантирует, что аналитика/исследование/реализация записывают шаги, а не устные договорённости.
3. **Переинициализируйте активные фичи.** Прогоните `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket> --auto` и `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh --ticket <ticket>` для всех актуальных задач — отчёты и PRD будут соответствовать обновлённым шаблонам. Tasklist заполните новыми секциями `Reports/Commands` вручную или скриптом.
4. **Добавьте проверки.** Расширьте CI lint/`pre-commit` кастомными grep'ами (например, запрещайте «Ответ N» вне `aidd/docs/prd/*.md`) и убедитесь, что ваши override-команды по-прежнему перечисляют все используемые CLI.

## Частые сценарии
- **Сделать предварительный прогон без изменений.** Добавьте флаг `--dry-run` (см. задачу Wave 1) или временно закомментируйте команду записи файлов в скрипте.
- **Работа в монорепозиториях с различными tooling.** Создайте несколько конфигураций в `aidd/config/` и переключайте их простым копированием (`cp aidd/config/conventions.android.json aidd/config/conventions.json`).
- **Отключить часть функциональности.** Например, временно отключите гейты в `aidd/config/gates.json`, если они мешают быстрым экспериментам.

Поддерживайте этот документ в актуальном состоянии и добавляйте успешные примеры override — это упростит адаптацию workflow под новые команды.
