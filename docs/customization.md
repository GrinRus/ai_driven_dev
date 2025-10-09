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
- Для временного расширения прав создайте отдельный пресет и подключите его через `/docs-generate` или прямое редактирование файла.
- Если нужна строгая политика для production, добавьте список каталогов в `.claude/hooks/protect-prod.sh`.
- Автопроверка (`tests/test_settings_policy.py`) гарантирует, что критические команды находятся в `ask/deny`. Запускается через `scripts/ci-lint.sh`.

Проверить корректность настроек поможет `/docs-generate` — команда отобразит предупреждения, если права нарушают внутренние правила.

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
- Через слэш-команду `/conventions-set conventional`.
- Через CLI `python3 scripts/conventions_set.py conventional`.

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
python3 scripts/commit_msg.py --validate "$(cat "$1")" >/dev/null || {
  echo "❌ Commit message не соответствует активному режиму в config/conventions.json" 1>&2
  exit 1
}
HOOK
chmod +x .git/hooks/commit-msg
```

Hook проверит сообщение коммита на соответствие активной конвенции. Добавьте аналогичные обёртки для `pre-commit` или `pre-push`, если нужно.

## Переопределение слэш-команд и шаблонов

- Файлы команд находятся в `.claude/commands/*.md`. Добавьте блоки `## Примеры` и `## Типичные ошибки`, чтобы ускорить onboarding команды.
- Шаблоны документации (`docs/*.template.md`) поддерживают маркеры `${placeholder}`. Новые плейсхолдеры опишите в `docs/customization.md`, чтобы пользователи знали, откуда берутся значения.
- Для кастомной логики напишите Python/ shell-скрипты и свяжите их в командах через раздел «Command pipeline».

Пример override для `/feature-new`, который добавляет чеклист дизайна:

```markdown
```command
python3 scripts/feature_new.py --include-design-checklist
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
