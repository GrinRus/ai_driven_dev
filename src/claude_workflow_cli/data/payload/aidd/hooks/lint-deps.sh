#!/usr/bin/env bash
# Предупреждает о зависимостях вне allowlist при изменении Gradle файлов (не блокирует)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

[[ "$(hook_config_get_bool config/gates.json deps_allowlist)" == "1" ]] || exit 0
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
  if [[ "$line" =~ (implementation|api|compileOnly|runtimeOnly)\([\"\']([^:\"\'\)]+:[^:\"\'\)]+) ]]; then
    ga="${BASH_REMATCH[2]}"
  fi
  [[ -z "$ga" ]] && continue
  if ! is_allowed "$ga"; then
    echo "WARN: dependency '$ga' не в allowlist (config/allowed-deps.txt)" 1>&2
  fi
done

exit 0
