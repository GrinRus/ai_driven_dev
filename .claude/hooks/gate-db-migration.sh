#!/usr/bin/env bash
# Требует наличие новой миграции Flyway/Liquibase при изменении сущностей/схемы
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=.claude/hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"

[[ "$(hook_config_get_bool config/gates.json db_migration)" == "1" ]] || exit 0

# триггеры: сущности/репозитории/схема
if [[ ! "$file_path" =~ (^|/)src/main/.*(entity|model|repository)/.*\.(kt|java)$ ]] && \
   [[ ! "$file_path" =~ (^|/)src/main/resources/.*/db/(schema|tables)\.(sql|ddl)$ ]]; then
  exit 0
fi

# ищем новую миграцию среди изменённых/неотслеживаемых файлов
has_migration=0
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  if git diff --name-only HEAD | grep -E '(^|/)src/main/resources/(.*/)?db/migration/.*\.(sql|xml|yaml)$' >/dev/null 2>&1; then
    has_migration=1
  fi
fi
if [[ $has_migration -eq 0 ]]; then
  if git ls-files --others --exclude-standard | grep -E '(^|/)src/main/resources/(.*/)?db/migration/.*\.(sql|xml|yaml)$' >/dev/null 2>&1; then
    has_migration=1
  fi
fi

if [[ $has_migration -eq 0 ]]; then
  echo "BLOCK: изменения модели/схемы требуют миграции в src/main/resources/**/db/migration/" 1>&2
  echo "Подсказка: создайте миграцию (например, V<timestamp>__<slug>.sql) или переведите db_migration=false в config/gates.json." 1>&2
  exit 2
fi
exit 0
