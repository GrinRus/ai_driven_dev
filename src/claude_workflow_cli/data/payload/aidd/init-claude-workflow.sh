#!/usr/bin/env bash
# init-claude-workflow.sh
# Bootstraps Claude Code workflow for language-agnostic repos.
# Creates .claude commands/agents/hooks, commit/branch conventions,
# optional build-system helpers, and basic docs (PRD/ADR templates).
#
# Usage:
#   bash init-claude-workflow.sh [--commit-mode MODE] [--enable-ci] [--force] [--dry-run]
#     --commit-mode   ticket-prefix | conventional | mixed   (default: ticket-prefix)
#     --enable-ci     add a minimal GitHub Actions workflow (manual trigger)
#     --force         overwrite existing files
#     --dry-run       log planned actions without touching the filesystem
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(pwd)"
WORKSPACE_ROOT="$ROOT_DIR"
if [[ "$(basename "$ROOT_DIR")" == "aidd" ]]; then
  WORKSPACE_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
fi
PAYLOAD_ROOT="${CLAUDE_TEMPLATE_DIR:-$SCRIPT_DIR}"
export CLAUDE_TEMPLATE_DIR="$PAYLOAD_ROOT"

COMMIT_MODE="ticket-prefix"
ENABLE_CI=0
FORCE=0
DRY_RUN=0
PROMPT_LOCALE="ru"
PRESET_NAME=""
PRESET_TICKET=""
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
  --prompt-locale LOCALE   ru | en (default: ru) — copy соответствующие промпты в agents и commands
  --preset NAME        generate demo artifacts for preset (feature-prd|feature-plan|feature-impl|feature-design|feature-release)
  --ticket VALUE       ticket identifier to use with --preset (legacy alias: --feature)
  --feature SLUG       deprecated alias for --ticket
  -h, --help           print this help
EOF
}

ensure_aidd_root() {
  if [[ "$(basename "$ROOT_DIR")" != "aidd" ]]; then
    die "init-claude-workflow.sh must run inside the aidd directory (current: $ROOT_DIR). Use 'claude-workflow init --target <workspace>' to bootstrap."
  fi
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
      --prompt-locale)
        [[ $# -ge 2 ]] || die "--prompt-locale requires a value"
        PROMPT_LOCALE="$2"; shift 2;;
      --preset)
        [[ $# -ge 2 ]] || die "--preset requires a value"
        PRESET_NAME="$2"; shift 2;;
      --ticket)
        [[ $# -ge 2 ]] || die "--ticket requires a value"
        PRESET_TICKET="$2"; shift 2;;
      --feature)
        [[ $# -ge 2 ]] || die "--feature requires a value"
        log_warn "--feature is deprecated; use --ticket instead."
        PRESET_TICKET="$2"; shift 2;;
      -h|--help)   usage; exit 0;;
      *)           die "Unknown argument: $1";;
    esac
  done

  case "$COMMIT_MODE" in
    ticket-prefix|conventional|mixed) ;;
    *) die "Unsupported --commit-mode: $COMMIT_MODE";;
  esac

  case "$PROMPT_LOCALE" in
    ru|en) ;;
    *) die "Unsupported --prompt-locale: $PROMPT_LOCALE";;
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
    log_info "Gradle detected (optional helpers enabled)"
  else
    log_warn "Gradle not found (expect ./gradlew or gradle). Gradle-specific selective tests will be unavailable until installed."
  fi

  if command -v ktlint >/dev/null 2>&1; then
    log_info "ktlint detected (optional formatter)"
  else
    log_warn "ktlint not found. Formatting step will be skipped unless another formatter is configured."
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
  local mode="${3:-copy}"
  local src="$PAYLOAD_ROOT/$relative"
  local dest_path="$destination"

  if [[ "$dest_path" != /* ]]; then
    dest_path="$ROOT_DIR/$dest_path"
  fi

  if [[ ! -f "$src" ]]; then
    log_warn "missing template source: $relative"
    return
  fi

  local rel_dest="${dest_path#"$ROOT_DIR"/}"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    if [[ "$mode" == "append" && -e "$dest_path" && "$FORCE" -ne 1 ]]; then
      log_info "[dry-run] append $relative -> $rel_dest"
    else
      log_info "[dry-run] copy $relative -> $rel_dest"
    fi
    return
  fi

  if [[ -e "$dest_path" && "$src" -ef "$dest_path" ]]; then
    log_info "template $relative already up to date"
    return
  fi

  if [[ -e "$dest_path" ]]; then
    if [[ "$mode" == "append" && "$FORCE" -ne 1 ]]; then
      if [[ -s "$dest_path" ]] && [[ "$(tail -c 1 "$dest_path" 2>/dev/null)" != $'\n' ]]; then
        printf '\n' >>"$dest_path"
      fi
      cat "$src" >>"$dest_path"
      log_info "appended: $rel_dest"
      return
    fi
    if [[ "$FORCE" -ne 1 ]]; then
      log_warn "skip: $rel_dest (exists, use --force to overwrite)"
      return
    fi
  fi

  mkdir -p "$(dirname "$dest_path")"
  cp "$src" "$dest_path"
  log_info "copied: $rel_dest"
}

copy_payload_file() {
  local src="$1"
  local dest="$2"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] copy $src -> $dest"
    return
  fi
  if [[ ! -f "$src" ]]; then
    log_warn "missing source: $src"
    return
  fi
  mkdir -p "$(dirname "$dest")"
  if [[ -e "$dest" && "$FORCE" -ne 1 ]]; then
    log_warn "skip: $dest (exists, use --force to overwrite)"
    return
  fi
  cp "$src" "$dest"
  log_info "copied: $dest"
}

copy_payload_dir() {
  local source_dir="$1"
  local target_dir="${2:-$1}"
  local src_path="$PAYLOAD_ROOT/$source_dir"
  if [[ ! -d "$src_path" ]]; then
    log_warn "missing payload directory: $source_dir"
    return
  fi
  while IFS= read -r -d '' file; do
    local relative="${file#"$src_path"/}"
    if [[ "$relative" == "$file" ]]; then
      relative="$(basename "$file")"
    fi
    copy_template "$source_dir/$relative" "$target_dir/$relative"
  done < <(find "$src_path" -type f -print0)
}

apply_prompt_locale() {
  case "$PROMPT_LOCALE" in
    ru)
      return
      ;;
    en)
      log_info "Applying prompt locale: en"
      local previous_force="$FORCE"
      FORCE=1
      copy_payload_dir "prompts/en/agents" "agents"
      copy_payload_dir "prompts/en/commands" "commands"
      FORCE="$previous_force"
      ;;
  esac
}

ensure_hook_permissions() {
  local hooks_dir="$ROOT_DIR/hooks"
  [[ -d "$hooks_dir" ]] || return 0
  while IFS= read -r -d '' hook; do
    local rel="${hook#"$ROOT_DIR"/}"
    case "$rel" in
      *.sh) set_executable "$rel" ;;
    esac
  done < <(find "$hooks_dir" -type f -print0)
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

preset_default_goals() {
  cat <<'EOF'
- развернуть шаблон всего за один запуск скрипта;
- понять, какие файлы и настройки добавляются;
- проверить, что выборочные тесты и хуки работают сразу после установки;
- пройти многошаговый цикл `/idea-new → claude-workflow research → /plan-new → /tasks-new → /implement → /review` и увидеть работу гейтов (workflow, research, миграции, тесты).
EOF
}

slug_to_title() {
  local slug="$1"
  slug="${slug//_/ }"
  slug="${slug//-/ }"
  printf '%s\n' "$slug" | awk '{for(i=1;i<=NF;i++){ $i=toupper(substr($i,1,1)) substr($i,2) } print}'
}

copy_presets() {
  copy_payload_dir "claude-presets"
}

tasklist_path_for_slug() {
  local slug="$1"
  printf 'docs/tasklist/%s.md\n' "$slug"
}

render_tasklist_template() {
  local slug="$1"
  local title="$2"
  local updated="$3"
  CLAUDE_TEMPLATE_DIR="$PAYLOAD_ROOT" python3 - "$slug" "$title" "$updated" <<'PY'
import os
import sys
from pathlib import Path

slug, title, updated = sys.argv[1:4]
template_candidates = [
    Path("templates/tasklist.md"),
    Path(os.environ.get("CLAUDE_TEMPLATE_DIR", "")) / "templates/tasklist.md",
]
template_text = None
for candidate in template_candidates:
    if candidate.exists():
        template_text = candidate.read_text(encoding="utf-8")
        break
if template_text is None:
    template_text = """---
Ticket: {slug}
Slug hint: {slug}
Feature: {title}
Status: draft
PRD: docs/prd/{slug}.prd.md
Plan: docs/plan/{slug}.md
Research: docs/research/{slug}.md
Updated: {updated}
---

# Tasklist — {title}

## 1. Аналитика и дизайн
- [ ] Обновите пункты чеклиста под свою фичу.
"""

replacements = {
    "<slug>": slug,
    "<ticket>": slug,
    "<slug-hint>": slug,
    "<slug-hint или повторите ticket>": slug,
    "<feature name>": title,
    "<display name>": title,
    "<Feature title>": title,
    "<Feature name>": title,
    "&lt;slug&gt;": slug,
    "&lt;ticket&gt;": slug,
    "&lt;slug-hint&gt;": slug,
    "&lt;slug-hint или повторите ticket&gt;": slug,
    "&lt;feature name&gt;": title,
    "&lt;display name&gt;": title,
    "&lt;Feature title&gt;": title,
    "&lt;Feature name&gt;": title,
    "YYYY-MM-DD": updated,
}

text = template_text
for placeholder, value in replacements.items():
    text = text.replace(placeholder, value)

print(text)
PY
}

ensure_tasklist_file() {
  local slug="$1"
  local title="$2"
  local path
  path="$(tasklist_path_for_slug "$slug")"
  if [[ -f "$path" && "$FORCE" -ne 1 ]]; then
    log_info "tasklist exists: ${path}"
    return
  fi
  local today
  today="$(date +%Y-%m-%d)"
  local content
  content="$(render_tasklist_template "$slug" "$title" "$today")"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] write tasklist ${path}"
    return
  fi
  mkdir -p "$(dirname "$path")"
  printf '%s\n' "$content" >"$path"
  log_info "written: ${path}"
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

  local slug="${PRESET_TICKET:-demo-agent-first}"
  local title
  title="$(slug_to_title "$slug")"
  local goals_block
  goals_block="$(preset_default_goals | format_bullets)"
  local tasks_block
  tasks_block="$(format_bullets < /dev/null)"
  local tasks_source="${TASKS_SOURCE:-}"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] preset ${PRESET_NAME} (ticket=${slug})"
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
- Источники: slug-hint пользователя, workflow.md.

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
- Подбор дефолтных значений для плейсхолдеров берём из workflow.md и пользовательских вводных.

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
      ensure_tasklist_file "$slug" "$title"
      local tasklist_path
      tasklist_path="$(tasklist_path_for_slug "$slug")"
      append_if_missing "$tasklist_path" "$section" "$block"
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
  local plugin_dirs=(
    "commands"
    "agents"
    "hooks"
    "doc"
    "config"
    "docs"
    "reports"
    "reports/qa"
    "reports/research"
  )
  local workspace_dirs=(
    ".claude"
    ".claude/cache"
    ".claude-plugin"
  )
  for dir in "${plugin_dirs[@]}"; do
    ensure_directory "$ROOT_DIR/$dir"
  done
  for dir in "${workspace_dirs[@]}"; do
    ensure_directory "$WORKSPACE_ROOT/$dir"
  done
}

generate_core_docs() {
  copy_template "AGENTS.md" "AGENTS.md" "append"
  copy_template "CLAUDE.md" "CLAUDE.md" "append"
  copy_template "conventions.md" "conventions.md"
  copy_template "workflow.md" "workflow.md"
}

generate_templates() {
  copy_payload_dir "docs"
  copy_template "templates/tasklist.md" "templates/tasklist.md"
  copy_payload_dir "templates/git-hooks" "templates/git-hooks"
}

generate_prompt_references() {
  copy_payload_dir "prompts/en" "prompts/en"
}

generate_claude_settings() {
  copy_payload_dir "../.claude" "$WORKSPACE_ROOT/.claude"
  embed_project_dir_in_settings
}

generate_agents() {
  copy_payload_dir "agents" "agents"
}

generate_commands() {
  copy_payload_dir "commands" "commands"
}

generate_plugin() {
  copy_payload_dir ".claude-plugin"
}

generate_plugin_hooks() {
  copy_payload_dir "hooks" "hooks"
  ensure_hook_permissions
}

copy_workspace_plugin_files() {
  local marketplace_src="$PAYLOAD_ROOT/../.claude-plugin/marketplace.json"
  local marketplace_fallback="$PAYLOAD_ROOT/.claude-plugin/marketplace.json"
  if [[ ! -f "$marketplace_src" && -f "$marketplace_fallback" ]]; then
    marketplace_src="$marketplace_fallback"
  fi

  local destinations=(
    "$marketplace_src::$WORKSPACE_ROOT/.claude-plugin/marketplace.json"
  )

  for pair in "${destinations[@]}"; do
    local src="${pair%%::*}"
    local dest="${pair##*::}"
    local dest_dir
    dest_dir="$(dirname "$dest")"
    if [[ -z "$src" || ! -f "$src" ]]; then
      log_warn "skip workspace plugin file (source missing): $src"
      continue
    fi
    if [[ "$DRY_RUN" -eq 1 ]]; then
      log_info "[dry-run] copy $src -> $dest"
      continue
    fi
    mkdir -p "$dest_dir"
    if [[ -f "$dest" && "$FORCE" -ne 1 ]]; then
      log_warn "skip workspace plugin file: $dest (exists, use --force to overwrite)"
      continue
    fi
    cp "$src" "$dest"
    log_info "workspace plugin file installed: $dest"
  done
}

generate_gradle_helpers() {
  :
}

generate_config_and_scripts() {
  copy_payload_dir "config"
  copy_payload_dir "scripts"
  copy_payload_dir "tools"
  local dirs=("$ROOT_DIR/scripts" "$ROOT_DIR/tools")
  for dir in "${dirs[@]}"; do
    if [[ -d "$dir" ]]; then
      while IFS= read -r -d '' file; do
        local rel="${file#"$ROOT_DIR"/}"
        case "$rel" in
          *.sh|*.py) set_executable "$rel" ;;
        esac
      done < <(find "$dir" -type f -print0)
    fi
  done
}

embed_project_dir_in_settings() {
  local settings_path="$WORKSPACE_ROOT/.claude/settings.json"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] rewrite hook commands in .claude/settings.json"
    return
  fi
  if [[ ! -f "$settings_path" ]]; then
    return
  fi
  local replacements
  replacements="$(python3 - "$settings_path" "$WORKSPACE_ROOT" <<'PY'
import json
import pathlib
import sys

settings_path = pathlib.Path(sys.argv[1])
project_dir = pathlib.Path(sys.argv[2]).resolve()

def update(entries):
    count = 0
    if not isinstance(entries, list):
        return 0
    for entry in entries:
        hooks = entry.get("hooks") if isinstance(entry, dict) else None
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            cmd = hook.get("command") if isinstance(hook, dict) else None
            if isinstance(cmd, str) and "\"$CLAUDE_PROJECT_DIR\"" in cmd:
                hook["command"] = cmd.replace("\"$CLAUDE_PROJECT_DIR\"", f'"{project_dir}"')
                count += 1
    return count

try:
    data = json.loads(settings_path.read_text(encoding="utf-8"))
except Exception:
    print(0)
    raise SystemExit(0)

total = 0
hooks_section = data.get("hooks")
if isinstance(hooks_section, dict):
    total += update(hooks_section.get("PreToolUse"))
    total += update(hooks_section.get("PostToolUse"))

presets = data.get("presets", {}).get("list", {})
if isinstance(presets, dict):
    for preset in presets.values():
        preset_hooks = preset.get("hooks") if isinstance(preset, dict) else None
        if isinstance(preset_hooks, dict):
            total += update(preset_hooks.get("PreToolUse"))
            total += update(preset_hooks.get("PostToolUse"))

if total:
    settings_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(total)
PY
  )"
  replacements="${replacements:-0}"
  if [[ "$replacements" =~ ^[0-9]+$ && "$replacements" -gt 0 ]]; then
    log_info "updated hook commands in .claude/settings.json ($replacements entries)"
  fi
}

generate_ci_workflow() {
  if [[ "$ENABLE_CI" -eq 1 ]]; then
    log_info "CI workflow templates больше не поставляются автоматически — загляните в docs/customization.md для примера GitHub Actions."
  fi
}

final_message() {
  log_info "Claude Code workflow is ready."
  cat <<'EOF'
Open the project in Claude Code and try:
  git checkout -b feature/STORE-123
  /idea-new STORE-123 checkout-discounts
  /plan-new checkout-discounts
  /tasks-new checkout-discounts
  /implement checkout-discounts
  /review checkout-discounts
  ./aidd/hooks/format-and-test.sh
EOF
  log_info "Preset catalog available at claude-presets/ (advanced presets live under claude-presets/advanced/)."
  if [[ -n "$PRESET_NAME" && "$DRY_RUN" -eq 0 ]]; then
    log_info "Preset ${PRESET_NAME} scaffolded demo artifacts for feature ${PRESET_RESULT_SLUG}."
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "Dry run completed. No files were written."
  fi
}

main() {
  parse_args "$@"
  ensure_aidd_root
  check_dependencies
  generate_directories
  generate_core_docs
  generate_templates
  generate_prompt_references
  copy_presets
  generate_claude_settings
  generate_agents
  generate_commands
  generate_plugin
  generate_plugin_hooks
  copy_workspace_plugin_files
  apply_prompt_locale
  generate_gradle_helpers
  generate_config_and_scripts
  replace_commit_mode
  generate_ci_workflow
  apply_preset
  final_message
}

main "$@"
