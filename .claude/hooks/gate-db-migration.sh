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

file_path="$(printf '%s' "$payload" | python3 - <<'PY'
import json,sys
d=json.load(sys.stdin)
print(d.get("tool_input",{}).get("file_path",""))
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
  if git diff --name-only HEAD | grep -E '(^|/)src/main/resources/.*/db/migration/.*\.(sql|xml|yaml)$' >/dev/null 2>&1; then
    has_migration=1
  fi
fi
if [[ $has_migration -eq 0 ]]; then
  if git ls-files --others --exclude-standard | grep -E '(^|/)src/main/resources/.*/db/migration/.*\.(sql|xml|yaml)$' >/dev/null 2>&1; then
    has_migration=1
  fi
fi

if [[ $has_migration -eq 0 ]]; then
  echo "BLOCK: изменения модели/схемы требуют миграции в src/main/resources/**/db/migration/" 1>&2
  echo "Подсказка: вызовите саб-агента db-migrator или создайте файл V<timestamp>__<slug>.sql вручную." 1>&2
  exit 2
fi
exit 0
