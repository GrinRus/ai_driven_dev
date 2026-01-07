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
    "reports/prd"
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
  copy_template "conventions.md" "conventions.md"
}

generate_templates() {
  copy_payload_dir "docs"
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
  copy_payload_dir "reports"
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
    log_info "CI workflow templates больше не поставляются автоматически — см. doc/dev/customization.md в репозитории."
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
  generate_claude_settings
  generate_agents
  generate_commands
  generate_plugin
  generate_plugin_hooks
  copy_workspace_plugin_files
  generate_gradle_helpers
  generate_config_and_scripts
  replace_commit_mode
  generate_ci_workflow
  final_message
}

main "$@"
