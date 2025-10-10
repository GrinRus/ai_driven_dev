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
