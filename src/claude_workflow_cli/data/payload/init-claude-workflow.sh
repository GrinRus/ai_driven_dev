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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(pwd)"

PAYLOAD_ROOT="${CLAUDE_TEMPLATE_DIR:-}"
if [[ -n "$PAYLOAD_ROOT" ]]; then
  PAYLOAD_ROOT="$(cd "$PAYLOAD_ROOT" && pwd)"
else
  if [[ "$SCRIPT_DIR" == */payload ]]; then
    PAYLOAD_ROOT="$SCRIPT_DIR"
  elif [[ -d "$SCRIPT_DIR/src/claude_workflow_cli/data/payload" ]]; then
    PAYLOAD_ROOT="$(cd "$SCRIPT_DIR/src/claude_workflow_cli/data/payload" && pwd)"
  elif [[ -d "$SCRIPT_DIR/payload" ]]; then
    PAYLOAD_ROOT="$(cd "$SCRIPT_DIR/payload" && pwd)"
  elif [[ -d "$SCRIPT_DIR/.claude" ]]; then
    PAYLOAD_ROOT="$SCRIPT_DIR"
  else
    PAYLOAD_ROOT="$SCRIPT_DIR"
  fi
fi
export CLAUDE_TEMPLATE_DIR="$PAYLOAD_ROOT"

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
  --preset NAME        generate demo artifacts for preset (feature-prd|feature-plan|feature-impl|feature-design|feature-release)
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
  local src="$PAYLOAD_ROOT/$relative"
  local dest_path="$destination"

  if [[ "$dest_path" != /* ]]; then
    dest_path="$ROOT_DIR/$dest_path"
  fi

  if [[ ! -f "$src" ]]; then
    log_warn "missing template source: $relative"
    return
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] copy $relative -> ${dest_path#"$ROOT_DIR"/}"
    return
  fi

  if [[ -e "$dest_path" && "$src" -ef "$dest_path" ]]; then
    log_info "template $relative already up to date"
    return
  fi

  if [[ -e "$dest_path" && "$FORCE" -ne 1 ]]; then
    log_warn "skip: ${dest_path#"$ROOT_DIR"/} (exists, use --force to overwrite)"
    return
  fi

  mkdir -p "$(dirname "$dest_path")"
  cp "$src" "$dest_path"
  log_info "copied: ${dest_path#"$ROOT_DIR"/}"
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

ensure_hook_permissions() {
  local hooks_dir="$ROOT_DIR/.claude/hooks"
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

extract_usage_demo_goals() {
  CLAUDE_TEMPLATE_DIR="$PAYLOAD_ROOT" python3 - <<'PY'
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
  CLAUDE_TEMPLATE_DIR="$PAYLOAD_ROOT" python3 - <<'PY'
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
Feature: {slug}
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
    "<feature name>": title,
    "<Feature title>": title,
    "<Feature name>": title,
    "&lt;slug&gt;": slug,
    "&lt;feature name&gt;": title,
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

  local defaults_output
  defaults_output="$(extract_wave7_defaults)"
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
  local dirs=(
    ".claude"
    ".claude/cache"
    "config"
    "docs"
    "reports"
    "reports/qa"
    "reports/research"
  )
  for dir in "${dirs[@]}"; do
    ensure_directory "$dir"
  done
}

generate_core_docs() {
  copy_template "CLAUDE.md" "CLAUDE.md"
  copy_template "conventions.md" "conventions.md"
  copy_template "workflow.md" "workflow.md"
}

generate_templates() {
  copy_payload_dir "docs"
  copy_template "templates/tasklist.md" "templates/tasklist.md"
  copy_payload_dir "templates/git-hooks" "templates/git-hooks"
}

generate_claude_settings() {
  copy_template ".claude/settings.json" ".claude/settings.json"
  copy_payload_dir ".claude/hooks"
  copy_payload_dir ".claude/cache"
  ensure_hook_permissions
}

generate_agents() {
  copy_payload_dir ".claude/agents"
}

generate_commands() {
  copy_payload_dir ".claude/commands"
}

generate_gradle_helpers() {
  copy_payload_dir ".claude/gradle"
}

generate_config_and_scripts() {
  copy_payload_dir "config"
  copy_payload_dir "scripts"
  local scripts_dir="$ROOT_DIR/scripts"
  if [[ -d "$scripts_dir" ]]; then
    while IFS= read -r -d '' script; do
      local rel="${script#"$ROOT_DIR"/}"
      case "$rel" in
        *.sh) set_executable "$rel" ;;
      esac
    done < <(find "$scripts_dir" -type f -print0)
  fi
}

generate_ci_workflow() {
  if [[ "$ENABLE_CI" -eq 1 ]]; then
    copy_template ".github/workflows/gradle.yml" ".github/workflows/gradle.yml"
  fi
}

final_message() {
  log_info "Claude Code workflow is ready."
  cat <<'EOF'
Open the project in Claude Code and try:
  git checkout -b feature/STORE-123
  /idea-new checkout-discounts STORE-123
  /plan-new checkout-discounts
  /tasks-new checkout-discounts
  /implement checkout-discounts
  /review checkout-discounts
  ./.claude/hooks/format-and-test.sh
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
  check_dependencies
  generate_directories
  generate_core_docs
  generate_templates
  copy_presets
  generate_claude_settings
  generate_agents
  generate_commands
  generate_gradle_helpers
  generate_config_and_scripts
  replace_commit_mode
  generate_ci_workflow
  apply_preset
  final_message
}

main "$@"
