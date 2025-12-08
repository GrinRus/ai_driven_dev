#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}"
# shellcheck source=.claude/hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"
HOOK_VENDOR_DIR="${SCRIPT_DIR}/_vendor"
if [[ -d "$HOOK_VENDOR_DIR" ]]; then
  if [[ -n "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="$HOOK_VENDOR_DIR:${PYTHONPATH}"
  else
    export PYTHONPATH="$HOOK_VENDOR_DIR"
  fi
fi

cd "$ROOT_DIR"

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"
current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

if [[ "$file_path" =~ (^|/)(agents|commands)/ ]] || [[ "$file_path" =~ (^|/)prompts/en/(agents|commands)/ ]]; then
  # Проверяем паритет RU/EN: RU в aidd/agents|commands, EN в prompts/en/**
  ru_path="$file_path"
  if [[ "$ru_path" =~ ^prompts/en/agents/ ]]; then
    ru_path="agents/${ru_path#prompts/en/agents/}"
  elif [[ "$ru_path" =~ ^prompts/en/commands/ ]]; then
    ru_path="commands/${ru_path#prompts/en/commands/}"
  fi
  en_path="prompts/en/${ru_path}"
  skip_lang_parity="$(python3 - "$ru_path" "$en_path" <<'PY'
from pathlib import Path
import sys

def has_skip(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return False
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            stripped = line.strip()
            if stripped == "---":
                break
            if stripped.lower().startswith("lang-parity:"):
                value = stripped.split(":", 1)[1].strip().lower()
                return value == "skip"
    return "Lang-Parity: skip" in text

ru = Path(sys.argv[1])
en = Path(sys.argv[2])
if has_skip(ru) or has_skip(en):
    print("skip")
PY
)"
  if [[ "$skip_lang_parity" == "skip" ]]; then
    exit 0
  fi
  if [[ ! -f "$ru_path" || ! -f "$en_path" ]]; then
    echo "BLOCK: промпты должны обновляться синхронно (RU/EN). Обновите обе локали или добавьте 'Lang-Parity: skip'." >&2
    exit 2
  fi
  if ! python3 - "$ru_path" "$en_path" <<'PY'
import sys
from pathlib import Path

def version(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    for line in text.splitlines():
        if line.strip().startswith("prompt_version"):
            return line.split(":", 1)[1].strip()
    return ""

ru_path = Path(sys.argv[1])
en_path = Path(sys.argv[2])
ru_v = version(ru_path)
en_v = version(en_path)
if ru_v and en_v and ru_v != en_v:
    print("BLOCK: промпты должны обновляться синхронно (RU/EN). Обновите обе локали или добавьте 'Lang-Parity: skip' в фронт-маттер.")
    raise SystemExit(2)
PY
  then
    exit 2
  fi
  exit 0
fi

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

ensure_template "docs/templates/research-summary.md" "docs/research/$ticket.md"

# Проверим артефакты
[[ -f "docs/prd/$ticket.prd.md" ]] || { echo "BLOCK: нет PRD → запустите /idea-new $ticket"; exit 2; }
analyst_cmd=(python3 -m claude_workflow_cli.tools.analyst_guard --ticket "$ticket")
if [[ -n "$current_branch" ]]; then
  analyst_cmd+=(--branch "$current_branch")
fi
if ! "${analyst_cmd[@]}" >/dev/null; then
  exit 2
fi
prd_review_gate="$(resolve_script_path "scripts/prd_review_gate.py" || true)"
if ! review_msg="$(python3 "${prd_review_gate:-scripts/prd_review_gate.py}" --ticket "$ticket" --file-path "$file_path" --branch "$current_branch" --skip-on-prd-edit)"; then
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
context_path = Path("reports/research") / f"{ticket}-context.json"
targets_path = Path("reports/research") / f"{ticket}-targets.json"
allow_missing = settings.get("allow_missing", False)
baseline_phrase = (settings.get("baseline_phrase") or "контекст пуст").strip().lower()
allow_pending_baseline = bool(settings.get("allow_pending_baseline", False))
if not doc_path.exists():
    if allow_missing:
        raise SystemExit(0)
    print(f"BLOCK: нет отчёта Researcher для {ticket} → запустите `claude-workflow research --ticket {ticket}` и оформите docs/research/{ticket}.md")
    raise SystemExit(1)

status = None
try:
    doc_text = doc_path.read_text(encoding="utf-8")
except Exception:
    print(f"BLOCK: не удалось прочитать docs/research/{ticket}.md.")
    raise SystemExit(1)
for line in doc_text.splitlines():
    stripped = line.strip()
    if stripped.lower().startswith("status:"):
        status = stripped.split(":", 1)[1].strip().lower()
        break

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
        if status == "pending" and allow_pending_baseline:
            print("ALLOW_PENDING_BASELINE")
            raise SystemExit(0)
        else:
            print(f"BLOCK: статус Researcher `{status}` не входит в {required_statuses} → актуализируйте отчёт.")
            raise SystemExit(1)

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
if [[ "$research_msg" == "ALLOW_PENDING_BASELINE" ]]; then
  exit 0
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
allowed_values = set(required_values + optional_values)

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
if allowed_values and value not in allowed_values:
    label = value or "empty"
    print(f"WARN: некорректный статус reviewer marker ({label}). Используйте required|optional|skipped.")
elif value in required_values:
    print(f"WARN: reviewer запросил тесты ({marker_path}). Запустите format-and-test или обновите маркер после прогонов.")
PY
)" || reviewer_notice=""
  if [[ -n "$reviewer_notice" ]]; then
    echo "$reviewer_notice" 1>&2
  fi
fi

if [[ -n "$ticket" ]]; then
  handoff_block="$(python3 - "$ticket" "$slug_hint" <<'PY'
import sys
from pathlib import Path

ticket = sys.argv[1]
slug_hint = sys.argv[2] if len(sys.argv) > 2 else ""
tasklist_path = Path("docs/tasklist") / f"{ticket}.md"
if not tasklist_path.exists():
    raise SystemExit(0)
reports = [
    ("qa", Path("reports/qa") / f"{ticket}.json", "reports/qa/"),
    ("review", Path("reports/review") / f"{ticket}.json", "reports/review/"),
    ("research", Path("reports/research") / f"{ticket}-context.json", "reports/research/"),
]
try:
    lines = tasklist_path.read_text(encoding="utf-8").splitlines()
except Exception:
    raise SystemExit(0)
text = "\n".join(lines).lower()
missing = []
for name, report_path, marker in reports:
    if not report_path.exists():
        continue
    if marker not in text:
        missing.append((name, report_path))
if missing:
    items = ", ".join(f"{name}: {path}" for name, path in missing)
    print(f"BLOCK: handoff-задачи не добавлены в tasklist ({items}). Запустите `claude-workflow tasks-derive --source <qa|review|research> --append --ticket {ticket}`.")
    raise SystemExit(1)
PY
)"
  if [[ -n "$handoff_block" ]]; then
    echo "$handoff_block"
    exit 2
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
