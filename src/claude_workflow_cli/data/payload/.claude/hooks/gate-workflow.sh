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
analyst_cmd=(python3 -m claude_workflow_cli.tools.analyst_guard --slug "$slug")
if [[ -n "$current_branch" ]]; then
  analyst_cmd+=(--branch "$current_branch")
fi
if ! "${analyst_cmd[@]}" >/dev/null; then
  exit 2
fi
if ! review_msg="$(python3 "$ROOT_DIR/scripts/prd_review_gate.py" --slug "$slug" --file-path "$file_path" --branch "$current_branch" --skip-on-prd-edit)"; then
  if [[ -n "$review_msg" ]]; then
    echo "$review_msg"
  else
    echo "BLOCK: PRD Review не готов → выполните /review-prd $slug"
  fi
  exit 2
fi

if ! research_msg="$(python3 - "$slug" "$current_branch" <<'PY'
import datetime as dt
import json
import sys
from pathlib import Path
from fnmatch import fnmatch

slug = sys.argv[1]
branch = sys.argv[2] if len(sys.argv) > 2 else ""
config_path = Path("config/gates.json")
if not config_path.exists():
    raise SystemExit(0)
try:
    config = json.loads(config_path.read_text(encoding="utf-8"))
except Exception:
    print("WARN: не удалось прочитать config/gates.json; пропускаем проверку Researcher.")
    raise SystemExit(0)

settings = config.get("researcher") or {}
if not settings or not settings.get("enabled", True):
    raise SystemExit(0)

branches = settings.get("branches")
if branch and isinstance(branches, list) and branches:
    if not any(fnmatch(branch, pattern) for pattern in branches if isinstance(pattern, str)):
        raise SystemExit(0)

skip_branches = settings.get("skip_branches")
if branch and isinstance(skip_branches, list):
    if any(fnmatch(branch, pattern) for pattern in skip_branches if isinstance(pattern, str)):
        raise SystemExit(0)

doc_path = Path("docs/research") / f"{slug}.md"
allow_missing = settings.get("allow_missing", False)
if not doc_path.exists():
    if allow_missing:
        raise SystemExit(0)
    print(f"BLOCK: нет отчёта Researcher для {slug} → запустите `claude-workflow research --feature {slug}` и оформите docs/research/{slug}.md")
    raise SystemExit(1)

status = None
try:
    for line in doc_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("status:"):
            status = stripped.split(":", 1)[1].strip().lower()
            break
except Exception:
    print(f"BLOCK: не удалось прочитать docs/research/{slug}.md.")
    raise SystemExit(1)

required_statuses = [
    (item or "").strip().lower()
    for item in settings.get("require_status", ["reviewed"])
    if isinstance(item, str)
]
if required_statuses:
    if not status:
        print(f"BLOCK: docs/research/{slug}.md не содержит строки `Status:` или она пуста.")
        raise SystemExit(1)
    if status not in required_statuses:
        print(f"BLOCK: статус Researcher `{status}` не входит в {required_statuses} → актуализируйте отчёт.")
        raise SystemExit(1)

targets_path = Path("reports/research") / f"{slug}-targets.json"
min_paths = int(settings.get("minimum_paths", 0) or 0)
if min_paths > 0:
    try:
        targets = json.loads(targets_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"BLOCK: отсутствует {targets_path} с целевыми директориями Researcher.")
        raise SystemExit(1)
    except json.JSONDecodeError:
        print(f"BLOCK: повреждён файл {targets_path}; пересоберите его командой claude-workflow research.")
        raise SystemExit(1)
    paths = targets.get("paths") or []
    if len(paths) < min_paths:
        print(f"BLOCK: Researcher targets содержат только {len(paths)} директорий (минимум {min_paths}).")
        raise SystemExit(1)

freshness_days = settings.get("freshness_days")
if freshness_days:
    context_path = Path("reports/research") / f"{slug}-context.json"
    try:
        context = json.loads(context_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"BLOCK: отсутствует {context_path}; выполните claude-workflow research для {slug}.")
        raise SystemExit(1)
    except json.JSONDecodeError:
        print(f"BLOCK: повреждён {context_path}; пересоздайте его.")
        raise SystemExit(1)
    generated_raw = context.get("generated_at")
    if not isinstance(generated_raw, str) or not generated_raw:
        print(f"BLOCK: контекст Researcher ({context_path}) не содержит поля generated_at.")
        raise SystemExit(1)
    try:
        if generated_raw.endswith("Z"):
            generated_dt = dt.datetime.fromisoformat(generated_raw.replace("Z", "+00:00"))
        else:
            generated_dt = dt.datetime.fromisoformat(generated_raw)
    except ValueError:
        print(f"BLOCK: некорректная метка времени generated_at в {context_path}.")
        raise SystemExit(1)
    now = dt.datetime.now(dt.timezone.utc)
    age_days = (now - generated_dt.astimezone(dt.timezone.utc)).days
    if age_days > int(freshness_days):
        print(f"BLOCK: контекст Researcher устарел ({age_days} дней) → обновите claude-workflow research для {slug}.")
        raise SystemExit(1)

raise SystemExit(0)
PY
)"; then
  if [[ -n "$research_msg" ]]; then
    echo "$research_msg"
  else
    echo "BLOCK: проверка Researcher не прошла."
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
