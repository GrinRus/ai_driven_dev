#!/usr/bin/env bash
set -euo pipefail
payload="$(cat)"

# Путь редактируемого файла
file_path="$(
  PAYLOAD="$payload" python3 - <<'PY'
import json
import os
import sys

payload = os.environ.get("PAYLOAD") or ""
try:
    data = json.loads(payload)
except json.JSONDecodeError:
    print("")
    sys.exit(0)

print(data.get("tool_input", {}).get("file_path", ""))
PY
)"

slug_file="docs/.active_feature"
[[ -f "$slug_file" ]] || exit 0  # нет активной фичи — не блокируем
slug="$(cat "$slug_file" 2>/dev/null || true)"
[[ -n "$slug" ]] || exit 0

# Если правится не код, пропускаем
if [[ ! "$file_path" =~ (^|/)src/ ]]; then
  exit 0
fi

# Проверим артефакты
[[ -f "docs/prd/$slug.prd.md" ]] || { echo "BLOCK: нет PRD → запустите /idea-new $slug"; exit 2; }
[[ -f "docs/plan/$slug.md"    ]] || { echo "BLOCK: нет плана → запустите /plan-new $slug"; exit 2; }
if ! python3 - "$slug" <<'PY'
import sys, pathlib
slug = sys.argv[1]
tasklist = pathlib.Path("tasklist.md")
if not tasklist.exists():
    sys.exit(1)
slug_tokens = {slug, slug.replace("-", " "), slug.replace("-", "_")}
for raw in tasklist.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line.startswith("- [ ]"):
        continue
    if "<slug>" in line:
        continue
    if any(token and token in line for token in slug_tokens) or "::" in line:
        sys.exit(0)
sys.exit(1)
PY
then
  echo "BLOCK: нет задач → запустите /tasks-new $slug"
  exit 2
fi

exit 0
