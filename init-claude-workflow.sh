#!/usr/bin/env bash
# init-claude-workflow.sh
# Bootstraps Claude Code workflow for Java/Kotlin monorepos.
# Creates .claude commands/agents/hooks, commit/branch conventions,
# Gradle selective-tests logic, and basic docs (PRD/ADR templates).
#
# Usage:
#   bash init-claude-workflow.sh [--commit-mode MODE] [--enable-ci] [--force] [--dry-run]
#     --commit-mode   ticket-prefix | conventional | mixed   (default: ticket-prefix)
#     --enable-ci     add a minimal GitHub Actions workflow (manual trigger)
#     --force         overwrite existing files
#     --dry-run       log planned actions without touching the filesystem
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
ROOT_DIR="$(pwd)"

COMMIT_MODE="ticket-prefix"
ENABLE_CI=0
FORCE=0
DRY_RUN=0

log_info()   { printf '[INFO] %s\n' "$*"; }
log_warn()   { printf '[WARN] %s\n' "$*" >&2; }
log_error()  { printf '[ERROR] %s\n' "$*" >&2; }
die()        { log_error "$*"; exit 1; }

usage() {
  cat <<'EOF'
Usage: bash init-claude-workflow.sh [options]
  --commit-mode MODE   ticket-prefix | conventional | mixed   (default: ticket-prefix)
  --enable-ci          add GitHub Actions workflow (manual trigger)
  --force              overwrite existing files
  --dry-run            show planned actions without writing files
  -h, --help           print this help
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --commit-mode)
        [[ $# -ge 2 ]] || die "--commit-mode requires a value"
        COMMIT_MODE="$2"; shift 2;;
      --enable-ci) ENABLE_CI=1; shift;;
      --force)     FORCE=1; shift;;
      --dry-run)   DRY_RUN=1; shift;;
      -h|--help)   usage; exit 0;;
      *)           die "Unknown argument: $1";;
    esac
  done

  case "$COMMIT_MODE" in
    ticket-prefix|conventional|mixed) ;;
    *) die "Unsupported --commit-mode: $COMMIT_MODE";;
  esac
}

require_command() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || die "Missing dependency: $cmd"
}

check_dependencies() {
  log_info "Checking prerequisites"
  require_command bash
  require_command git
  require_command python3

  local has_gradle=0
  if [[ -x "$ROOT_DIR/gradlew" ]]; then
    has_gradle=1
  elif command -v gradle >/dev/null 2>&1; then
    has_gradle=1
  fi

  if [[ "$has_gradle" -eq 1 ]]; then
    log_info "Gradle detected"
  else
    log_warn "Gradle not found (expect ./gradlew or gradle). Selective tests will be unavailable until installed."
  fi

  if command -v ktlint >/dev/null 2>&1; then
    log_info "ktlint detected"
  else
    log_warn "ktlint not found. Formatting step will be skipped if Spotless is absent."
  fi
}

ensure_directory() {
  local dir="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] ensure directory $dir/"
  else
    mkdir -p "$dir"
  fi
}

write_template() {
  local path="$1"
  if [[ -e "$path" && "$FORCE" -ne 1 ]]; then
    log_warn "skip: $path (exists, use --force to overwrite)"
    cat >/dev/null
    return
  fi

  local dir
  dir="$(dirname "$path")"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] write $path"
    cat >/dev/null
  else
    mkdir -p "$dir"
    cat >"$path"
    log_info "wrote: $path"
  fi
}

set_executable() {
  local path="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] chmod +x $path"
  else
    chmod +x "$path"
  fi
}

replace_commit_mode() {
  local path="config/conventions.json"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] set commit mode to $COMMIT_MODE in $path"
    return
  fi
  python3 - <<PY
import json, pathlib
path = pathlib.Path("$path")
data = json.loads(path.read_text(encoding="utf-8"))
data.setdefault("commit", {})["mode"] = "$COMMIT_MODE"
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
  log_info "commit mode set to $COMMIT_MODE"
}

generate_directories() {
  log_info "Ensuring directory structure"
  local dirs=(
    ".claude"
    ".claude/commands"
    ".claude/agents"
    ".claude/hooks"
    ".claude/gradle"
    ".claude/cache"
    "config"
    "scripts"
    "docs"
    "docs/prd"
    "docs/adr"
    "docs/plan"
    "docs/api"
    "docs/test"
  )
  for dir in "${dirs[@]}"; do
    ensure_directory "$dir"
  done
}

generate_core_docs() {
  write_template "CLAUDE.md" <<'MD'
# Claude Code Workflow (AI-driven)

## Основной цикл
1. `/feature-activate <slug>` — зафиксируйте активную фичу (используется гейтами).
2. `/idea-new <slug> [TICKET]` — агент analyst собирает требования и оформляет PRD.
3. `/plan-new <slug>` — planner составляет план реализации, validator проверяет полноту.
4. `/tasks-new <slug>` — tasklist синхронизируется с планом (реализация, тесты, документация).
5. `/implement <slug>` — агент implementer вносит кодовые изменения, автотесты запускаются через `/test-changed`.
6. `/review <slug>` — reviewer проводит код-ревью и возвращает замечания в tasklist.

Дополнительно:
- `/api-spec-new`, `/tests-generate`, `/docs-generate` — поддерживающие артефакты.
- `/branch-new`, `/commit`, `/commit-validate`, `/conventions-set` — управление ветками и коммитами.

## Хуки и гейты
- `.claude/hooks/protect-prod.sh` — блокирует опасные правки в infra/prod.
- `.claude/hooks/gate-workflow.sh` — не даёт редактировать `src/**`, пока не готовы PRD/план/тасклист.
- `.claude/hooks/gate-api-contract.sh` / `gate-db-migration.sh` / `gate-tests.sh` — contract/DB/tests гейты.
- `.claude/hooks/format-and-test.sh` — автоформатирование и выборочные Gradle тесты.
- `.claude/hooks/lint-deps.sh` — напоминает про allowlist зависимостей.

Настройки и пресеты смотрите в `.claude/settings.json`, правила коммитов — в `config/conventions.json`.
MD

  write_template "conventions.md" <<'MD'
# conventions.md

- **Стиль кода**: следуем KISS/YAGNI/MVP; используем JetBrains/Google style (Spotless + ktlint при наличии).
- **Ветки**: создаём через `/branch-new` (`feature/<TICKET>`, `feat/<scope>`, `hotfix/<TICKET>`).
- **Коммиты**: формируются командой `/commit`, режим задаётся в `config/conventions.json`.
- **Документация**: PRD (`docs/prd/<slug>.prd.md`), план (`docs/plan/<slug>.md`), tasklist (`tasklist.md`), API (`docs/api/<slug>.yaml`).
- **Автогейты**: для работы с кодом должны быть готовы PRD/план/таски; для контроллеров — актуальный OpenAPI; для сущностей — миграция.
- **Тесты**: после каждого изменения запускаем `/test-changed`; при необходимости дозаказываем `/tests-generate`.
- **Контроль зависимостей**: список разрешённых артефактов — `config/allowed-deps.txt`, изменяется через ревью.
MD

  write_template "workflow.md" <<'MD'
# Workflow Claude Code

Документ описывает целевой процесс работы команды после запуска `init-claude-workflow.sh`. Цикл строится вокруг идеи и проходит шесть этапов: **идея → план → валидация → задачи → реализация → ревью**. На каждом шаге задействованы специализированные саб-агенты Claude Code и автоматические гейты, которые защищают кодовую базу.

## Обзор этапов

| Этап | Команда | Саб-агент | Основные артефакты |
| --- | --- | --- | --- |
| Аналитика идеи | `/idea-new <slug> [TICKET]` | `analyst` | `docs/prd/<slug>.prd.md`, активная фича |
| Планирование | `/plan-new <slug>` | `planner`, `validator` | `docs/plan/<slug>.md`, уточнённые вопросы |
| Тасклист | `/tasks-new <slug>` | — | `tasklist.md` (обновлённые чеклисты) |
| Реализация | `/implement <slug>` | `implementer` | кодовые изменения, обновлённые тесты |
| Доп. артефакты | `/api-spec-new <slug>`, `/tests-generate <slug>` | `api-designer`, `qa-author` | `docs/api/<slug>.yaml`, `docs/test/<slug>-manual.md` |
| Ревью | `/review <slug>` | `reviewer` | замечания в `tasklist.md`, итоговый статус |

## Подробности по шагам

### 1. Идея (`/idea-new`)
- Устанавливает активную фичу (`docs/.active_feature`).
- Создаёт PRD по шаблону (`docs/prd/<slug>.prd.md`), собирает вводные, риски и метрики.
- Саб-агент **analyst** уточняет контекст и формирует финальный документ.

### 2. План (`/plan-new`)
- Саб-агент **planner** формирует пошаговый план реализации по PRD.
- Саб-агент **validator** проверяет план; найденные вопросы возвращаются продукту.
- Все открытые вопросы синхронизируются между PRD и планом.

### 3. Тасклист (`/tasks-new`)
- Преобразует план в чеклисты в `tasklist.md`.
- Структурирует задачи по этапам (аналитика, разработка, QA, релиз).
- Добавляет критерии приёмки и зависимости.

### 4. Реализация (`/implement`)
- Саб-агент **implementer** следует шагам плана и вносит изменения малыми итерациями.
- После каждой правки автоматически запускается `/test-changed` (отключаемо через `SKIP_AUTO_TESTS=1`).
- Изменения блокируются до появления необходимых артефактов гейтами:
  - `gate-workflow.sh` — проверяет наличие PRD/плана/тасклиста.
  - `gate-api-contract.sh` — требует OpenAPI контракт для активной фичи.
  - `gate-db-migration.sh` — проверяет наличие миграций при изменении сущностей.
  - `gate-tests.sh` — убеждается, что для исходников есть тесты (soft/hard режим).

### 5. Дополнительные артефакты
- `/api-spec-new <slug>` задействует **api-designer** для генерации или обновления OpenAPI.
- `/tests-generate <slug>` подключает **qa-author**, который дополняет автотесты и формирует чеклист ручного тестирования (`docs/test/<slug>-manual.md`).
- Эти команды помогают пройти API/DB/тест-гейты и ускоряют ревью.

### 6. Ревью (`/review`)
- Саб-агент **reviewer** проводит код-ревью и синхронизирует замечания в `tasklist.md`.
- При блокирующих проблемах фича возвращается на стадию реализации; при минорных — фиксируется список рекомендаций.

## Автоматизация и гейты

- `.claude/settings.json` включает пресет `strict`, который запускает защитные хуки при любой записи (`Write|Edit`).
- `.claude/hooks/format-and-test.sh` выполняет форматирование и выборочные Gradle-тесты; полный прогон запускается, если изменены общие файлы.
- Переменная `SKIP_AUTO_TESTS=1` временно отключает автостарт `/test-changed` (полезно для больших миграций или отладки).
- `config/gates.json` управляет режимами гейтов:
  - `api_contract`, `db_migration` — включение/отключение проверок.
  - `tests_required` — `disabled`/`soft`/`hard`.
  - `feature_slug_source` — путь к файлу с активной фичей.
- При необходимости можно расширить список гейтов (см. `docs/customization.md`).

## Роли и ответственность команды

- **Product/Analyst** — поддерживает PRD и контролирует, что вопросы валидируются.
- **Tech Lead/Architect** — утверждает план и следит за API/DB гейтами.
- **Разработчики** — реализуют по плану и поддерживают актуальность тестов и документации.
- **QA** — участвует в `/tests-generate`, наполняет `docs/test/*.md` и помогает с гейтами `gate-tests.sh`.
- **Reviewer** — финализирует фичу, проверяет, что все чеклисты в `tasklist.md` закрыты.

Следуйте этому циклу, чтобы команда оставалась синхронизированной, а артефакты — в актуальном состоянии.
MD

  write_template "tasklist.md" <<'MD'
# tasklist.md — чеклист фичи

## Контекст
- [ ] PRD: `[docs/prd/<slug>.prd.md]`
- [ ] План: `[docs/plan/<slug>.md]`
- [ ] Tasklist обновлён командой `/tasks-new <slug>`
- [ ] Ответственные (dev / qa / pm)

## Реализация
- [ ] Код соответствует плану и архитектурным решениям.
- [ ] Обновлены схемы/контракты (API, миграции).
- [ ] Покрыты основные и пограничные сценарии тестами.
- [ ] `/test-changed` проходит без ошибок.

## QA и документация
- [ ] Юнит/интеграционные тесты дополнены.
- [ ] Документация (README, usage-demo, customization) актуальна.
- [ ] Задокументированы ручные сценарии (`docs/test/<slug>-manual.md`).

## Ревью и релиз
- [ ] Код-ревью выполнено (`/review <slug>`), замечания закрыты.
- [ ] Tasklist отмечен READY, артефакты синхронизированы.
- [ ] Добавлено в `docs/release-notes.md` (при релизе).
MD
}

generate_templates() {
  write_template "docs/prd.template.md" <<'MD'
# PRD — Шаблон

Заполните текст в соответствии с проектом. Примеры в скобках помогут выбрать формат.

## 1. Обзор
- **Название продукта/фичи**: `<Название или код>` (например, `Smart Checkout`)
- **Владелец**: `<Имя + роль>`
- **Дата/версия**: `<2024-05-14 v1>`
- **Краткое описание**: `<1–2 предложения о цели инициативы>`

## 2. Контекст и проблемы
- **Текущая ситуация**: `<Что происходит сейчас>` (например, «Конверсия падает на 12% при переходе к оплате»)
- **Проблемы/гипотезы**: `<Список ключевых pain points>`
- **Затронутые сегменты**: `<Перечень сегментов и доля пользователей>`

## 3. Цели и метрики успеха
- **North Star / основная метрика**: `<A → B>` (например, «Увеличить конверсию до 68% (+10 п.п.)»)
- **Поддерживающие метрики**: `<метрика → целевое значение>` (например, «Сократить время оформления заказа до 40 сек.»)
- **Контрольные метрики**: `<метрика → пороговое значение>` (например, «Доля ошибок оплаты ≤ 1%»)

## 4. Связанные ADR и артефакты
- `<adr/0001-smart-checkout.md — объясняет выбор протокола>`
- `<adr/0002-payment-gateway.md — описывает интеграцию с PSP>`
- `<таски / epic / RFC>` (укажите ссылки или идентификаторы)

## 5. Пользовательские сценарии
Опишите ключевые сценарии от лица пользователя:
1. `<Как пользователь выполняет ключевое действие>`
2. `<Edge-case сценарий>`
Добавьте диаграммы или последовательности, если они помогают.

## 6. Требования
### 6.1 Функциональные
- [ ] `<Краткое описание поведения>` (например, «Система сохраняет черновик корзины на 7 дней»)
- [ ] `<Валидации, пограничные состояния>`

### 6.2 Нефункциональные
- [ ] `<SLO/SLI или производительность>` (например, «P95 ответа сервиса ≤ 300 мс»)
- [ ] `<Безопасность, доступность, локализация>`

## 7. Ограничения и зависимости
- **Технические**: `<Legacy, инфраструктура, лицензии>`
- **Процессные**: `<Календари релизов, внешние команды>`
- **Внешние**: `<Партнёры, регуляторы>`

## 8. План и этапы
- **Майлстоуны**: `<MVP, Beta, GA>`
- **Команда**: `<Product, Design, Eng, Data>`
- **Оценка ресурсов**: `<Часы/Story Points/Спринты>`

## 9. Риски и стратегии
- `<Риск>` → `<Вероятность/Импакт>` → `<Митигация>`
- `<Что делаем, если тезис не подтверждается>`

## 10. Открытые вопросы
- `<Вопрос>` → `<Ответственный>` → `<Дедлайн решения>`

## 11. Чеклист ревью PRD
- [ ] Цели и метрики успеха согласованы со стейкхолдерами.
- [ ] Есть ссылки на все актуальные ADR и связанные таски.
- [ ] Сценарии пользователя покрывают happy-path и edge-case.
- [ ] Указаны контрольные метрики и граничные условия.
- [ ] Риски и зависимости описаны с планом действий.
- [ ] Команда подтверждает ресурсы/таймлайн.

## 12. История изменений
- `<Дата>` — `<Что изменилось>` — `<Автор>`
MD

  write_template "docs/adr.template.md" <<'MD'
# ADR — Шаблон

> Архитектурное решение должно быть коротким и воспроизводимым. Заполните секции, убрав подсказки в угловых скобках.

## 1. Метаданные
- **Идентификатор**: `ADR-<номер>` (например, `ADR-0005`)
- **Название**: `<Кратко сформулированное решение>`
- **Статус**: `<Proposed | Accepted | Rejected | Superseded>`
- **Дата**: `<YYYY-MM-DD>`
- **Связанный PRD / инициативы**: `[PRD: <ссылка>]`, `[Таски: <JIRA-123, RFC-45>]`

## 2. Контекст
Опишите ситуацию и требования, которые приводят к необходимости решения.
- **Проблема**: `<Какое ограничение необходимо снять>`
- **Драйверы**: `<Метрики, SLA, бизнес-кейсы>`
- **Альтернативы, которые рассматривались**: `<Кратко, по 1–2 предложения>`

## 3. Решение
- **Выбранный подход**: `<Описание архитектуры / паттерна>`
- **Компоненты**: `<Сервисы, модули, библиотеки>`
- **Диаграмма** *(опционально)*: `<Ссылка на C4/Sequence>`

## 4. Импакт на систему
- **Затронутые домены**: `<Auth, Checkout, Payments>`
- **Изменения интерфейсов / API**: `<REST / gRPC / события>`
- **Миграции / данные**: `<Новые таблицы, скрипты миграции>`
- **Операционные эффекты**: `<Мониторинг, алерты, on-call нагрузка>`
- **Риски и обходные планы**: `<Что пойдёт не так и как реагировать>`

## 5. Оценка альтернатив
| Вариант | Плюсы | Минусы | Причина отказа |
| --- | --- | --- | --- |
| `<Вариант A>` | `<+>` | `<->` | `<Почему не выбрали>` |
| `<Вариант B>` | `<+>` | `<->` | `<Почему не выбрали>` |

## 6. Критерии принятия решения
- [ ] `<Требование, которое должно выполняться>` (например, «P95 < 250 мс»)
- [ ] `<Совместимость / обратная совместимость проверена>`
- [ ] `<План миграции согласован с командами>`
- [ ] `<Мониторинг и алерты определены>`
- [ ] `<Документация и обучение подготовлены>`

## 7. План внедрения
- **Этапы**: `<PoC → Beta → GA>`
- **Зависимости**: `<Команды, контракты, инфраструктура>`
- **Дедлайны**: `<Дата/спринт>`

## 8. Решение и последующие действия
- **Принято/отклонено**: `<Кто утвердил и когда>`
- **TODO после принятия**: `<Список follow-up задач>`
- **Связанные PR / коммиты**: `<Ссылки>`

## 9. История
- `<Дата>` — `<Изменение>` — `<Автор>`
MD

  write_template "docs/plan/.gitkeep" <<'MD'
MD

  write_template "docs/api/.gitkeep" <<'MD'
MD

  write_template "docs/test/.gitkeep" <<'MD'
MD
}

generate_claude_settings() {
  write_template ".claude/settings.json" <<'JSON'
{
  "model": "sonnet",
  "outputStyle": "Explanatory",
  "presets": {
    "active": "strict",
    "instructions": "Измените это поле и скопируйте permissions/hooks из presets.list.<name> на верхний уровень, чтобы переключаться между пресетами.",
    "list": {
      "start": {
        "description": "Базовый режим: минимальные права и отсутствие автоматических хуков.",
        "permissions": {
          "allow": [
            "Read",
            "Write",
            "Edit",
            "Grep",
            "Glob"
          ],
          "ask": [
            "Bash(git add:*)",
            "Bash(git commit:*)"
          ],
          "deny": [
            "Bash(curl:*)",
            "Read(./.env)",
            "Read(./.env.*)",
            "Read(./secrets/**)"
          ]
        },
        "hooks": {
          "PreToolUse": [],
          "PostToolUse": []
        }
      },
      "strict": {
        "description": "Строгий режим: включены проверки защищённых путей и автозапуск форматирования/тестов.",
        "permissions": {
          "allow": [
            "Read",
            "Write",
            "Edit",
            "Grep",
            "Glob",
            "Bash(git status:*)",
            "Bash(git diff:*)",
            "Bash(git rev-parse:*)",
            "Bash(git checkout:*)",
            "Bash(./gradlew:*)",
            "Bash(gradle:*)",
            "Bash(.claude/hooks/*:*)",
            "Bash(python3 scripts/*:*)",
            "SlashCommand:/test-changed:*",
            "SlashCommand:/commit:*",
            "SlashCommand:/tests-generate:*",
            "SlashCommand:/api-spec-new:*"
          ],
          "ask": [
            "Bash(git add:*)",
            "Bash(git commit:*)",
            "Bash(git push:*)"
          ],
          "deny": [
            "Bash(curl:*)",
            "Read(./.env)",
            "Read(./.env.*)",
            "Read(./secrets/**)",
            "Write(./infra/prod/**)"
          ]
        },
        "hooks": {
          "PreToolUse": [
            {
              "matcher": "Write|Edit",
              "hooks": [
                {
                  "type": "command",
                  "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/protect-prod.sh",
                  "timeout": 5
                },
                {
                  "type": "command",
                  "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/gate-workflow.sh",
                  "timeout": 5
                },
                {
                  "type": "command",
                  "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/gate-api-contract.sh",
                  "timeout": 5
                },
                {
                  "type": "command",
                  "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/gate-db-migration.sh",
                  "timeout": 5
                },
                {
                  "type": "command",
                  "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/gate-tests.sh",
                  "timeout": 5
                }
              ]
            }
          ],
          "PostToolUse": [
            {
              "matcher": "Write|Edit",
              "hooks": [
                {
                  "type": "command",
                  "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/format-and-test.sh",
                  "timeout": 900
                },
                {
                  "type": "command",
                  "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/lint-deps.sh",
                  "timeout": 10
                }
              ]
            }
          ]
        }
      }
    }
  },
  "permissions": {
    "allow": [
      "Read",
      "Write",
      "Edit",
      "Grep",
      "Glob",
      "Bash(git status:*)",
      "Bash(git diff:*)",
      "Bash(git rev-parse:*)",
      "Bash(git checkout:*)",
      "Bash(./gradlew:*)",
      "Bash(gradle:*)",
      "Bash(.claude/hooks/*:*)",
      "Bash(python3 scripts/*:*)",
      "SlashCommand:/test-changed:*",
      "SlashCommand:/commit:*",
      "SlashCommand:/tests-generate:*",
      "SlashCommand:/api-spec-new:*"
    ],
    "ask": [
      "Bash(git add:*)",
      "Bash(git commit:*)",
      "Bash(git push:*)"
    ],
    "deny": [
      "Bash(curl:*)",
      "Read(./.env)",
      "Read(./.env.*)",
      "Read(./secrets/**)",
      "Write(./infra/prod/**)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/protect-prod.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/gate-workflow.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/gate-api-contract.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/gate-db-migration.sh",
            "timeout": 5
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/gate-tests.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/format-and-test.sh",
            "timeout": 900
          },
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/lint-deps.sh",
            "timeout": 10
          }
        ]
      }
    ]
  },
  "automation": {
    "format": {
      "commands": [],
      "notes": "Добавьте сюда массив команд (например, [ [\"./gradlew\", \"spotlessApply\"] ]) или укажите SKIP_FORMAT=1.",
      "env": {
        "SKIP_FORMAT": "1 — пропустить форматирование;",
        "FORMAT_ONLY": "1 — выполнить только форматирование без тестов."
      }
    },
    "tests": {
      "runner": "bash",
      "defaultTasks": [
        "scripts/ci-lint.sh"
      ],
      "fallbackTasks": [
        "scripts/ci-lint.sh"
      ],
      "changedOnly": true,
      "strictDefault": 1,
      "moduleMatrix": [],
      "env": {
        "TEST_SCOPE": "Список задач через запятую (например, :app:test,:lib:test).",
        "TEST_CHANGED_ONLY": "0 — запускать полный набор задач независимо от diff.",
        "STRICT_TESTS": "1 — падать при первых ошибках тестов, 0 — только предупреждать."
      }
    }
  },
  "protection": {
    "protectedGlobs": [
      "infra/prod/*",
      "deploy/prod/*"
    ],
    "allowlist": [
      "infra/prod/README.md"
    ],
    "bypassEnv": "PROTECT_PROD_BYPASS",
    "logOnlyEnv": "PROTECT_LOG_ONLY",
    "docs": "docs/customization.md#prod-protection",
    "notes": "Добавьте новые паттерны или перенесите объекты в allowlist, если они безопасны."
  }
}
JSON

  write_template ".claude/hooks/protect-prod.sh" <<'BASH'
#!/usr/bin/env bash
set -euo pipefail

# protect-prod.sh
# ----------------
# Hook, который блокирует несанкционированную работу с чувствительными путями.
# Использует секцию protection в .claude/settings.json.
# Переменные окружения:
#   PROTECT_PROD_BYPASS=1  — явный override (или имя из protection.bypassEnv).
#   PROTECT_LOG_ONLY=1     — не блокировать, а только предупреждать.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_FILE="${ROOT_DIR}/.claude/settings.json"

log() {
  printf '[protect-prod] %s\n' "$*" >&2
}

collect_candidate_files() {
  local -a files=()
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    while IFS= read -r line; do
      [[ -n "$line" ]] && files+=("$line")
    done < <(git diff --name-only --cached)
    while IFS= read -r line; do
      [[ -n "$line" ]] && files+=("$line")
    done < <(git diff --name-only)
  fi
  while IFS= read -r line; do
    [[ -n "$line" ]] && files+=("$line")
  done < <(git ls-files --others --exclude-standard)

  if ((${#files[@]})); then
    printf '%s\n' "${files[@]}" | sort -u
  fi
}

if [[ ! -f "$CONFIG_FILE" ]]; then
  log "Не найден ${CONFIG_FILE} — пропускаем проверку путей."
  exit 0
fi

readarray -t CHECK_RESULT < <(
  python3 - "$CONFIG_FILE" <<'PY'
import json
import os
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
data = json.loads(config_path.read_text(encoding="utf-8"))
protection = data.get("protection", {})

bypass_env = protection.get("bypassEnv", "PROTECT_PROD_BYPASS")
log_only_env = protection.get("logOnlyEnv", "PROTECT_LOG_ONLY")
protected = protection.get("protectedGlobs", [])
allowlist = protection.get("allowlist", [])
help_url = protection.get("docs", "docs/customization.md#prod-protection")

print(f"BYPASS_ENV={bypass_env}")
print(f"LOG_ONLY_ENV={log_only_env}")
print("PROTECTED=" + "\0".join(protected))
print("ALLOWLIST=" + "\0".join(allowlist))
print(f"HELP_URL={help_url}")
PY
)

declare BYPASS_ENV=""
declare LOG_ONLY_ENV=""
declare HELP_URL=""
declare -a PROTECTED_GLOBS=()
declare -a ALLOWLIST_GLOBS=()

for line in "${CHECK_RESULT[@]}"; do
  case "$line" in
    BYPASS_ENV=*)
      BYPASS_ENV="${line#BYPASS_ENV=}"
      ;;
    LOG_ONLY_ENV=*)
      LOG_ONLY_ENV="${line#LOG_ONLY_ENV=}"
      ;;
    HELP_URL=*)
      HELP_URL="${line#HELP_URL=}"
      ;;
    PROTECTED=*)
      IFS=$'\0' read -r -a PROTECTED_GLOBS <<< "${line#PROTECTED=}"
      ;;
    ALLOWLIST=*)
      IFS=$'\0' read -r -a ALLOWLIST_GLOBS <<< "${line#ALLOWLIST=}"
      ;;
  esac
done

if [[ -n "$BYPASS_ENV" && "${!BYPASS_ENV:-0}" == "1" ]]; then
  log "Обнаружен ${BYPASS_ENV}=1 — защита отключена."
  exit 0
fi

mapfile -t CANDIDATE_FILES < <(collect_candidate_files || true)
if ((${#CANDIDATE_FILES[@]} == 0)); then
  exit 0
fi

readarray -t VIOLATIONS < <(
  python3 - "$CONFIG_FILE" "${CANDIDATE_FILES[@]}" <<'PY'
import fnmatch
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
files = sys.argv[2:]
data = json.loads(config_path.read_text(encoding="utf-8"))
protection = data.get("protection", {})

protected = protection.get("protectedGlobs", [])
allowlist = protection.get("allowlist", [])

matches = []

def is_allowed(path):
    return any(fnmatch.fnmatch(path, pattern) for pattern in allowlist)

for path in files:
    if is_allowed(path):
        continue
    for pattern in protected:
        if fnmatch.fnmatch(path, pattern):
            matches.append((path, pattern))
            break

for path, pattern in matches:
    print(f"{path}|{pattern}")
PY
)

if ((${#VIOLATIONS[@]} == 0)); then
  exit 0
fi

log "Обнаружены изменения в защищённых путях:"
for entry in "${VIOLATIONS[@]}"; do
  file="${entry%%|*}"
  pattern="${entry#*|}"
  log "  - ${file} (паттерн: ${pattern})"
done

if [[ -n "$LOG_ONLY_ENV" && "${!LOG_ONLY_ENV:-0}" == "1" ]]; then
  log "${LOG_ONLY_ENV}=1 — только предупреждение (операция не блокирована)."
  exit 0
fi

log "Чтобы добавить исключение, обновите protection.allowlist в .claude/settings.json или переместите файлы."
if [[ -n "$HELP_URL" ]]; then
  log "Подробности: ${HELP_URL}"
fi
exit 1
BASH
  set_executable ".claude/hooks/protect-prod.sh"

  write_template ".claude/hooks/gate-workflow.sh" <<'BASH'
#!/usr/bin/env bash
set -euo pipefail
payload="$(cat)"

# Путь редактируемого файла
file_path="$(
  PAYLOAD="$payload" python3 - <<'PY'
import json
import os
import sys

payload = os.environ.get("PAYLOAD") or ""
try:
    data = json.loads(payload)
except json.JSONDecodeError:
    print("")
    sys.exit(0)

print(data.get("tool_input", {}).get("file_path", ""))
PY
)"

slug_file="docs/.active_feature"
[[ -f "$slug_file" ]] || exit 0  # нет активной фичи — не блокируем
slug="$(cat "$slug_file" 2>/dev/null || true)"
[[ -n "$slug" ]] || exit 0

# Если правится не код, пропускаем
if [[ ! "$file_path" =~ (^|/)src/ ]]; then
  exit 0
fi

# Проверим артефакты
[[ -f "docs/prd/$slug.prd.md" ]] || { echo "BLOCK: нет PRD → запустите /idea-new $slug"; exit 2; }
[[ -f "docs/plan/$slug.md"    ]] || { echo "BLOCK: нет плана → запустите /plan-new $slug"; exit 2; }
if ! python3 - "$slug" <<'PY'
import sys, pathlib
slug = sys.argv[1]
tasklist = pathlib.Path("tasklist.md")
if not tasklist.exists():
    sys.exit(1)
slug_tokens = {slug, slug.replace("-", " "), slug.replace("-", "_")}
for raw in tasklist.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line.startswith("- [ ]"):
        continue
    if "<slug>" in line:
        continue
    if any(token and token in line for token in slug_tokens) or "::" in line:
        sys.exit(0)
sys.exit(1)
PY
then
  echo "BLOCK: нет задач → запустите /tasks-new $slug"
  exit 2
fi

exit 0
BASH
  set_executable ".claude/hooks/gate-workflow.sh"

  write_template ".claude/hooks/gate-api-contract.sh" <<'BASH'
#!/usr/bin/env bash
# Блокирует правки контроллеров/роутов, если нет OpenAPI контракта для активной фичи
set -euo pipefail
payload="$(cat)"

json_get_bool() {
  python3 - <<'PY' "$1" "$2"
import json,sys
path=sys.argv[1]; key=sys.argv[2]
try:
  cfg=json.load(open(path,'r',encoding='utf-8'))
  v=cfg.get(key, False)
  print("1" if v else "0")
except Exception:
  print("0")
PY
}

file_path="$(
  PAYLOAD="$payload" python3 - <<'PY'
import json, os
payload = os.environ.get("PAYLOAD") or ""
try:
    data = json.loads(payload)
except json.JSONDecodeError:
    print("")
else:
    print(data.get("tool_input", {}).get("file_path", ""))
PY
)"

[[ -f config/gates.json ]] || exit 0
[[ "$(json_get_bool config/gates.json api_contract)" == "1" ]] || exit 0

slug_file="$(python3 - <<'PY'
import json,sys
cfg='config/gates.json'
try:
  import json
  g=json.load(open(cfg,'r',encoding='utf-8'))
  print(g.get('feature_slug_source','docs/.active_feature'))
except Exception:
  print('docs/.active_feature')
PY
)"

[[ -f "$slug_file" ]] || exit 0
slug="$(cat "$slug_file" 2>/dev/null || true)"
[[ -n "$slug" ]] || exit 0

# если правится не контроллер/роут — пропустим
if [[ ! "$file_path" =~ (^|/)src/main/.*/(controller|rest|web|routes?)/.*\.(kt|java)$ ]] && \
   [[ ! "$file_path" =~ (Controller|Resource)\.(kt|java)$ ]]; then
  exit 0
fi

# проверим наличие контракта
has_spec=0
for p in "docs/api/$slug.yaml" "docs/api/$slug.yml" "docs/api/$slug.json" "src/main/resources/openapi.yaml" "openapi.yaml"; do
  [[ -f "$p" ]] && has_spec=1 && break
done

if [[ $has_spec -eq 0 ]]; then
  echo "BLOCK: нет API контракта для '$slug'. Создайте его командой: /api-spec-new $slug" 1>&2
  exit 2
fi
exit 0
BASH
  set_executable ".claude/hooks/gate-api-contract.sh"

  write_template ".claude/hooks/gate-db-migration.sh" <<'BASH'
#!/usr/bin/env bash
# Требует наличие новой миграции Flyway/Liquibase при изменении сущностей/схемы
set -euo pipefail
payload="$(cat)"

json_get_bool() {
  python3 - <<'PY' "$1" "$2"
import json,sys
cfg=sys.argv[1]; key=sys.argv[2]
try:
  d=json.load(open(cfg,'r',encoding='utf-8'))
  print("1" if d.get(key, False) else "0")
except Exception:
  print("0")
PY
}

file_path="$(
  PAYLOAD="$payload" python3 - <<'PY'
import json, os
payload = os.environ.get("PAYLOAD") or ""
try:
    data = json.loads(payload)
except json.JSONDecodeError:
    print("")
else:
    print(data.get("tool_input", {}).get("file_path", ""))
PY
)"

[[ -f config/gates.json ]] || exit 0
[[ "$(json_get_bool config/gates.json db_migration)" == "1" ]] || exit 0

# триггеры: сущности/репозитории/схема
if [[ ! "$file_path" =~ (^|/)src/main/.*(entity|model|repository)/.*\.(kt|java)$ ]] && \
   [[ ! "$file_path" =~ (^|/)src/main/resources/.*/db/(schema|tables)\.(sql|ddl)$ ]]; then
  exit 0
fi

# ищем новую миграцию среди изменённых/неотслеживаемых файлов
has_migration=0
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  if git diff --name-only HEAD | grep -E '(^|/)src/main/resources/(.*/)?db/migration/.*\.(sql|xml|yaml)$' >/dev/null 2>&1; then
    has_migration=1
  fi
fi
if [[ $has_migration -eq 0 ]]; then
  if git ls-files --others --exclude-standard | grep -E '(^|/)src/main/resources/(.*/)?db/migration/.*\.(sql|xml|yaml)$' >/dev/null 2>&1; then
    has_migration=1
  fi
fi

if [[ $has_migration -eq 0 ]]; then
  echo "BLOCK: изменения модели/схемы требуют миграции в src/main/resources/**/db/migration/" 1>&2
  echo "Подсказка: вызовите саб-агента db-migrator или создайте файл V<timestamp>__<slug>.sql вручную." 1>&2
  exit 2
fi
exit 0
BASH
  set_executable ".claude/hooks/gate-db-migration.sh"

  write_template ".claude/hooks/gate-tests.sh" <<'BASH'
#!/usr/bin/env bash
# Требует наличие теста для редактируемого исходника (soft/hard режим)
set -euo pipefail
payload="$(cat)"

json_get_str() {
  python3 - <<'PY' "$1" "$2" "$3"
import json,sys
cfg, key, dv = sys.argv[1], sys.argv[2], sys.argv[3]
try:
  d=json.load(open(cfg,'r',encoding='utf-8'))
  print(str(d.get(key, dv)))
except Exception:
  print(dv)
PY
}

file_path="$(
  PAYLOAD="$payload" python3 - <<'PY'
import json, os
payload = os.environ.get("PAYLOAD") or ""
try:
    data = json.loads(payload)
except json.JSONDecodeError:
    print("")
else:
    print(data.get("tool_input", {}).get("file_path", ""))
PY
)"

mode="$(json_get_str config/gates.json tests_required disabled)"
[[ "$mode" == "disabled" ]] && exit 0

# интересует только src/main и *.kt|*.java
if [[ ! "$file_path" =~ (^|/)src/main/ ]] || [[ ! "$file_path" =~ \.(kt|java)$ ]]; then
  exit 0
fi

# выведем ожидаемые имена тестов (Kotlin/Java)
rel="${file_path#*src/main/}"
test1="src/test/${rel%.*}Test.${file_path##*.}"
test2="src/test/${rel%.*}Tests.${file_path##*.}"

if [[ -f "$test1" || -f "$test2" ]]; then
  exit 0
fi

if [[ "$mode" == "soft" ]]; then
  echo "WARN: отсутствует тест для ${file_path}. Рекомендуется создать ${test1}." 1>&2
  exit 0
fi

echo "BLOCK: нет теста для ${file_path}. Создайте ${test1} (или ${test2}) или выполните /tests-generate <slug>." 1>&2
exit 2
BASH
  set_executable ".claude/hooks/gate-tests.sh"

  write_template ".claude/hooks/lint-deps.sh" <<'BASH'
#!/usr/bin/env bash
# Предупреждает о зависимостях вне allowlist при изменении Gradle файлов (не блокирует)
set -euo pipefail
[[ -f config/gates.json ]] || exit 0
allow_deps="$(python3 - <<'PY'
import json
try:
  d=json.load(open('config/gates.json','r',encoding='utf-8'))
  print('1' if d.get('deps_allowlist', False) else '0')
except Exception:
  print('0')
PY
)"
[[ "$allow_deps" == "1" ]] || exit 0
[[ -f config/allowed-deps.txt ]] || exit 0

mapfile -t allowed < <(grep -Ev '^\s*(#|$)' config/allowed-deps.txt | sed 's/[[:space:]]//g')
is_allowed() { local ga="$1"; for a in "${allowed[@]}"; do [[ "$ga" == "$a" ]] && return 0; done; return 1; }

# Смотрим добавленные строки в Gradle файлах
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  mapfile -t added < <(git diff --unified=0 --no-color HEAD -- '**/build.gradle*' 'gradle/libs.versions.toml' | grep '^\+' || true)
else
  added=()
fi

for line in "${added[@]}"; do
  ga=""
  if [[ "$line" =~ (implementation|api|compileOnly|runtimeOnly)\([\"\' ]*([^:\"\'\)]+:[^:\"\'\)]+) ]]; then
    ga="${BASH_REMATCH[2]}"
  fi
  [[ -z "$ga" ]] && continue
  if ! is_allowed "$ga"; then
    echo "WARN: dependency '$ga' не в allowlist (config/allowed-deps.txt)" 1>&2
  fi
done

exit 0
BASH
  set_executable ".claude/hooks/lint-deps.sh"

  write_template ".claude/gradle/init-print-projects.gradle" <<'GRADLE'
gradle.settingsEvaluated {
  gradle.rootProject {
    tasks.register("ccPrintProjectDirs") {
      doLast { allprojects { println("${it.path}=${it.projectDir.absolutePath}") } }
    }
  }
}
GRADLE
}

generate_hook_format_test() {
  write_template ".claude/hooks/format-and-test.sh" <<'BASH'
#!/usr/bin/env python3
"""Unified formatter and test runner hook.

Reads automation settings from .claude/settings.json (or CLAUDE_SETTINGS_PATH),
runs configured formatting commands, then executes the appropriate test tasks
depending on the change scope and configuration flags.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List

LOG_PREFIX = "[format-and-test]"
ROOT_DIR = Path(__file__).resolve().parents[2]
SETTINGS_PATH = Path(
    os.environ.get("CLAUDE_SETTINGS_PATH", ROOT_DIR / ".claude" / "settings.json")
)
COMMON_PATTERNS = (
    "config/",
    "gradle/libs.versions.toml",
    "settings.gradle",
    "settings.gradle.kts",
    "build.gradle",
    "build.gradle.kts",
    "buildSrc/",
)


def log(message: str) -> None:
    print(f"{LOG_PREFIX} {message}", file=sys.stderr)


def fail(message: str, code: int = 1) -> int:
    log(message)
    return code


def load_config() -> dict | None:
    if not SETTINGS_PATH.exists():
        log(f"Конфигурация {SETTINGS_PATH} не найдена — шаги пропущены.")
        return None
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(fail(f"Не удалось разобрать {SETTINGS_PATH}: {exc}", 1))


def run_subprocess(cmd: List[str], strict: bool = True) -> bool:
    log(f"→ {' '.join(cmd)}")
    result = subprocess.run(cmd, text=True)
    if result.returncode == 0:
        return True
    if strict:
        log(f"Команда завершилась с ошибкой (exit={result.returncode}).")
    return False


def env_flag(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return value not in {"0", "false", "False"}


def collect_changed_files() -> List[str]:
    files: set[str] = set()

    def git_lines(args: Iterable[str]) -> List[str]:
        proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        if proc.returncode != 0:
            return []
        return [line.strip() for line in proc.stdout.splitlines() if line.strip()]

    proc = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if proc.returncode == 0:
        files.update(git_lines(["git", "diff", "--name-only", "HEAD"]))

    files.update(git_lines(["git", "ls-files", "--others", "--exclude-standard"]))
    return sorted(files)


def append_unique(container: List[str], value: str) -> None:
    if value and value not in container:
        container.append(value)


def parse_scope(value: str) -> List[str]:
    items: List[str] = []
    for chunk in value.replace(",", " ").split():
        chunk = chunk.strip()
        if chunk:
            append_unique(items, chunk)
    return items


def determine_project_dir() -> Path:
    if "CLAUDE_PROJECT_DIR" in os.environ:
        return Path(os.environ["CLAUDE_PROJECT_DIR"]).resolve()
    settings_parent = SETTINGS_PATH.parent
    if settings_parent.name == ".claude":
        return settings_parent.parent.resolve()
    return settings_parent.resolve()


def main() -> int:
    os.chdir(determine_project_dir())
    config = load_config()
    if config is None:
        return 0

    automation = config.get("automation", {})
    format_cfg = automation.get("format", {})
    format_commands = [
        [str(part) for part in cmd]
        for cmd in format_cfg.get("commands", [])
        if isinstance(cmd, list)
    ]

    tests_cfg = automation.get("tests", {})
    runner_cfg = tests_cfg.get("runner", "./gradlew")
    if isinstance(runner_cfg, list):
        test_runner = [str(part) for part in runner_cfg]
    else:
        test_runner = [str(runner_cfg)]

    default_tasks = [str(task) for task in tests_cfg.get("defaultTasks", [":test"])]
    fallback_tasks = [str(task) for task in tests_cfg.get("fallbackTasks", [])]
    module_matrix = [
        {"match": str(item.get("match", "")), "tasks": [str(t) for t in item.get("tasks", [])]}
        for item in tests_cfg.get("moduleMatrix", [])
        if isinstance(item, dict)
    ]
    changed_only_default = bool(tests_cfg.get("changedOnly", True))
    strict_default = bool(tests_cfg.get("strictDefault", 1))

    skip_format = os.environ.get("SKIP_FORMAT", "0") == "1"
    if skip_format:
        log("SKIP_FORMAT=1 — форматирование пропущено.")
    else:
        if not format_commands:
            log("Команды форматирования не настроены (automation.format.commands).")
        else:
            for cmd in format_commands:
                if not run_subprocess(cmd):
                    return 1

    if os.environ.get("FORMAT_ONLY", "0") == "1":
        log("FORMAT_ONLY=1 — стадия тестов пропущена.")
        return 0

    strict_flag = env_flag("STRICT_TESTS")
    if strict_flag is None:
        strict_flag = strict_default

    changed_only_flag = env_flag("TEST_CHANGED_ONLY")
    if changed_only_flag is None:
        changed_only_flag = changed_only_default

    test_tasks: List[str] = []
    test_scope_env = os.environ.get("TEST_SCOPE")
    if test_scope_env:
        for item in parse_scope(test_scope_env):
            append_unique(test_tasks, item)
        changed_only_flag = False

    changed_files = collect_changed_files()
    active_slug_path = Path("docs/.active_feature")
    active_slug = active_slug_path.read_text(encoding="utf-8").strip() if active_slug_path.exists() else ""

    if active_slug and changed_files:
        common_hits = [
            path
            for path in changed_files
            if any(path == pattern or path.startswith(pattern) for pattern in COMMON_PATTERNS)
        ]
        if common_hits:
            changed_only_flag = False
            log(
                f"Активная фича '{active_slug}', изменены общие файлы: {' '.join(common_hits)} — полный прогон тестов."
            )

    if changed_only_flag and changed_files and module_matrix:
        matrix_tasks: List[str] = []
        for item in module_matrix:
            match = item.get("match", "")
            if not match:
                continue
            if any(path.startswith(match) for path in changed_files):
                for task in item.get("tasks", []):
                    append_unique(matrix_tasks, task)
        for task in matrix_tasks:
            append_unique(test_tasks, task)

    if not test_tasks:
        for task in default_tasks:
            append_unique(test_tasks, task)

    if not test_tasks:
        for task in fallback_tasks:
            append_unique(test_tasks, task)

    if not test_tasks:
        log("Нет задач для запуска тестов — проверка пропущена.")
        return 0

    log(f"Выбранные задачи тестов: {' '.join(test_tasks)}")

    if not test_runner or not test_runner[0]:
        log("Не указан runner для тестов — стадия пропущена.")
        return 0

    command = test_runner + test_tasks
    log(f"Запуск тестов: {' '.join(command)}")
    result = subprocess.run(command, text=True)
    if result.returncode == 0:
        log("Тесты завершились успешно.")
        return 0

    if strict_flag:
        return fail("Тесты завершились с ошибкой (STRICT_TESTS=1).", result.returncode)

    log("Тесты завершились с ошибкой, но STRICT_TESTS != 1 — продолжаем.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
BASH
  set_executable ".claude/hooks/format-and-test.sh"
}
generate_agents() {
  write_template ".claude/agents/analyst.md" <<'MD'
---
name: analyst
description: Сбор свободной идеи → уточняющие вопросы → PRD. Превращает сырую идею в спецификацию.
tools: Read, Write, Grep, Glob
model: inherit
---
Ты — продуктовый аналитик. Преобразуй сырую идею в PRD.
Правила:
1) Итеративно задавай конкретные вопросы (формат: "Вопрос N: …" + краткие варианты/пояснения).
2) После ответов — оформи PRD по шаблону @docs/prd.template.md в `docs/prd/$SLUG.prd.md`.
3) Явно перечисли открытые риски/допущения. Если что-то не ясно — снова спроси.
4) Заверши кратким резюме статуса: READY|BLOCKED и списком открытых вопросов.

Выводи только готовый PRD и список открытых вопросов при необходимости.
MD

  write_template ".claude/agents/planner.md" <<'MD'
---
name: planner
description: План реализации по согласованному PRD. Декомпозиция на итерации и проверяемые шаги.
tools: Read, Write, Grep, Glob
model: inherit
---
Ты — технический планировщик. На основе `docs/prd/$SLUG.prd.md` создай `docs/plan/$SLUG.md`:
- Архитектурные решения (KISS/YAGNI/MVP), границы модулей.
- Пошаговый план (итерации) с критериями готовности (DoD) и метриками проверки.
- Ссылки на файлы/модули, затрагиваемые изменениями.

Если остаются неопределённости — сформируй список вопросов пользователю и пометь общий статус BLOCKED.
Выводи итоговый план и список вопросов, если есть.
MD

  write_template ".claude/agents/validator.md" <<'MD'
---
name: validator
description: Валидация полноты PRD/плана; формирование вопросов к пользователю.
tools: Read
model: inherit
---
Проверь `docs/prd/$SLUG.prd.md` и `docs/plan/$SLUG.md` по критериям:
- Полнота user stories и acceptance criteria
- Зависимости/риски/фич‑флаги
- Границы модулей и интеграции

Дай статус для каждого раздела (PASS|FAIL) и общий статус:
- Если FAIL — перечисли конкретные вопросы к пользователю и пометь общий статус BLOCKED.
- Если PASS — кратко резюмируй почему.
MD

  write_template ".claude/agents/implementer.md" <<'MD'
---
name: implementer
description: Реализация задачи. При неопределённости — задаёт вопросы пользователю; запускает тесты.
tools: Read, Edit, Write, Grep, Glob, Bash(./gradlew:*), Bash(gradle:*)
model: inherit
---
Действия:
1) Сверься с `docs/plan/$SLUG.md` и чеклистом задач.
2) Пиши код малыми итерациями, каждый шаг — отдельный коммит (используй `/commit`).
3) После каждой правки запускай `/test-changed`. При падениях — исправь и повтори.
4) Если не ясно, какой алгоритм/интеграцию/БД использовать — остановись и задай вопрос пользователю.

Выводи только план следующего шага и изменения в коде. Без лишней болтовни.
MD

  write_template ".claude/agents/reviewer.md" <<'MD'
---
name: reviewer
description: Ревью кода. Проверка качества, безопасности, тестов. Возвращает замечания в задачи.
tools: Read, Grep, Glob, Bash(git diff:*), Bash(./gradlew:*), Bash(gradle:*)
model: inherit
---
Шаги:
1) Проанализируй `git diff` и соответствие PRD/плану.
2) Проверь тесты (попроси выполнить `/test-changed` при необходимости).
3) Найди дефекты/риски (конкурентность, транзакции, NPE, boundary conditions).
4) Сформируй actionable‑замечания. Если критично — статус BLOCKED, иначе SUGGESTIONS.

Выводи краткий отчёт (итоговый статус + список замечаний).
MD

  write_template ".claude/agents/api-designer.md" <<'MD'
---
name: api-designer
description: Проектирует контракт API (OpenAPI) по PRD. Обновляет docs/api/$SLUG.yaml.
tools: Read, Write, Grep, Glob
model: inherit
---
Задача: на основе `docs/prd/$SLUG.prd.md` спроектируй HTTP API в формате OpenAPI 3.0+.
Требования:
- CRUD-ручки и нестандартные операции должны иметь чёткие схемы запросов/ответов.
- Статусы ошибок и коды описать (error schema).
- Версионирование и фич-флаг для новой ручки (если применимо).
- Укажи пример payload и пограничные случаи (empty, large, invalid).

Запиши контракт в `docs/api/$SLUG.yaml` (или дополни существующий), сохраняя валидный YAML.
В конце кратко перечисли неясности (если есть) — статус READY|BLOCKED.
MD

  write_template ".claude/agents/db-migrator.md" <<'MD'
---
name: db-migrator
description: Готовит миграции БД (Flyway/Liquibase) по изменениям в модели/схеме.
tools: Read, Write, Grep, Glob
model: inherit
---
Найди изменения в доменной модели/схеме (entity/*, schema.sql).
Сгенерируй миграцию (по принятому инструменту) в `src/main/resources/db/migration/` с именованием:
- Flyway: `V<timestamp>__<slug>_<short>.sql`
- Liquibase: файл `changelog-<timestamp>-<slug>.xml` и include в master.

Убедись, что миграция идемпотентна (IF NOT EXISTS / CREATE OR REPLACE …) и обратима (если политика требует).
Добавь заметку в план/задачи, если есть ручные шаги.
MD

  write_template ".claude/agents/contract-checker.md" <<'MD'
---
name: contract-checker
description: Сверяет контроллеры/эндпоинты с OpenAPI контрактом. Выявляет расхождения.
tools: Read, Grep, Glob
model: inherit
---
Проверь соответствие кода и контракта:
- Найди контроллеры/роуты (Spring/Ktor) по `$MODULE/src/main/**/(controller|web|rest)/**`.
- Сверь пути/методы/коды ответа/модели с `docs/api/$SLUG.yaml`.
- Выяви несовпадающие элементы (лишние/отсутствующие эндпоинты, статусы, поля).

Сформируй отчёт с actionable-исправлениями (куда и что добавить/поправить).
Если критично — статус BLOCKED; иначе SUGGESTIONS.
MD

  write_template ".claude/agents/qa-author.md" <<'MD'
---
name: qa-author
description: Создаёт юнит/интеграционные тесты и сценарии ручной проверки.
tools: Read, Write, Grep, Glob, Bash(./gradlew:*), Bash(gradle:*)
model: inherit
---
Список задач:
1) На основе `docs/plan/$SLUG.md` и изменённого кода — допиши/создай юнит-тесты (`src/test/**`) для критичной логики.
2) При необходимости добавь фейковые адаптеры/фабрики данных.
3) Сформируй `docs/test/$SLUG-manual.md` со сценариями ручной проверки (positive/negative/boundary).
4) Запусти `/test-changed` и приложи краткий отчёт, что покрыто тестами.
MD
}

generate_commands() {
  write_template ".claude/commands/feature-activate.md" <<'MD'
---
description: "Установить активную фичу для гейтов (docs/.active_feature)"
argument-hint: "<slug>"
allowed-tools: Bash(*),Read,Write
---
Создай/перезапиши файл `docs/.active_feature` значением `$1`:
!`mkdir -p docs && printf "%s" "$1" > docs/.active_feature && echo "active feature: $1"`
MD

  write_template ".claude/commands/idea-new.md" <<'MD'
---
description: "Инициация фичи: сбор идеи → уточнения → PRD"
argument-hint: "<slug> [TICKET]"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(*)
---
1) Установи активную фичу: создавай/перезапиши файл `docs/.active_feature` значением `$1`.
2) Используя @docs/prd.template.md, @conventions.md и @workflow.md, создай/обнови `docs/prd/$1.prd.md`.
3) Вызови саб‑агента **analyst** для итеративного уточнения идеи. Если передан TICKET ($2) — добавь раздел Tracking.

Выполни:
!`mkdir -p docs && printf "%s" "$1" > docs/.active_feature && echo "active feature: $1"`
MD

  write_template ".claude/commands/plan-new.md" <<'MD'
---
description: "План реализации по согласованному PRD + валидация"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
1) Вызови саб‑агента **planner** для создания `docs/plan/$1.md` на основе `docs/prd/$1.prd.md`.
2) Затем вызови саб‑агента **validator**. Если статус BLOCKED — верни список вопросов пользователю.
3) Обнови раздел «Открытые вопросы» в PRD/плане.
MD

  write_template ".claude/commands/tasks-new.md" <<'MD'
---
description: "Сформировать чеклист задач (tasklist.md) для фичи"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
На основе `docs/plan/$1.md` обнови @tasklist.md: добавь задачи с чекбоксами по шагам плана
(реализация, тесты, документация, ревью), отметь зависимости и критерии приёмки.
MD

  write_template ".claude/commands/implement.md" <<'MD'
---
description: "Реализация фичи по плану + выборочные тесты"
argument-hint: "<slug>"
allowed-tools: Bash("$CLAUDE_PROJECT_DIR/.claude/hooks/format-and-test.sh:*"),Read,Edit,Write,Grep,Glob
---
1) Вызови саб‑агента **implementer** для выполнения шага реализации по `docs/plan/$1.md`.
2) После каждой правки запускай `/test-changed` — автозапуск срабатывает автоматически после успешных правок (отключить: `SKIP_AUTO_TESTS=1`).
3) Если возникает неопределённость (алгоритм/интеграция/БД) — приостановись и задавай вопросы пользователю.
MD

  write_template ".claude/commands/review.md" <<'MD'
---
description: "Код-ревью и возврат замечаний в задачи"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(git diff:*)
---
Вызови саб‑агента **reviewer** для ревью изменений по `$1`.
При критичных замечаниях — статус BLOCKED и вернуть задачу саб‑агенту implementer; иначе — внести рекомендации в @tasklist.md.
MD

  write_template ".claude/commands/tests-generate.md" <<'MD'
---
description: "Сгенерировать тесты к изменённому коду"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(./gradlew:*),Bash(gradle:*)
---
Вызови саб-агента **qa-author**. Цели:
1) Создать/обновить юнит-тесты для изменённого кода (по `git diff`).
2) При необходимости — добавить интеграционные тесты (mock/stub) для внешних взаимодействий.
3) Сохранить короткие сценарии ручной проверки в `docs/test/$1-manual.md`.
4) Запустить `/test-changed`.
MD

  write_template ".claude/commands/api-spec-new.md" <<'MD'
---
description: "Создать/обновить OpenAPI контракт для фичи"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Создай каталог `docs/api/` (если нет). Вызови саб-агента **api-designer** для формирования/обновления `docs/api/$1.yaml` на основе `docs/prd/$1.prd.md`.
Если контракт уже существует — корректно смержи изменения.
MD

  write_template ".claude/commands/docs-generate.md" <<'MD'
---
description: "Актуализировать обзорную документацию"
allowed-tools: Read,Edit,Write,Grep,Glob
---
На основе текущих PRD/планов обнови `docs/intro.md`, добавь ссылки на артефакты и синхронизируй раздел в README.
Выложи короткий changelog (основные изменения, риски, тесты).
MD

  write_template ".claude/commands/test-changed.md" <<'MD'
---
description: "Прогнать тесты по затронутым Gradle-модулям"
allowed-tools: Bash("$CLAUDE_PROJECT_DIR/.claude/hooks/format-and-test.sh:*"),Read
---
!`"$CLAUDE_PROJECT_DIR/.claude/hooks/format-and-test.sh"`
MD

  write_template ".claude/commands/conventions-sync.md" <<'MD'
---
description: "Синхронизировать conventions.md с Gradle конфигами"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Просмотри build.gradle*, settings.gradle*, gradle/libs.versions.toml; обнови @conventions.md разделы стиль/линт/тесты.
MD

  write_template ".claude/commands/branch-new.md" <<'MD'
---
description: "Создать ветку по пресету (feature/..., feat/..., mixed)"
argument-hint: "<type> <args>"
allowed-tools: Bash(git checkout:*),Bash(python3 scripts/branch_new.py:*),Read
---
!`python3 scripts/branch_new.py $ARGUMENTS | { read n; git checkout -b "$n" || git checkout "$n"; echo "branch: $n"; }`
MD

  write_template ".claude/commands/commit.md" <<'MD'
---
description: "Собрать коммит согласно config/conventions.json"
argument-hint: "<summary>"
allowed-tools: Bash(git add:*),Bash(git commit:*),Bash(python3 scripts/commit_msg.py:*),Read
---
!`msg="$(python3 scripts/commit_msg.py --summary "$ARGUMENTS")"; git add -A && git commit -m "$msg" && echo "$msg"`
MD

  write_template ".claude/commands/commit-validate.md" <<'MD'
---
description: "Проверить сообщение коммита по текущему пресету"
argument-hint: "<message>"
allowed-tools: Bash(python3 scripts/commit_msg.py:*),Read
---
!`python3 scripts/commit_msg.py --validate "$ARGUMENTS" && echo "OK"`
MD

  write_template ".claude/commands/conventions-set.md" <<'MD'
---
description: "Переключить режим: ticket-prefix | conventional | mixed"
argument-hint: "<commit-mode>"
allowed-tools: Bash(python3 scripts/conventions_set.py:*),Read,Edit,Write
---
!`python3 scripts/conventions_set.py --commit-mode "$ARGUMENTS" && echo "commit.mode set to $ARGUMENTS"`
MD
}

generate_config_and_scripts() {
  write_template "config/conventions.json" <<'JSON'
{
  "commit": {
    "mode": "__COMMIT_MODE__",
    "ticket": {
      "branch_pattern": "^feature/(?P<ticket>[A-Z]+-\\d+)(?:/.*)?$",
      "format": "{ticket}: {summary}"
    },
    "conventional": {
      "types": ["feat","fix","chore","docs","test","refactor","perf","build","ci","revert"],
      "branch_pattern": "^(?P<type>feat|fix|chore|docs|test|refactor|perf|build|ci|revert)/(?P<scope>[\\w\\-]+)$",
      "format": "{type}({scope}): {summary}"
    },
    "mixed": {
      "branch_pattern": "^feature/(?P<ticket>[A-Z]+-\\d+)/(?:)(?P<type>feat|fix|chore|docs|refactor|perf)/(?P<scope>[\\w\\-]+)$",
      "format": "{ticket} {type}({scope}): {summary}"
    }
  },
  "branch": {
    "allowed": [
      "^feature/[A-Z]+-\\d+(?:/.*)?$",
      "^(feat|fix|chore|docs|test|refactor|perf|build|ci|revert)/[\\w\\-]+$",
      "^hotfix/[A-Z]+-\\d+$",
      "^release/v\\d+\\.\\d+\\.\\d+$"
    ],
    "mainline": "main"
  }
}
JSON

  write_template "config/gates.json" <<'JSON'
{
  "feature_slug_source": "docs/.active_feature",
  "api_contract": true,
  "db_migration": true,
  "tests_required": "soft",
  "deps_allowlist": false
}
JSON

  write_template "config/allowed-deps.txt" <<'TXT'
# Разрешённые зависимости в формате group:artifact (без версии)
org.jetbrains.kotlin:kotlin-stdlib
org.jetbrains.kotlin:kotlin-reflect
org.jetbrains.kotlinx:kotlinx-coroutines-core
com.fasterxml.jackson.core:jackson-databind
com.fasterxml.jackson.module:jackson-module-kotlin
org.springframework.boot:spring-boot-starter-web
org.springframework.boot:spring-boot-starter-test
io.ktor:ktor-server-core
io.ktor:ktor-server-netty
org.junit.jupiter:junit-jupiter
org.assertj:assertj-core
TXT

  write_template "scripts/commit_msg.py" <<'PY'
#!/usr/bin/env python3
import json,re,subprocess,sys,argparse
CFG='config/conventions.json'
def load_cfg():
  with open(CFG,'r',encoding='utf-8') as f: return json.load(f)
def git_branch():
  try: return subprocess.check_output(["git","rev-parse","--abbrev-ref","HEAD"]).decode().strip()
  except: return ""
def validate_msg(mode,msg):
  pats={
    "ticket-prefix": r"^[A-Z]+-\\d+: .+",
    "conventional":  r"^(feat|fix|chore|docs|test|refactor|perf|build|ci|revert)(\\([\\w\\-\\*]+\\))?: .+",
    "mixed":         r"^[A-Z]+-\\d+ (feat|fix|chore|docs|refactor|perf)(\\([\\w\\-\\*]+\\))?: .+"
  }
  return re.match(pats.get(mode,"^.+$"), msg or "") is not None
def build(cfg,mode,branch,summary,typ=None):
  c=cfg["commit"]
  if mode=="ticket-prefix":
    m=re.match(c["ticket"]["branch_pattern"], branch or "") or sys.exit(f"[commit] Branch '{branch}' not ticket-prefix")
    ticket=m.group("ticket");  return c["ticket"]["format"].format(ticket=ticket,summary=summary)
  if mode=="conventional":
    m=re.match(c["conventional"]["branch_pattern"], branch or "") or sys.exit("[commit] Branch must be 'feat/scope' etc")
    typ=(typ or m.group("type")); scope=m.group("scope"); return c["conventional"]["format"].format(type=typ,scope=scope,summary=summary)
  if mode=="mixed":
    m=re.match(c["mixed"]["branch_pattern"], branch or "") or sys.exit("[commit] Branch must be 'feature/TICKET/{type}/{scope}'")
    ticket=m.group("ticket"); typ=(typ or m.group("type")); scope=m.group("scope"); return c["mixed"]["format"].format(ticket=ticket,type=typ,scope=scope,summary=summary)
  sys.exit(f"[commit] Unknown mode: {mode}")
def main():
  ap=argparse.ArgumentParser()
  ap.add_argument("--summary", required=False, default="")
  ap.add_argument("--type")
  ap.add_argument("--branch")
  ap.add_argument("--mode")
  ap.add_argument("--validate")
  a=ap.parse_args()
  cfg=load_cfg(); mode=a.mode or cfg["commit"]["mode"]
  if a.validate is not None:
    print("OK" if validate_msg(mode, a.validate.strip()) else "FAIL"); sys.exit(0)
  if not a.summary.strip(): sys.exit("[commit] require --summary")
  branch=a.branch or git_branch()
  print(build(cfg,mode,branch,a.summary.strip(),a.type))
if __name__=="__main__": main()
PY
  set_executable "scripts/commit_msg.py"

  write_template "scripts/branch_new.py" <<'PY'
#!/usr/bin/env python3
import re,sys,argparse
ap=argparse.ArgumentParser()
ap.add_argument("type"); ap.add_argument("arg1", nargs="?"); ap.add_argument("arg2", nargs="?"); ap.add_argument("arg3", nargs="?")
a=ap.parse_args()
t=a.type; name=""
if t=="feature":
  if not a.arg1 or not re.match(r"^[A-Z]+-\\d+$", a.arg1): sys.exit("Use: feature <TICKET>")
  name=f"feature/{a.arg1}"
elif t in ("feat","fix","chore","docs","test","refactor","perf","build","ci","revert"):
  if not a.arg1: sys.exit(f"Use: {t} <scope>")
  name=f"{t}/{a.arg1}"
elif t=="hotfix":
  if not a.arg1 or not re.match(r"^[A-Z]+-\\d+$", a.arg1): sys.exit("Use: hotfix <TICKET>")
  name=f"hotfix/{a.arg1}"
elif t=="mixed":
  if not (a.arg1 and a.arg2 and a.arg3): sys.exit("Use: mixed <TICKET> <type> <scope>")
  if not re.match(r"^[A-Z]+-\\d+$", a.arg1): sys.exit("TICKET must be A-Z+-digits")
  if a.arg2 not in ("feat","fix","chore","docs","refactor","perf"): sys.exit("type must be feat|fix|chore|docs|refactor|perf")
  name=f"feature/{a.arg1}/{a.arg2}/{a.arg3}"
else: sys.exit("Unknown branch type")
print(name)
PY
  set_executable "scripts/branch_new.py"

  write_template "scripts/conventions_set.py" <<'PY'
#!/usr/bin/env python3
import json,sys,argparse
CFG='config/conventions.json'
ap=argparse.ArgumentParser(); ap.add_argument("--commit-mode", choices=["ticket-prefix","conventional","mixed"], required=True)
a=ap.parse_args()
with open(CFG,'r+',encoding='utf-8') as f:
  cfg=json.load(f); cfg.setdefault("commit",{})["mode"]=a.commit_mode
  f.seek(0); json.dump(cfg,f,indent=2,ensure_ascii=False); f.truncate()
print(a.commit_mode)
PY
  set_executable "scripts/conventions_set.py"
}

generate_ci_workflow() {
  if [[ "$ENABLE_CI" -eq 1 ]]; then
    write_template ".github/workflows/gradle.yml" <<'YML'
name: Gradle (selective modules)
on: { workflow_dispatch: {} }  # enable pull_request later if needed
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-java@v4
        with: { distribution: 'temurin', java-version: '21' }
      - name: Cache Gradle
        uses: actions/cache@v4
        with:
          path: |
            ~/.gradle/caches
            ~/.gradle/wrapper
          key: gradle-${{ runner.os }}-${{ hashFiles('**/*.gradle*','**/gradle-wrapper.properties','gradle/libs.versions.toml') }}
          restore-keys: gradle-${{ runner.os }}-
      - name: Run selective tests
        run: bash .claude/hooks/format-and-test.sh
YML
  fi
}

final_message() {
  log_info "Claude Code workflow is ready."
  cat <<'EOF'
Open the project in Claude Code and try:
  /branch-new feature STORE-123
  /feature-activate checkout-discounts
  /idea-new checkout-discounts STORE-123
  /plan-new checkout-discounts
  /tasks-new checkout-discounts
  /implement checkout-discounts
  /review checkout-discounts
  /test-changed
EOF
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "Dry run completed. No files were written."
  fi
}

main() {
  parse_args "$@"
  check_dependencies
  generate_directories
  generate_core_docs
  generate_templates
  generate_claude_settings
  generate_hook_format_test
  generate_agents
  generate_commands
  generate_config_and_scripts
  replace_commit_mode
  generate_ci_workflow
  final_message
}

main "$@"
