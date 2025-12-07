#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/.." && pwd)"
payload_dir="${PAYLOAD_DIR:-${repo_root}/src/claude_workflow_cli/data/payload/aidd}"

usage() {
  cat <<'EOF'
Usage: scripts/sync-payload.sh [--direction to-root|from-root] [--dry-run]

Sync payload artefacts between src/claude_workflow_cli/data/payload and the
runtime snapshot in the repository root.

Options:
  --direction <mode>  to-root (payload → root) or from-root (root → payload). Default: to-root.
  --dry-run           Show rsync changes without modifying files.
  --paths <list>      Comma-separated subset of paths to sync (optional).
  -h, --help          Show this message.
EOF
}

direction="to-root"
dry_run=0
custom_paths=()

trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --direction)
      shift
      direction="${1:-}"
      ;;
    --direction=*)
      direction="${1#*=}"
      ;;
    --dry-run)
      dry_run=1
      ;;
    --paths)
      shift
      IFS=',' read -r -a custom_paths <<< "${1:-}"
      ;;
    --paths=*)
      IFS=',' read -r -a custom_paths <<< "${1#*=}"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

if [[ ! -d "${payload_dir}" ]]; then
  echo "Payload directory not found: ${payload_dir}" >&2
  exit 1
fi

case "${direction}" in
  to-root)
    src_base="${payload_dir}"
    dst_base="${repo_root}"
    ;;
  from-root)
    src_base="${repo_root}"
    dst_base="${payload_dir}"
    ;;
  *)
    echo "Invalid direction: ${direction} (expected to-root or from-root)" >&2
    exit 1
    ;;
esac

default_paths=(
  ".claude"
  "claude-presets"
  "config"
  "docs"
  "README.md"
  "README.en.md"
  "CHANGELOG.md"
  "templates"
  "tools"
  "workflow.md"
  "CLAUDE.md"
  "conventions.md"
  "init-claude-workflow.sh"
  "scripts/ci-lint.sh"
  "scripts/migrate-tasklist.py"
  "scripts/prd-review-agent.py"
  "scripts/prd_review_gate.py"
  "scripts/qa-agent.py"
  "scripts/smoke-workflow.sh"
)

if [[ ${#custom_paths[@]} -gt 0 ]]; then
  sync_paths=()
  for raw_path in "${custom_paths[@]}"; do
    cleaned="$(trim "$raw_path")"
    if [[ -n "$cleaned" ]]; then
      sync_paths+=("$cleaned")
    fi
  done
  if [[ ${#sync_paths[@]} -eq 0 ]]; then
    sync_paths=("${default_paths[@]}")
  fi
else
  sync_paths=("${default_paths[@]}")
fi

rsync_base=(rsync -a --human-readable --itemize-changes)
if [[ ${dry_run} -eq 1 ]]; then
  rsync_base+=("--dry-run")
fi

sync_path() {
  local relative_path="$1"
  local source_path="${src_base}/${relative_path}"
  local target_path="${dst_base}/${relative_path}"

  if [[ ! -e "${source_path}" ]]; then
    echo "[skip] ${relative_path} missing in ${src_base}"
    return
  fi

  if [[ -d "${source_path}" ]]; then
    mkdir -p "${target_path}"
    "${rsync_base[@]}" --delete "${source_path}/" "${target_path}/"
  else
    mkdir -p "$(dirname "${target_path}")"
    "${rsync_base[@]}" "${source_path}" "${target_path}"
  fi
}

echo "[sync] ${direction} (${src_base} → ${dst_base})"
for path in "${sync_paths[@]}"; do
  sync_path "${path}"
done

if [[ ${dry_run} -eq 1 ]]; then
  echo "[dry-run] No files were modified."
fi
