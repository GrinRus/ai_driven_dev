#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=.claude/hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"
current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

slug_file="docs/.active_feature"
[[ -f "$slug_file" ]] || exit 0  # нет активной фичи — не блокируем
slug="$(hook_read_slug "$slug_file" || true)"
[[ -n "$slug" ]] || exit 0

# Если правится не код, пропускаем
if [[ ! "$file_path" =~ (^|/)src/ ]]; then
  exit 0
fi

# Проверим артефакты
[[ -f "docs/prd/$slug.prd.md" ]] || { echo "BLOCK: нет PRD → запустите /idea-new $slug"; exit 2; }
if ! review_msg="$(python3 "$ROOT_DIR/scripts/prd_review_gate.py" --slug "$slug" --file-path "$file_path" --branch "$current_branch" --skip-on-prd-edit)"; then
  if [[ -n "$review_msg" ]]; then
    echo "$review_msg"
  else
    echo "BLOCK: PRD Review не готов → выполните /review-prd $slug"
  fi
  exit 2
fi
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
