#!/usr/bin/env bash
# Блокирует правки контроллеров/роутов, если нет OpenAPI контракта для активной фичи
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=.claude/hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"

[[ "$(hook_config_get_bool config/gates.json api_contract)" == "1" ]] || exit 0

slug_file="$(hook_config_get_str config/gates.json feature_slug_source docs/.active_feature)"
[[ -f "$slug_file" ]] || exit 0
slug="$(hook_read_slug "$slug_file" || true)"
[[ -n "$slug" ]] || exit 0

# если правится не контроллер/роут — пропустим
if [[ ! "$file_path" =~ (^|/)src/main/.*/(controller|rest|web|routes?)/.*\.(kt|java)$ ]] && \
   [[ ! "$file_path" =~ (Controller|Resource)\.(kt|java)$ ]]; then
  exit 0
fi

# проверим наличие контракта
has_spec=0
for p in "docs/api/$slug.yaml" "docs/api/$slug.yml" "docs/api/$slug.json" "src/main/resources/openapi.yaml" "openapi.yaml"; do
  [[ -f "$p" ]] && has_spec=1 && break
done

if [[ $has_spec -eq 0 ]]; then
  echo "BLOCK: нет API контракта для '$slug'. Добавьте docs/api/${slug}.yaml (OpenAPI) или отключите проверку в config/gates.json." 1>&2
  exit 2
fi
exit 0
