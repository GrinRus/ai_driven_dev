#!/usr/bin/env bash
# Блокирует правки контроллеров/роутов, если нет OpenAPI контракта для активной фичи
set -euo pipefail
payload="$(cat)"

json_get_bool() {
  python3 - <<'PY' "$1" "$2"
import json,sys
path=sys.argv[1]; key=sys.argv[2]
try:
  cfg=json.load(open(path,'r',encoding='utf-8'))
  v=cfg.get(key, False)
  print("1" if v else "0")
except Exception:
  print("0")
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

[[ -f config/gates.json ]] || exit 0
[[ "$(json_get_bool config/gates.json api_contract)" == "1" ]] || exit 0

slug_file="$(python3 - <<'PY'
import json,sys
cfg='config/gates.json'
try:
  import json
  g=json.load(open(cfg,'r',encoding='utf-8'))
  print(g.get('feature_slug_source','docs/.active_feature'))
except Exception:
  print('docs/.active_feature')
PY
)"

[[ -f "$slug_file" ]] || exit 0
slug="$(cat "$slug_file" 2>/dev/null || true)"
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
  echo "BLOCK: нет API контракта для '$slug'. Создайте его командой: /api-spec-new $slug" 1>&2
  exit 2
fi
exit 0
