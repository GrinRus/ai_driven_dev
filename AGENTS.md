# AGENTS (Repo development guide)

Этот файл — единая dev‑документация репозитория. Все dev‑правила и шаблоны живут здесь.

## Репозиторий и структура
- Runtime (плагин): `commands/`, `agents/`, `hooks/`, `tools/`, `config/`, `.claude-plugin/`.
- Workspace‑шаблоны: `templates/aidd/` (копируются в `./aidd` через `/feature-dev-aidd:aidd-init`).
- Тесты: `tests/`.
- Repo tools: `tests/repo_tools/`.
- Backlog: `backlog.md` (корень).
- User‑артефакты: `aidd/**` (docs/reports/config).

## Архитектура путей (plugin cache vs workspace)
- Плагин копируется в cache Claude Code: записи в `${CLAUDE_PLUGIN_ROOT}` недопустимы.
- Рабочий root всегда workspace (`./aidd`); только туда пишем `docs/`, `reports/`, `config/`.
- `${CLAUDE_PLUGIN_ROOT}` используется только для чтения ресурсов плагина (hooks/tools/templates).
- CWD хуков не гарантирован; корень проекта вычисляется из payload (cwd/workspace), без fallback на plugin root.

## Быстрые проверки (repo‑only)
- Полный линт + unit‑тесты: `tests/repo_tools/ci-lint.sh`.
- E2E smoke: `tests/repo_tools/smoke-workflow.sh`.
- Дополнительно (если нужно): `python3 -m unittest discover -s tests -t .`.

## Workflow (кратко)
Канонические стадии: `idea → research → plan → review-plan → review-prd → tasklist → implement → review → qa`.

Ключевые команды:
- Идея: `/feature-dev-aidd:idea-new <ticket> [slug-hint]` → PRD + `analyst`.
- Research: `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket> --auto --deep-code` → `/feature-dev-aidd:researcher <ticket>`.
- План: `/feature-dev-aidd:plan-new <ticket>`.
- Review‑spec (plan + PRD): `/feature-dev-aidd:review-spec <ticket>`.
- Тасклист: `/feature-dev-aidd:tasks-new <ticket>`.
- Реализация: `/feature-dev-aidd:implement <ticket>` (гейтит `gate-workflow`, auto `format-and-test`).
- Ревью: `/feature-dev-aidd:review <ticket>`.
- QA: `/feature-dev-aidd:qa <ticket>` → отчёт `aidd/reports/qa/<ticket>.json`.

Agent‑first правило: сначала читаем артефакты (`aidd/docs/**`, `aidd/reports/**`), запускаем разрешённые команды (`rg`, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh`, тесты), затем задаём вопросы пользователю.

## Кастомизация (минимум)
- `.claude/settings.json`: permissions и automation/tests cadence (`on_stop|checkpoint|manual`).
- `aidd/config/gates.json`:
  - `feature_ticket_source`, `feature_slug_hint_source`
  - `prd_review`, `plan_review`, `researcher`, `analyst`
  - `tests_required` (`disabled|soft|hard`), `tests_gate`
  - `deps_allowlist`
  - `qa.debounce_minutes`
  - `tasklist_progress`
- Важные env:
  - `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`
  - `AIDD_TEST_PROFILE`, `AIDD_TEST_TASKS`, `AIDD_TEST_FILTERS`, `AIDD_TEST_FORCE`

## Prompt versioning
- Semver: `MAJOR.MINOR.PATCH`.
- `source_version` всегда равен `prompt_version` для RU.
- Команды:
  - `python3 tests/repo_tools/prompt-version bump --root <workflow-root> --prompts <name> --kind agent|command --lang ru --part <major|minor|patch>`
  - `python3 tests/repo_tools/lint-prompts.py --root <workflow-root>`

## Reports format (MVP)
- Naming:
  - Research context: `aidd/reports/research/<ticket>-context.json` + `*.pack.yaml|*.pack.toon`
  - Research targets: `aidd/reports/research/<ticket>-targets.json`
  - QA: `aidd/reports/qa/<ticket>.json` + pack
  - PRD review: `aidd/reports/prd/<ticket>.json` + pack
  - Reviewer marker: `aidd/reports/reviewer/<ticket>.json`
  - Tests log: `aidd/reports/tests/<ticket>.jsonl`
- Pack‑first: читать pack (yaml/toon) если есть, иначе JSON.
- Header (минимум): `ticket`, `slug|slug_hint`, `generated_at`, `status`, `summary` (если есть), `tests_summary` (QA).
- Determinism: стабильная сериализация, stable‑truncation, стабильные `id`.
- Columnar формат: `cols` + `rows`.
- Budgets (пример):
  - research context pack: total <= 1200 chars, matches<=20, reuse<=8, call_graph<=30
  - QA pack: findings<=20, tests_executed<=10
  - PRD pack: findings<=20, action_items<=10
- Патчи (опционально): RFC6902 в `aidd/reports/<type>/<ticket>.patch.json`.
- Pack‑only/field filters: `AIDD_PACK_ONLY`, `AIDD_PACK_ALLOW_FIELDS`, `AIDD_PACK_STRIP_FIELDS`.

## Report stats (auto)
<!-- report-stats:start -->
No reports found. Run `python3 tests/repo_tools/report_stats.py --write` after reports exist.
<!-- report-stats:end -->

## Release checklist (сжато)
- Обновить `README.md`/`README.en.md` и `AGENTS.md` при изменении поведения.
- Закрыть задачи в `backlog.md`, создать следующую волну при необходимости.
- Прогнать `tests/repo_tools/ci-lint.sh` и `tests/repo_tools/smoke-workflow.sh`.
- Проверить prompt‑versioning и prompt‑lint (см. выше).
- Убедиться, что dev‑only артефакты не попали в дистрибутив.
- Обновить `CHANGELOG.md` (и release notes при необходимости).

## Migration (marketplace‑only → `aidd/`)
1. Зафиксируйте локальные изменения.
2. В рабочем проекте удалите legacy‑снапшоты: `.claude/`, `.claude-plugin/`, `config/`, `docs/`, `templates/`, `tools/` (если это старые копии). Не трогайте каталоги плагина в этом репозитории.
3. Установите плагин через marketplace и запустите `/feature-dev-aidd:aidd-init`.
4. Перенесите артефакты в `aidd/docs` и `aidd/reports`.
5. Прогоните `tests/repo_tools/smoke-workflow.sh`.

## ADR: Workspace в `aidd/`
- Решение: рабочие артефакты живут в `./aidd`, плагин — в корне репозитория.
- Init идемпотентен и не перезаписывает пользовательские файлы.
- Smoke/pytest используют текущий git checkout.

## Prompt templates

### Agent template
```md
---
name: {{NAME}}
description: {{DESCRIPTION}}
lang: {{LANG}}
prompt_version: {{PROMPT_VERSION}}
source_version: {{SOURCE_VERSION}}
tools: {{TOOLS}}
model: inherit
---

## Контекст
Кратко опишите роль агента, его цель и ключевые ограничения. Ссылайтесь на документы формата `@aidd/docs/...`. Подчеркните agent-first подход: какие данные агент обязан собрать сам и какие команды он запускает до обращения к пользователю.

## Входные артефакты
- `aidd/docs/prd/<ticket>.prd.md` — пример обязательного входа. Укажите, какие файлы требуются и что делать, если их нет.
- Перечислите остальные артефакты (plan, tasklist, отчёты, `aidd/reports/*.json`) и отметьте условия (READY/BLOCKED). Обязательно опишите, как агент ищет ссылки (например, `rg <ticket> aidd/docs/**`, поиск по ADR, использование slug-hint из `aidd/docs/.active_feature`).

## Автоматизация
- Перечислите гейты (`gate-*`), хуки и переменные (`SKIP_AUTO_TESTS`, `TEST_SCOPE`), которые агент обязан учитывать.
- Укажите разрешённые CLI-команды (`<test-runner> …`, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh …`, `rg …`) и как агент должен логировать вывод/пути. Опишите, как реагировать на автозапуск `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` и когда использовать ручные команды.

## Пошаговый план
1. Распишите действия агента (чтение артефактов, запуск `rg`/`<test-runner>`, обновление файлов, обращение к другим агентам).
2. Каждое действие должно приводить к измеримому результату (например, обновлённый файл, лог команды, ссылка на отчёт).
3. Укажите, что вопросы пользователю допустимы только после перечисления проверенных артефактов и должны включать формат ответа.

## Fail-fast и вопросы
- Укажите условия, при которых агент должен остановиться и запросить данные у пользователя (например, отсутствует PRD/plan). Перед вопросом перечислите, что уже проверено.
- Формат вопросов:
  ```
  Вопрос N (Blocker|Clarification): ...
  Зачем: ...
  Варианты: A) ... B) ...
  Default: ...
  ```

## Формат ответа
- Всегда начинайте с `Checkbox updated: ...`.
- Далее укажите `Status: ...`, `Artifacts updated: ...`, `Next actions: ...` и ссылки на файлы/команды.
- Если статус BLOCKED, перечислите конкретные вопросы, список проверенных артефактов и следующие шаги.
```

### Command template
```md
---
description: {{DESCRIPTION}}
argument-hint: {{ARGUMENT_HINT}}
lang: {{LANG}}
prompt_version: {{PROMPT_VERSION}}
source_version: {{SOURCE_VERSION}}
allowed-tools: {{ALLOWED_TOOLS}}
model: inherit
---

## Контекст
Опишите назначение команды, связь с агентами и обязательные предварительные условия (активный ticket, готовые артефакты и т.д.). Уточните, что команда следует agent-first принципам: собирает данные из репозитория и запускает разрешённые CLI автоматически, а вопросы пользователю задаёт только при отсутствии информации.

## Входные артефакты
- Перечислите файлы/репорты (`aidd/docs/prd/*.md`, `aidd/docs/research/*.md`, `aidd/reports/*.json`, slug-hint в `aidd/docs/.active_feature`) и укажите, как команда находит их (например, `rg <ticket>`).
- Отметьте, что делать при отсутствии входа (остановиться с BLOCKED, попросить запустить другую команду) и какие команды нужно выполнить, прежде чем просить пользователя о данных.

## Когда запускать
- Опишите стадии workflow, в которых команда применяется, и кто инициирует запуск.
- Уточните ограничения (например, только после `/feature-dev-aidd:review-spec` или при статусе READY).

## Автоматические хуки и переменные
- Перечислите хуки/гейты и команды, запускаемые во время выполнения (`${CLAUDE_PLUGIN_ROOT}/tools/set-active-feature.sh`, `${CLAUDE_PLUGIN_ROOT}/tools/research.sh`, `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh`, `<test-runner> <args>`, `rg`).
- Опишите переменные окружения (`SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`) и требования к логам/ссылкам на вывод команд.

## Что редактируется
- Укажите файлы/директории, которые команда должна обновлять (например, `aidd/docs/tasklist/<ticket>.md`, `src/**`), и какие артефакты нужно ссылать в ответе (diff, отчёты, логи команд).
- Добавьте ссылки на шаблоны и требования к структуре правок, включая хранение команд и источников данных.

## Пошаговый план
1. Распишите последовательность действий команды (вызов саб-агентов, запуск скриптов, обновление артефактов).
2. Добавьте проверки готовности (например, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source ...`).
3. При необходимости предусмотрите ветки для ручных вмешательств.

## Fail-fast и вопросы
- Опишите ситуации, когда команда должна остановиться (нет PRD, отсутствует approved статус, не найден список задач).
- Формат вопросов:
  ```
  Вопрос N (Blocker|Clarification): ...
  Зачем: ...
  Варианты: A) ... B) ...
  Default: ...
  ```

## Ожидаемый вывод
- Укажите, какие файлы/разделы должны быть обновлены по завершении.
- Зафиксируйте требования к финальному сообщению: `Checkbox updated: ...`, затем `Status: ...`, `Artifacts updated: ...`, `Next actions: ...`.

## Примеры CLI
- Приведите пример вызова команды/скрипта (например, `/feature-dev-aidd:implement ABC-123` или `!bash -lc '${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --ticket ABC-123'`).
- Добавьте подсказки по аргументам и типовым ошибкам.
```

## Git hook templates
Эти хуки предназначены для разработки этого репозитория. В пользовательских проектах запускайте нужные хуки через `${CLAUDE_PLUGIN_ROOT}/hooks/*` или адаптируйте скрипты под свой репозиторий.

### Установка
Создайте файл в `.git/hooks/`, сделайте исполняемым:
```
chmod +x .git/hooks/<hook>
```

### commit-msg
```bash
#!/usr/bin/env bash
set -euo pipefail

MESSAGE_FILE="$1"
ROOT_DIR="$(git rev-parse --show-toplevel)"
CONFIG_FILE="${ROOT_DIR}/aidd/config/conventions.json"

# Установите COMMIT_LINT_BYPASS=1, чтобы пропустить проверку (например, для emergency-коммитов).
if [[ "${COMMIT_LINT_BYPASS:-0}" == "1" ]]; then
  exit 0
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  printf '[commit-msg] aidd/config/conventions.json не найден, проверка пропущена\n' >&2
  exit 0
fi

python3 - "$CONFIG_FILE" "$MESSAGE_FILE" <<'PY'
import json
import re
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
message_file = Path(sys.argv[2])

data = json.loads(config_path.read_text(encoding="utf-8"))
commit_cfg = data.get("commit", {})
mode = commit_cfg.get("mode") or commit_cfg.get("activeMode", "ticket-prefix")
modes = commit_cfg.get("modes", {})
mode_cfg = modes.get(mode, {})

first_line = message_file.read_text(encoding="utf-8").splitlines()[0].strip()

if not first_line or first_line.startswith("Merge") or first_line.startswith("#"):
    sys.exit(0)

patterns = {
    "ticket-prefix": r"^[A-Z0-9._-]+: .+",
    "conventional": r"^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([^)]+\))?: .+",
    "mixed": r"^[A-Z0-9._-]+ (build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([^)]+\))?: .+"
}

pattern = patterns.get(mode)
if pattern is None:
    sys.exit(0)

if re.match(pattern, first_line):
    sys.exit(0)

example = mode_cfg.get("example", "STORE-123: describe change")
print(f"[commit-msg] Сообщение не соответствует режиму '{mode}'. Пример: {example}", file=sys.stderr)
sys.exit(1)
PY
```

### prepare-commit-msg
```bash
#!/usr/bin/env bash
set -euo pipefail

MESSAGE_FILE="$1"
ROOT_DIR="$(git rev-parse --show-toplevel)"
CONFIG_FILE="${ROOT_DIR}/aidd/config/conventions.json"

# Пропустить автозаполнение, если сообщение уже содержит текст (игнорируя комментарии).
if grep -Eq '^[^#[:space:]]' "$MESSAGE_FILE"; then
  exit 0
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
  exit 0
fi

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

python3 - "$CONFIG_FILE" "$MESSAGE_FILE" "$CURRENT_BRANCH" <<'PY'
import json
import re
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
message_file = Path(sys.argv[2])
branch = sys.argv[3]

data = json.loads(config_path.read_text(encoding="utf-8"))
commit_cfg = data.get("commit", {})
mode = commit_cfg.get("mode") or commit_cfg.get("activeMode", "ticket-prefix")
modes = commit_cfg.get("modes", {})
mode_cfg = modes.get(mode, {})
example = mode_cfg.get("example", "STORE-123: describe change")

ticket = ""
if branch:
    match = re.search(r"[A-Z][A-Z0-9]+-[0-9]+", branch)
    if match:
        ticket = match.group(0)

if mode == "ticket-prefix" and ticket:
    suggestion = f"{ticket}: "
elif mode == "mixed" and ticket:
    suggestion = f"{ticket} feat(<scope>): "
elif mode == "conventional":
    suggestion = "feat(<scope>): "
else:
    suggestion = ""

if not suggestion:
    sys.exit(0)

original = message_file.read_text(encoding="utf-8", errors="ignore")
comment_hint = f"# Пример ({mode}): {example}"

message_file.write_text(
    suggestion + "\n\n" + comment_hint + "\n" + original,
    encoding="utf-8"
)
PY
```

### pre-push
```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
HOOK="${ROOT_DIR}/hooks/format-and-test.sh"

# Установите PRE_PUSH_SKIP=1, чтобы временно отключить проверку.
if [[ "${PRE_PUSH_SKIP:-0}" == "1" ]]; then
  exit 0
fi

if [[ ! -x "$HOOK" ]]; then
  printf '[pre-push] %s не найден, пропускаем проверки\n' "$HOOK" >&2
  exit 0
fi

export STRICT_TESTS="${STRICT_TESTS:-1}"
export SKIP_FORMAT="${SKIP_FORMAT:-0}"

cd "$ROOT_DIR"
"$HOOK"
```
