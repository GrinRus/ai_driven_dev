#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
# shellcheck source=.claude/hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"
current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

ticket_source="$(hook_config_get_str config/gates.json feature_ticket_source docs/.active_ticket)"
slug_hint_source="$(hook_config_get_str config/gates.json feature_slug_hint_source docs/.active_feature)"
if [[ -z "$ticket_source" && -z "$slug_hint_source" ]]; then
  exit 0
fi
if [[ -n "$ticket_source" && ! -f "$ticket_source" ]] && [[ -n "$slug_hint_source" && ! -f "$slug_hint_source" ]]; then
  exit 0  # нет активной фичи — не блокируем
fi
ticket="$(hook_read_ticket "$ticket_source" "$slug_hint_source" || true)"
slug_hint="$(hook_read_slug "$slug_hint_source" || true)"
[[ -n "$ticket" ]] || exit 0

# Если правится не код, пропускаем
if [[ ! "$file_path" =~ (^|/)src/ ]]; then
  exit 0
fi

# Проверим артефакты
[[ -f "docs/prd/$ticket.prd.md" ]] || { echo "BLOCK: нет PRD → запустите /idea-new $ticket"; exit 2; }
analyst_cmd=(python3 -m claude_workflow_cli.tools.analyst_guard --ticket "$ticket")
if [[ -n "$current_branch" ]]; then
  analyst_cmd+=(--branch "$current_branch")
fi
if ! "${analyst_cmd[@]}" >/dev/null; then
  exit 2
fi
if ! review_msg="$(python3 "$ROOT_DIR/scripts/prd_review_gate.py" --ticket "$ticket" --file-path "$file_path" --branch "$current_branch" --skip-on-prd-edit)"; then
  if [[ -n "$review_msg" ]]; then
    echo "$review_msg"
  else
    echo "BLOCK: PRD Review не готов → выполните /review-prd $ticket"
  fi
  exit 2
fi

if ! research_msg="$(python3 - "$ticket" "$current_branch" <<'PY'
import datetime as dt
import json
import sys
from pathlib import Path
from fnmatch import fnmatch

ticket = sys.argv[1]
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

doc_path = Path("docs/research") / f"{ticket}.md"
allow_missing = settings.get("allow_missing", False)
if not doc_path.exists():
    if allow_missing:
        raise SystemExit(0)
    print(f"BLOCK: нет отчёта Researcher для {ticket} → запустите `claude-workflow research --ticket {ticket}` и оформите docs/research/{ticket}.md")
    raise SystemExit(1)

status = None
try:
    for line in doc_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("status:"):
            status = stripped.split(":", 1)[1].strip().lower()
            break
except Exception:
    print(f"BLOCK: не удалось прочитать docs/research/{ticket}.md.")
    raise SystemExit(1)

required_statuses = [
    (item or "").strip().lower()
    for item in settings.get("require_status", ["reviewed"])
    if isinstance(item, str)
]
if required_statuses:
    if not status:
        print(f"BLOCK: docs/research/{ticket}.md не содержит строки `Status:` или она пуста.")
        raise SystemExit(1)
    if status not in required_statuses:
        print(f"BLOCK: статус Researcher `{status}` не входит в {required_statuses} → актуализируйте отчёт.")
        raise SystemExit(1)

targets_path = Path("reports/research") / f"{ticket}-targets.json"
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
    context_path = Path("reports/research") / f"{ticket}-context.json"
    try:
        context = json.loads(context_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"BLOCK: отсутствует {context_path}; выполните claude-workflow research для {ticket}.")
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
        print(f"BLOCK: контекст Researcher устарел ({age_days} дней) → обновите claude-workflow research для {ticket}.")
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

[[ -f "docs/plan/$ticket.md"    ]] || { echo "BLOCK: нет плана → запустите /plan-new $ticket"; exit 2; }
if ! python3 - "$ticket" <<'PY'
import sys
from pathlib import Path

ticket = sys.argv[1]
tasklist = Path("docs") / "tasklist" / f"{ticket}.md"
if not tasklist.exists():
    sys.exit(1)
for raw in tasklist.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line.startswith("- [ ]"):
        continue
    lower_line = line.lower()
    if "<slug>" in lower_line or "<ticket>" in lower_line:
        continue
    sys.exit(0)
sys.exit(1)
PY
then
  echo "BLOCK: нет задач → запустите /tasks-new $ticket (docs/tasklist/$ticket.md)"
  exit 2
fi

if [[ -n "$ticket" ]]; then
  reviewer_notice="$(python3 - "$ticket" "$slug_hint" <<'PY'
import json
import sys
from pathlib import Path

ticket = sys.argv[1]
slug_hint = sys.argv[2] if len(sys.argv) > 2 else ""
config_path = Path("config/gates.json")
try:
    config = json.loads(config_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

reviewer_cfg = config.get("reviewer") or {}
if not reviewer_cfg or not reviewer_cfg.get("enabled", True):
    raise SystemExit(0)

template = str(
    reviewer_cfg.get("tests_marker")
    or reviewer_cfg.get("marker")
    or "reports/reviewer/{ticket}.json"
)
field = str(reviewer_cfg.get("tests_field") or reviewer_cfg.get("field") or "tests")
required_values_source = reviewer_cfg.get("requiredValues", reviewer_cfg.get("required_values", ["required"]))
required_values = [
    str(value).strip().lower()
    for value in (required_values_source if isinstance(required_values_source, list) else ["required"])
]
optional_values = reviewer_cfg.get("optionalValues", reviewer_cfg.get("optional_values", []))
if isinstance(optional_values, list):
    optional_values = [str(value).strip().lower() for value in optional_values]
else:
    optional_values = []

slug_value = slug_hint.strip() or ticket
marker_path = Path(template.replace("{ticket}", ticket).replace("{slug}", slug_value))
if not marker_path.exists():
    if reviewer_cfg.get("warn_on_missing", True):
        print(
            f"WARN: reviewer маркер не найден ({marker_path}). Используйте `claude-workflow reviewer-tests --status required` при необходимости."
        )
    raise SystemExit(0)

try:
    data = json.loads(marker_path.read_text(encoding="utf-8"))
except Exception:
    print(
        f"WARN: повреждён маркер reviewer ({marker_path}). Пересоздайте его командой `claude-workflow reviewer-tests --status required`."
    )
    raise SystemExit(0)

value = str(data.get(field, "")).strip().lower()
if value in required_values:
    print(
        f"WARN: reviewer запросил тесты ({marker_path}). Запустите format-and-test или обновите маркер после прогонов."
    )
PY
)"
  if [[ -n "$reviewer_notice" ]]; then
    echo "$reviewer_notice" 1>&2
  fi
fi

progress_args=("--root" "$PWD" "--ticket" "$ticket" "--source" "gate" "--quiet-ok")
if [[ -n "$slug_hint" ]]; then
  progress_args+=("--slug-hint" "$slug_hint")
fi
if [[ -n "$current_branch" ]]; then
  progress_args+=("--branch" "$current_branch")
fi
set +e
progress_output="$(python3 -m claude_workflow_cli.progress "${progress_args[@]}" 2>&1)"
progress_status=$?
set -e
if [[ "$progress_status" -ne 0 ]]; then
  if [[ -n "$progress_output" ]]; then
    echo "$progress_output"
  else
    echo "BLOCK: tasklist не обновлён — отметьте завершённые чекбоксы перед продолжением."
  fi
  exit 2
fi
if [[ -n "$progress_output" ]]; then
  echo "$progress_output"
fi

exit 0
