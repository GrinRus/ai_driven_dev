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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(pwd)"

COMMIT_MODE="ticket-prefix"
ENABLE_CI=0
FORCE=0
DRY_RUN=0
PRESET_NAME=""
PRESET_FEATURE=""
PRESET_RESULT_SLUG=""

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
  --preset NAME        generate demo artifacts for preset (feature-prd|feature-design|feature-plan|feature-impl|feature-release)
  --feature SLUG       feature slug to use with --preset (default derived from doc/backlog.md)
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
      --preset)
        [[ $# -ge 2 ]] || die "--preset requires a value"
        PRESET_NAME="$2"; shift 2;;
      --feature)
        [[ $# -ge 2 ]] || die "--feature requires a value"
        PRESET_FEATURE="$2"; shift 2;;
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

copy_template() {
  local relative="$1"
  local destination="$2"
  local src="$SCRIPT_DIR/$relative"
  local dest_path="$destination"

  if [[ "$dest_path" != /* ]]; then
    dest_path="$ROOT_DIR/$dest_path"
  fi

  if [[ ! -f "$src" ]]; then
    log_warn "missing template source: $relative"
    return
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] copy $relative -> ${dest_path#$ROOT_DIR/}"
    return
  fi

  if [[ -e "$dest_path" && "$src" -ef "$dest_path" ]]; then
    log_info "template $relative already up to date"
    return
  fi

  if [[ -e "$dest_path" && "$FORCE" -ne 1 ]]; then
    log_warn "skip: ${dest_path#$ROOT_DIR/} (exists, use --force to overwrite)"
    return
  fi

  mkdir -p "$(dirname "$dest_path")"
  cp "$src" "$dest_path"
  log_info "copied: ${dest_path#$ROOT_DIR/}"
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

format_bullets() {
  local line has=0
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    has=1
    printf -- "- %s\n" "$line"
  done
  if [[ "$has" -eq 0 ]]; then
    printf -- "- TBD\n"
  fi
}

extract_usage_demo_goals() {
  CLAUDE_TEMPLATE_DIR="$SCRIPT_DIR" python3 - <<'PY'
from pathlib import Path
import os

primary = Path("docs/usage-demo.md")
fallback_dir = Path(os.environ.get("CLAUDE_TEMPLATE_DIR", ""))
fallback = fallback_dir / "docs/usage-demo.md"
path = primary if primary.exists() else fallback
if not path.exists():
    raise SystemExit(0)

lines = path.read_text(encoding="utf-8").splitlines()
capture = False
for line in lines:
    if line.startswith("## "):
        capture = line.strip() == "## Цель сценария"
        continue
    if capture:
        if line.startswith("## "):
            break
        if line.startswith("- "):
            print(line[2:].strip())
PY
}

extract_wave7_defaults() {
  CLAUDE_TEMPLATE_DIR="$SCRIPT_DIR" python3 - <<'PY'
from pathlib import Path
import re
import os
import base64

primary = Path("doc/backlog.md")
fallback_dir = Path(os.environ.get("CLAUDE_TEMPLATE_DIR", ""))
fallback = fallback_dir / "doc/backlog.md"
path = primary if primary.exists() else fallback
slug = ""
title = ""
tasks = []
if path.exists():
    lines = path.read_text(encoding="utf-8").splitlines()
    in_wave7 = False
    collecting = False
    for line in lines:
        if line.startswith("## "):
            in_wave7 = line.strip().lower() == "## wave 7"
            collecting = False
            continue
        if in_wave7 and line.startswith("### "):
            title = line[4:].strip()
            slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
            collecting = True
            continue
        if collecting:
            if line.startswith("### "):
                break
            stripped = line.strip()
            if stripped.startswith("- ["):
                entry = stripped.split("]", 1)[1].strip()
                if entry:
                    tasks.append(entry)
if not slug and title:
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')

joined = "\n".join(tasks)
encoded = base64.b64encode(joined.encode("utf-8")).decode("ascii") if joined else ""
print(slug or "demo-checkout")
print(title or "Demo Checkout Presets")
print(encoded)
PY
}

slug_to_title() {
  local slug="$1"
  slug="${slug//_/ }"
  slug="${slug//-/ }"
  printf '%s\n' "$slug" | awk '{for(i=1;i<=NF;i++){ $i=toupper(substr($i,1,1)) substr($i,2) } print}'
}

copy_presets() {
  local src="${SCRIPT_DIR}/claude-presets"
  local dest="${ROOT_DIR}/claude-presets"
  if [[ ! -d "$src" ]]; then
    log_warn "preset templates missing at $src"
    return
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] sync presets from $src -> $dest"
    return
  fi
  mkdir -p "$dest"
  while IFS= read -r -d '' file; do
    local rel="${file#$src/}"
    local target="$dest/$rel"
    mkdir -p "$(dirname "$target")"
    if [[ -e "$target" && "$FORCE" -ne 1 ]]; then
      log_warn "skip preset: $target (exists, use --force)"
      continue
    fi
    cp "$file" "$target"
    log_info "preset: $target"
  done < <(find "$src" -type f -print0)
}

append_if_missing() {
  local path="$1"
  local marker="$2"
  local content="$3"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] append ${marker} to $path"
    return
  fi
  mkdir -p "$(dirname "$path")"
  if [[ -f "$path" && "$FORCE" -ne 1 ]]; then
    if grep -Fq "$marker" "$path"; then
      log_warn "skip append: ${marker} already present in $path (use --force to duplicate)"
      return
    fi
  fi
  printf '\n%s\n' "$content" >>"$path"
  log_info "updated: $path (${marker})"
}

apply_preset() {
  if [[ -z "$PRESET_NAME" ]]; then
    return
  fi

  local defaults_output="$(extract_wave7_defaults)"
  local default_slug
  default_slug="$(printf '%s\n' "$defaults_output" | sed -n '1p')"
  local default_title
  default_title="$(printf '%s\n' "$defaults_output" | sed -n '2p')"
  local tasks_source=""
  local tasks_b64
  tasks_b64="$(printf '%s\n' "$defaults_output" | sed -n '3p')"
  if [[ -n "$tasks_b64" ]]; then
    tasks_source="$(TASKS_B64="$tasks_b64" python3 - <<'PY'
import base64, os
data = os.environ.get("TASKS_B64", "")
if data:
    try:
        print(base64.b64decode(data.encode("ascii")).decode("utf-8"))
    except Exception:
        pass
PY
)"
  fi

  local slug="${PRESET_FEATURE:-${default_slug:-demo-checkout}}"
  local title=""
  if [[ -n "$PRESET_FEATURE" ]]; then
    title="$(slug_to_title "$slug")"
  else
    title="${default_title:-}"
    if [[ -z "$title" ]]; then
      title="$(slug_to_title "$slug")"
    fi
  fi
  local goals_block
  goals_block="$(extract_usage_demo_goals | format_bullets)"
  local tasks_block
  tasks_block="$(printf '%s' "$tasks_source" | format_bullets)"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] preset ${PRESET_NAME} (feature=${slug})"
    return
  fi

  local release_notes_path="docs/release-notes.md"

  case "$PRESET_NAME" in
    feature-prd)
      write_template "docs/prd/${slug}.prd.md" <<EOF
# PRD — ${title}

## Контекст
- Фича: ${title}
- Цель: автоматизировать пресеты Claude Code для стадий фичи.
- Источники: doc/backlog.md (Wave 7), docs/usage-demo.md.

## Цели и метрики успеха
${goals_block}

## Основные задачи
${tasks_block}

## Открытые вопросы
- Требуется согласовать схему интеграции пресетов с CLI.
- Уточнить команды автозапуска smoke-сценария.
EOF
      ;;
    feature-design)
      write_template "docs/design/${slug}.md" <<EOF
# Дизайн — ${title}

## Вводные
- PRD: docs/prd/${slug}.prd.md
- Workflow: workflow.md
- Preset каталог: claude-presets/

## Архитектура
${tasks_block}

## Риски и ограничения
- Пересоздание артефактов должно быть безопасным (учитываем режим overwrite/append).
- Подбор дефолтных значений для плейсхолдеров берём из doc/backlog.md и docs/usage-demo.md.

## План проверки
${goals_block}
EOF
      ;;
    feature-plan)
      write_template "docs/plan/${slug}.md" <<EOF
# План — ${title}

## Этапы реализации
${tasks_block}

## Контрольные точки
- PRD и дизайн синхронизированы.
- Тасклист обновляется через пресет feature-impl.
- Smoke-сценарий проходит с использованием init-claude-workflow.sh и пресетов.

## Метрики успеха
${goals_block}
EOF
      ;;
    feature-impl)
      local section="## ${title}"
      local checklist_block=""
      if [[ -n "$tasks_source" ]]; then
        while IFS= read -r line; do
          [[ -z "$line" ]] && continue
          checklist_block+="- [ ] ${slug} :: ${line}"$'\n'
        done <<<"$tasks_source"
      fi
      if [[ -z "$checklist_block" ]]; then
        checklist_block="- [ ] ${slug} :: Подтвердить план фичи"$'\n'
      fi
      local block="${section}
${checklist_block}"
      append_if_missing "tasklist.md" "$section" "$block"
      ;;
    feature-release)
      local release_block="## ${title}
- Фича: ${title}
- Проверка пресетов: запланирована
${goals_block}
"
      append_if_missing "$release_notes_path" "## ${title}" "$release_block"
      ;;
    *)
      die "Unknown preset: $PRESET_NAME"
      ;;
  esac
  log_info "preset ${PRESET_NAME} applied for feature ${slug}"
  PRESET_RESULT_SLUG="$slug"
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

  copy_template "templates/tasklist.md" "tasklist.md"
  write_template "docs/plan/.gitkeep" <<'MD'
MD

  write_template "docs/api/.gitkeep" <<'MD'
MD

  write_template "docs/test/.gitkeep" <<'MD'
MD
}

generate_templates() {
  local files=(
    "docs/prd.template.md"
    "docs/adr.template.md"
  )
  for template in "${files[@]}"; do
    copy_template "$template" "$template"
  done
}

generate_claude_settings() {
  copy_template ".claude/settings.json" ".claude/settings.json"

  local hooks=(
    ".claude/hooks/lib.sh"
    ".claude/hooks/protect-prod.sh"
    ".claude/hooks/gate-workflow.sh"
    ".claude/hooks/gate-api-contract.sh"
    ".claude/hooks/gate-db-migration.sh"
    ".claude/hooks/gate-tests.sh"
    ".claude/hooks/lint-deps.sh"
    ".claude/hooks/format-and-test.sh"
  )

  for hook in "${hooks[@]}"; do
    copy_template "$hook" "$hook"
    case "$hook" in
      *.sh|*.py)
        set_executable "$hook"
        ;;
    esac
  done
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
  log_info "Preset catalog available at claude-presets/ (use --preset feature-prd --feature demo-checkout for a demo scaffold)."
  if [[ -n "$PRESET_NAME" && "$DRY_RUN" -eq 0 ]]; then
    log_info "Preset ${PRESET_NAME} scaffolded demo artifacts for feature ${PRESET_RESULT_SLUG}."
  fi
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
  copy_presets
  generate_claude_settings
  generate_agents
  generate_commands
  generate_config_and_scripts
  replace_commit_mode
  generate_ci_workflow
  apply_preset
  final_message
}

main "$@"
