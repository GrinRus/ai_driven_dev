#!/usr/bin/env bash
# Требует наличие теста для редактируемого исходника (soft/hard режим)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=.claude/hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"

mode="$(hook_config_get_str config/gates.json tests_required disabled)"
mode="$(printf '%s' "$mode" | tr '[:upper:]' '[:lower:]')"
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

echo "BLOCK: нет теста для ${file_path}. Создайте ${test1} (или ${test2}) либо переведите tests_required в config/gates.json в soft/disabled." 1>&2
exit 2
