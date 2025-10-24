#!/usr/bin/env bash
# Блокирует правки контроллеров/роутов, если нет OpenAPI контракта для активной фичи
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=.claude/hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"

[[ "$(hook_config_get_bool config/gates.json api_contract)" == "1" ]] || exit 0

ticket_source="$(hook_config_get_str config/gates.json feature_ticket_source docs/.active_ticket)"
slug_hint_source="$(hook_config_get_str config/gates.json feature_slug_hint_source docs/.active_feature)"
ticket="$(hook_read_ticket "$ticket_source" "$slug_hint_source" || true)"
slug_hint="$(hook_read_slug "$slug_hint_source" || true)"
[[ -n "$ticket" ]] || exit 0

# если правится не контроллер/роут — пропустим
if [[ ! "$file_path" =~ (^|/)src/main/.*/(controller|rest|web|routes?)/.*\.(kt|java)$ ]] && \
   [[ ! "$file_path" =~ (Controller|Resource)\.(kt|java)$ ]]; then
  exit 0
fi

# проверим наличие контракта
has_spec=0
for p in "docs/api/$ticket.yaml" "docs/api/$ticket.yml" "docs/api/$ticket.json" "src/main/resources/openapi.yaml" "openapi.yaml"; do
  [[ -f "$p" ]] && has_spec=1 && break
done

if [[ $has_spec -eq 0 ]]; then
  if [[ -n "$slug_hint" && "$slug_hint" != "$ticket" ]]; then
    echo "BLOCK: нет API контракта для '${ticket}' (slug hint: ${slug_hint}). Добавьте docs/api/${ticket}.yaml (OpenAPI) или отключите проверку в config/gates.json." 1>&2
  else
    echo "BLOCK: нет API контракта для '${ticket}'. Добавьте docs/api/${ticket}.yaml (OpenAPI) или отключите проверку в config/gates.json." 1>&2
  fi
  exit 2
fi
exit 0
