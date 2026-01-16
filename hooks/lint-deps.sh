#!/usr/bin/env bash
# Предупреждает о зависимостях вне allowlist при изменении Gradle-манифестов (не блокирует)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"
HOOK_PREFIX="[lint-deps]"
log_stdout() { printf '%s\n' "$*" | hook_prefix_lines "$HOOK_PREFIX"; }

ROOT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
if [[ "$(basename "$ROOT_DIR")" != "aidd" && ( -d "$ROOT_DIR/aidd/docs" || -d "$ROOT_DIR/aidd/hooks" ) ]]; then
  ROOT_DIR="$ROOT_DIR/aidd"
fi
if [[ ! -d "$ROOT_DIR/docs" ]]; then
  exit 0
fi

cd "$ROOT_DIR"

if [[ "${CLAUDE_SKIP_STAGE_CHECKS:-0}" != "1" ]]; then
  active_stage="$(hook_resolve_stage "docs/.active_stage" || true)"
  if [[ "$active_stage" != "implement" ]]; then
    exit 0
  fi
fi

[[ "$(hook_config_get_bool config/gates.json deps_allowlist)" == "1" ]] || exit 0
[[ -f config/allowed-deps.txt ]] || exit 0

allowed=()
while IFS= read -r line; do
  [[ -n "$line" ]] && allowed+=("$line")
done < <(grep -Ev '^\s*(#|$)' config/allowed-deps.txt | sed 's/[[:space:]]//g')
is_allowed() { local ga="$1"; for a in "${allowed[@]}"; do [[ "$ga" == "$a" ]] && return 0; done; return 1; }

# Смотрим добавленные строки в Gradle-манифестах
added=()
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  while IFS= read -r line; do
    [[ -n "$line" ]] && added+=("$line")
  done < <(git diff --unified=0 --no-color HEAD -- '**/build.gradle*' 'gradle/libs.versions.toml' | grep '^\+' || true)
fi

for line in "${added[@]}"; do
  ga=""
  if [[ "$line" =~ (implementation|api|compileOnly|runtimeOnly)\([\"\']([^:\"\'\)]+:[^:\"\'\)]+) ]]; then
    ga="${BASH_REMATCH[2]}"
  fi
  [[ -z "$ga" ]] && continue
  if ! is_allowed "$ga"; then
    log_stdout "WARN: dependency '$ga' не в allowlist (config/allowed-deps.txt)"
  fi
done

exit 0
