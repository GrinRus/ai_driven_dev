# Кастомизация Claude Code workflow

Документ описывает, как адаптировать настройки Claude Code workflow под процессы команды: от политик доступа и конвенций до поведения git-хуков и слэш-команд.

## Содержание
- [.claude/settings.json](#.claudesettingsjson)
- [config/conventions.json](#configconventionsjson)
- [Git-хуки](#git-хуки)
- [Переопределение слэш-команд и шаблонов](#переопределение-слэш-команд-и-шаблонов)
- [Расширенные пресеты для команд](#расширенные-пресеты-для-команд)

## `.claude/settings.json`

Файл управляет доступом инструментов Claude Code (CLI-команды, git, shell). Пример:

```json
{
  "model": "sonnet",
  "permissions": {
    "allow": ["Read", "Write", "Edit", "Grep", "Glob", "Bash(git status:*)", "..."],
    "ask": ["Bash(git add:*)", "Bash(git commit:*)", "Bash(git push:*)"],
    "deny": ["Bash(curl:*)", "Read(./secrets/**)", "Write(./infra/prod/**)"]
  },
  "hooks": {
    "PreToolUse": [{ "matcher": "Write|Edit", "hooks": [{ "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/protect-prod.sh" }] }],
    "PostToolUse": [{ "matcher": "Write|Edit", "hooks": [{ "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/format-and-test.sh" }] }]
  }
}
```

Рекомендации:
- `allow` оставляйте только для безопасных операций (например, чтение файлов). Для действий с побочными эффектами (`git commit`, `rm`) используйте `ask`.
- Для временного расширения прав создайте отдельный пресет и переключитесь на него, обновив поле `presets.active` в `.claude/settings.json` или запустив `bash init-claude-workflow.sh --preset <name>`.
- Если нужна строгая политика для production, добавьте список каталогов в `.claude/hooks/protect-prod.sh`.
- Автопроверка (`tests/test_settings_policy.py`) гарантирует, что критические команды находятся в `ask/deny`. Запускается через `scripts/ci-lint.sh`.

Проверить корректность настроек можно тестом `python -m pytest tests/test_settings_policy.py` или общим `scripts/ci-lint.sh`.

## `config/conventions.json`

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
- Отредактируйте поле `commit.mode` в `config/conventions.json` (допустимые значения: `ticket-prefix`, `conventional`, `mixed`).

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

## Git-хуки

### `.claude/hooks/format-and-test.sh`

- Включает автоформатирование (Spotless/ktlint) и выборочные тесты Gradle.
- Экспортируйте переменную `STRICT_TESTS=1`, чтобы падение тестов блокировало коммит:

```bash
export STRICT_TESTS=1
.claude/hooks/format-and-test.sh
```

- Для пропуска форматирования используйте `SKIP_FORMAT=1`.
- Логи вывода можно перенаправить в файл: `LOG_FILE=.claude/logs/format.log`.

### `.claude/hooks/protect-prod.sh`

Шаблон блокирует изменения в `infra/prod`, `.secrets`, `config/prod`. Добавьте собственные каталоги:

```bash
PROTECTED_PATHS+=("services/billing/prod" "terraform/prod")
```

При необходимости разрешите конкретные файлы:

```bash
ALLOWED_EXCEPTIONS+=("infra/prod/README.md")
```

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
mode = json.loads(Path("config/conventions.json").read_text(encoding="utf-8"))["commit"]["mode"]
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

Hook проверит сообщение коммита на соответствие активной конвенции. Добавьте аналогичные обёртки для `pre-commit` или `pre-push`, если нужно.

## Гейты и автотесты

### `config/gates.json`
- `feature_slug_source` — путь к файлу с активной фичей (по умолчанию `docs/.active_feature`).
- `api_contract` / `db_migration` — включают или отключают соответствующие гейты. При `false` скрипты `gate-api-contract.sh` и `gate-db-migration.sh` завершаются сразу.
- `tests_required` — режим проверки тестов: `disabled`, `soft` (только предупреждение), `hard` (блокирующая ошибка).
- `deps_allowlist` — включает предупреждения `lint-deps.sh` о зависимостях, отсутствующих в `config/allowed-deps.txt`.

Комбинируйте настройки: например, для прототипов отключите `api_contract` и `db_migration`, оставив `tests_required="soft"`.

### Allowlist зависимостей
- Список хранится в `config/allowed-deps.txt`. Формат: один `group:artifact` на строку, поддерживаются комментарии (`#`).
- При `deps_allowlist=true` хук `lint-deps.sh` выводит `WARN`, если новая зависимость не в списке.
- Для монорепо можно хранить несколько списков и переключать их копированием (`cp config/allowed-deps.mobile.txt config/allowed-deps.txt`).

### Автотесты и альтернативные раннеры
- Автоматический запуск `.claude/hooks/format-and-test.sh` можно временно отключить через `SKIP_AUTO_TESTS=1` (например, для длительных миграций).
- Для проектов без Gradle измените `automation.tests.runner` в `.claude/settings.json` (например, на `["npm", "test"]` или `["pytest"]`) и обновите `defaultTasks`.
- Если в монорепо разные стекы, заполните `moduleMatrix` (см. пример в `settings.json`), чтобы сопоставлять пути и команды тестов.

## Переопределение слэш-команд и шаблонов

- Файлы команд находятся в `.claude/commands/*.md`. Добавьте блоки `## Примеры` и `## Типичные ошибки`, чтобы ускорить onboarding команды.
- Шаблоны документации (`docs/*.template.md`) поддерживают маркеры `${placeholder}`. Новые плейсхолдеры опишите в `docs/customization.md`, чтобы пользователи знали, откуда берутся значения.
- Для кастомной логики напишите Python/ shell-скрипты и свяжите их в командах через раздел «Command pipeline».

Пример override для `/idea-new`, который добавляет дополнительный чеклист дизайна через пресет `feature-design`:

```markdown
```command
!`bash init-claude-workflow.sh --preset feature-design --feature "$1"`
```
```

## Расширенные пресеты для команд

| Команда | Особенности | Рекомендации |
| --- | --- | --- |
| Backend | Используйте `mixed` режим и строгие тесты | `STRICT_TESTS=1`, `ticket-prefix` с workstream |
| Mobile | Подключите Spotless и KtLint, разрешите Android задачи (`:testDebugUnitTest`) | Убедитесь, что `ANDROID_SDK_ROOT` доступен |
| Data/ML | Оставьте форматирование мягким, добавьте проверку ноутбуков | Расширьте `PROTECTED_PATHS` для продовых моделей |

## Частые сценарии
- **Сделать предварительный прогон без изменений.** Добавьте флаг `--dry-run` (см. задачу Wave 1) или временно закомментируйте команду записи файлов в скрипте.
- **Работа в монорепозиториях с различными tooling.** Создайте несколько конфигураций в `config/` и переключайте их простым копированием (`cp config/conventions.android.json config/conventions.json`).
- **Отключить часть функциональности.** Например, удалите `.claude/hooks/protect-prod.sh` из `settings.json`, если ограничения мешают прототипированию.

Поддерживайте этот документ в актуальном состоянии и добавляйте успешные примеры override — это упростит адаптацию workflow под новые команды.
