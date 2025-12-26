# Кастомизация Claude Code workflow

Документ описывает, как адаптировать настройки Claude Code workflow под процессы команды: от политик доступа и конвенций до поведения git-хуков и слэш-команд.

> Все служебные файлы (команды, агенты, хуки, шаблоны, конфиги) лежат в payload каталога `src/claude_workflow_cli/data/payload/` и разворачиваются из него через `claude-workflow init` / `claude-workflow upgrade`. Для точечной пересборки используйте `claude-workflow sync` (например, `claude-workflow sync --include .claude --include .claude-plugin --include claude-presets`; чтобы подтянуть последнюю версию из GitHub Releases, укажите `--release latest` или конкретный тег `--release v0.2.0`). CLI сверяет контрольные суммы из `manifest.json` и выводит diff перед синхронизацией. Для локального dogfooding без установки CLI предусмотрен скрипт `scripts/bootstrap-local.sh`, который копирует payload в `.dev/.claude-example/`.
>
> По умолчанию релизы скачиваются из `ai-driven-dev/ai_driven_dev`; переопределите репозиторий переменной `CLAUDE_WORKFLOW_RELEASE_REPO` или явно укажите `--release owner/repo@tag`. Кеш скачанных архивов хранится в `~/.cache/claude-workflow` (`CLAUDE_WORKFLOW_CACHE` или `--cache-dir`). Чтобы избежать лимитов GitHub API, задайте `GH_TOKEN` / `GITHUB_TOKEN`.
>
> Ticket — основной идентификатор фичи; при необходимости указывайте slug-hint (сохраняется в `aidd/docs/.active_feature`).

## Синхронизация payload

> Repo-only: `scripts/sync-payload.sh` и `tools/check_payload_sync.py` находятся в корне репозитория и не входят в установленный payload.

1. **Правим только payload.** Любые изменения `.claude/`, `.claude-plugin/`, `aidd/**`, `templates/`, скриптов и агентов в root должны приходить из `src/claude_workflow_cli/data/payload`. Перед редактированием разверните содержание в корень командой `scripts/sync-payload.sh --direction=to-root`.
2. **Фиксируем изменения назад.** После правок выполните `scripts/sync-payload.sh --direction=from-root` и закоммитьте обе стороны. Скрипт поддерживает `--paths` и `--dry-run` для точечного сравнения.
3. **Проверяем контрольные суммы.** Запустите `python3 tools/check_payload_sync.py` (или `pre-commit run payload-sync-check`) — он сравнит хэши файлов payload и runtime snapshot. Любое расхождение блокирует CI (job `ci-lint` в GitHub Actions).
4. **Dogfooding без установки.** Для проверки payload в стороннем проекте используйте `scripts/bootstrap-local.sh --payload src/claude_workflow_cli/data/payload --target .dev/.claude-example --force`, а не ручное редактирование `.claude` в репозитории.

Соблюдайте эти шаги перед публикацией релиза, чтобы `uv tool install claude-workflow-cli` всегда получал последнюю версию скриптов.

## Содержание
- [.claude/settings.json](#claudesettingsjson)
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
    "PreToolUse": [{ "matcher": "Write|Edit", "hooks": [{ "type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT:-./aidd}\"/hooks/gate-workflow.sh" }] }],
    "PostToolUse": [{ "matcher": "Write|Edit", "hooks": [{ "type": "command", "command": "\"${CLAUDE_PLUGIN_ROOT:-./aidd}\"/hooks/format-and-test.sh" }] }]
  }
}
```

Рекомендации:
- `allow` оставляйте только для безопасных операций (например, чтение файлов). Для действий с побочными эффектами (`git commit`, `rm`) используйте `ask`.
- Для временного расширения прав создайте отдельный пресет и переключитесь на него, обновив поле `presets.active` в `.claude/settings.json` или вызвав `claude-workflow preset <name>`.
- Автопроверка (`tests/test_settings_policy.py`) гарантирует, что критические команды находятся в `ask/deny`. Запускается в CI (job `ci-lint`) или локально из репозитория.
- Вернуть исходные настройки и хуки можно командой `claude-workflow sync` (по умолчанию синхронизирует `.claude/**` и `.claude-plugin/**`; добавьте `--include claude-presets`, чтобы подтянуть пресеты и `--release <tag|latest>`, если нужна версия из GitHub Releases).

Проверить корректность настроек можно тестом `python -m pytest tests/test_settings_policy.py` (в репозитории) или общим прогоном CI lint.

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

### `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh`

- Включает автоформатирование (Spotless/ktlint) и выборочные тесты Gradle.
- Экспортируйте переменную `STRICT_TESTS=1`, чтобы падение тестов блокировало коммит:

```bash
export STRICT_TESTS=1
${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh
```

- Для пропуска форматирования используйте `SKIP_FORMAT=1`.
- Логи вывода можно перенаправить в файл: `LOG_FILE=aidd/reports/logs/format.log`.

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
- `feature_ticket_source` — путь к файлу с активным ticket (по умолчанию `aidd/docs/.active_ticket`); `feature_slug_hint_source` указывает, где хранить slug-хинт (`aidd/docs/.active_feature`).
- `prd_review` — описывает, как проверяется раздел `## PRD Review`: ветки, допустимые (`READY`) и блокирующие (`BLOCKED`) статусы, `allow_missing_report` (разрешить отсутствие отчёта `reports/prd/{ticket}.json`), `blocking_severities` (уровни findings, которые блокируют), `report_path` для кастомизации расположения отчёта.
- `tests_required` — режим проверки тестов: `disabled`, `soft` (только предупреждение), `hard` (блокирующая ошибка).
- `deps_allowlist` — включает предупреждения `lint-deps.sh` о зависимостях, отсутствующих в `config/allowed-deps.txt`.

Комбинируйте настройки: например, для прототипов оставьте `tests_required="soft"`.

### Allowlist зависимостей
- Список хранится в `config/allowed-deps.txt`. Формат: один `group:artifact` на строку, поддерживаются комментарии (`#`).
- При `deps_allowlist=true` хук `lint-deps.sh` выводит `WARN`, если новая зависимость не в списке.
- Для монорепо можно хранить несколько списков и переключать их копированием (`cp config/allowed-deps.mobile.txt config/allowed-deps.txt`).

### Автотесты и альтернативные раннеры
- Автоматический запуск `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh` можно временно отключить через `SKIP_AUTO_TESTS=1` (например, для длительных миграций).
- Для проектов без Gradle измените `automation.tests.runner` в `.claude/settings.json` (например, на `["npm", "test"]` или `["pytest"]`) и обновите `defaultTasks`.
- Если в монорепо разные стекы, заполните `moduleMatrix` (см. пример в `settings.json`), чтобы сопоставлять пути и команды тестов.

## Переопределение слэш-команд и шаблонов

- Файлы команд находятся в `aidd/commands/*.md`. Добавьте блоки `## Примеры` и `## Типичные ошибки`, чтобы ускорить onboarding команды.
- Шаблоны документации (`aidd/docs/*.template.md`) поддерживают маркеры `${placeholder}`. Новые плейсхолдеры опишите в `aidd/docs/customization.md`, чтобы пользователи знали, откуда берутся значения.
- Для кастомной логики напишите Python/ shell-скрипты и свяжите их в командах через раздел «Command pipeline».

Пример override для `/idea-new`, который добавляет дополнительный чеклист дизайна через пресет `feature-design`:

```markdown
```command
!`claude-workflow preset feature-design --ticket "$1"`
```
```

## Миграция на agent-first
1. **Синхронизируйте payload и промпты (repo-only).** Выполните `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py`, затем скопируйте обновлённые `aidd/agents|commands` и `aidd/prompts/en/**`, чтобы описания ролей и allowed-tools отражали новые требования (логирование команд, ссылки на артефакты).
2. **Обновите шаблоны документов.** Сравните свои `aidd/docs/prd.template.md`, `aidd/docs/tasklist.template.md`, `aidd/docs/templates/research-summary.md` с текущими версиями и перенесите секции «Исходные артефакты», «Автоматизация и проверки», «Commands/Reports`. Это гарантирует, что аналитика/исследование/реализация записывают шаги, а не устные договорённости.
3. **Переинициализируйте активные фичи.** Прогоните `claude-workflow research --ticket <ticket> --auto` и `claude-workflow analyst-check --ticket <ticket>` для всех актуальных задач — отчёты и PRD будут соответствовать обновлённым шаблонам. Tasklist заполните новыми атрибутами (reports/commands) вручную или скриптом.
4. **Добавьте проверки.** Расширьте CI lint/`pre-commit` кастомными grep'ами (например, запрещайте «Ответ N» вне `aidd/docs/prd/*.md`) и убедитесь, что ваши override-команды по-прежнему перечисляют все используемые CLI.

## Расширенные пресеты для команд

| Команда | Особенности | Рекомендации |
| --- | --- | --- |
| Backend | Используйте `mixed` режим и строгие тесты | `STRICT_TESTS=1`, `ticket-prefix` с workstream |
| Mobile | Подключите Spotless и KtLint, разрешите Android задачи (`:testDebugUnitTest`) | Убедитесь, что `ANDROID_SDK_ROOT` доступен |
| Data/ML | Оставьте форматирование мягким, добавьте проверку ноутбуков | Расширьте правила в `config/gates.json` для продовых моделей |

## Частые сценарии
- **Сделать предварительный прогон без изменений.** Добавьте флаг `--dry-run` (см. задачу Wave 1) или временно закомментируйте команду записи файлов в скрипте.
- **Работа в монорепозиториях с различными tooling.** Создайте несколько конфигураций в `config/` и переключайте их простым копированием (`cp config/conventions.android.json config/conventions.json`).
- **Отключить часть функциональности.** Например, временно отключите гейты в `config/gates.json`, если они мешают быстрым экспериментам.

Поддерживайте этот документ в актуальном состоянии и добавляйте успешные примеры override — это упростит адаптацию workflow под новые команды.
