#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${CLAUDE_PROJECT_DIR:-${CLAUDE_PLUGIN_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}}"
if [[ "$(basename "$ROOT_DIR")" != "aidd" && ( -d "$ROOT_DIR/aidd/docs" || -d "$ROOT_DIR/aidd/hooks" ) ]]; then
  echo "WARN: detected workspace root; using ${ROOT_DIR}/aidd as project root" >&2
  ROOT_DIR="$ROOT_DIR/aidd"
fi
if [[ ! -d "$ROOT_DIR/docs" ]]; then
  echo "BLOCK: aidd/docs not found at $ROOT_DIR/docs. Run 'claude-workflow init --target <workspace>' to install payload into ./aidd." >&2
  exit 2
fi
export ROOT_DIR
# shellcheck source=hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"
HOOK_VENDOR_DIR="${SCRIPT_DIR}/_vendor"
if [[ -d "$HOOK_VENDOR_DIR" ]]; then
  if [[ -n "${PYTHONPATH:-}" ]]; then
    export PYTHONPATH="$HOOK_VENDOR_DIR:${PYTHONPATH}"
  else
    export PYTHONPATH="$HOOK_VENDOR_DIR"
  fi
fi

EVENT_TYPE="gate-workflow"
EVENT_STATUS=""
EVENT_SHOULD_LOG=0
EVENT_SOURCE="hook gate-workflow"
trap 'if [[ "${EVENT_SHOULD_LOG:-0}" == "1" ]]; then hook_append_event "$ROOT_DIR" "$EVENT_TYPE" "$EVENT_STATUS" "" "" "$EVENT_SOURCE"; fi' EXIT

cd "$ROOT_DIR"

collect_changed_files() {
  local files=()
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    while IFS= read -r path; do
      [[ -n "$path" ]] && files+=("$path")
    done < <(git diff --name-only HEAD)
  fi
  while IFS= read -r path; do
    [[ -n "$path" ]] && files+=("$path")
  done < <(git ls-files --others --exclude-standard)
  if ((${#files[@]} == 0)); then
    return 0
  fi
  printf '%s\n' "${files[@]}" | awk '!seen[$0]++'
}

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"
current_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"

changed_files=()
if [[ -n "$file_path" ]]; then
  changed_files+=("$file_path")
fi
while IFS= read -r path; do
  [[ -n "$path" ]] && changed_files+=("$path")
done < <(collect_changed_files || true)

if ((${#changed_files[@]} > 0)); then
  deduped=()
  while IFS= read -r path; do
    [[ -n "$path" ]] && deduped+=("$path")
  done < <(printf '%s\n' "${changed_files[@]}" | awk '!seen[$0]++')
  changed_files=("${deduped[@]}")
fi


if [[ -z "$file_path" && ${#changed_files[@]} -gt 0 ]]; then
  for candidate in "${changed_files[@]}"; do
    if [[ "$candidate" =~ (^|/)src/ ]]; then
      file_path="$candidate"
      break
    fi
  done
  if [[ -z "$file_path" ]]; then
    file_path="${changed_files[0]}"
  fi
fi

has_src_changes=0
for candidate in "${changed_files[@]}"; do
  if [[ "$candidate" =~ (^|/)src/ ]]; then
    has_src_changes=1
    break
  fi
done

if [[ "${CLAUDE_SKIP_STAGE_CHECKS:-0}" != "1" ]]; then
  active_stage="$(hook_resolve_stage "docs/.active_stage" || true)"
  if [[ -n "$active_stage" ]]; then
    case "$active_stage" in
      implement|review|qa)
        : ;;
      *)
        if [[ "$has_src_changes" -eq 1 ]]; then
          echo "BLOCK: активная стадия '$active_stage' не разрешает правки кода. Переключитесь на /implement (или установите стадию вручную)." >&2
          exit 2
        fi
        exit 0
        ;;
    esac
  fi
fi

ticket_source="$(hook_config_get_str config/gates.json feature_ticket_source docs/.active_ticket)"
slug_hint_source="$(hook_config_get_str config/gates.json feature_slug_hint_source docs/.active_feature)"
if [[ -z "$ticket_source" && -z "$slug_hint_source" ]]; then
  exit 0
fi
if [[ -n "$ticket_source" && "$ticket_source" == aidd/* && ! -f "$ticket_source" && -f "${ticket_source#aidd/}" ]]; then
  ticket_source="${ticket_source#aidd/}"
fi
if [[ -n "$slug_hint_source" && "$slug_hint_source" == aidd/* && ! -f "$slug_hint_source" && -f "${slug_hint_source#aidd/}" ]]; then
  slug_hint_source="${slug_hint_source#aidd/}"
fi
if [[ -n "$ticket_source" && ! -f "$ticket_source" ]] && [[ -n "$slug_hint_source" && ! -f "$slug_hint_source" ]]; then
  exit 0  # нет активной фичи — не блокируем
fi
ticket="$(hook_read_ticket "$ticket_source" "$slug_hint_source" || true)"
slug_hint="$(hook_read_slug "$slug_hint_source" || true)"
[[ -n "$ticket" ]] || exit 0

# Если правится не код, пропускаем
if [[ "$has_src_changes" -ne 1 ]]; then
  exit 0
fi

EVENT_SHOULD_LOG=1
EVENT_STATUS="fail"

ensure_template "docs/research/template.md" "docs/research/$ticket.md"
ensure_template "docs/prd/template.md" "docs/prd/$ticket.prd.md"
plan_path="docs/plan/$ticket.md"
if [[ ! -f "$plan_path" ]]; then
  ensure_template "docs/plan/template.md" "$plan_path"
  echo "BLOCK: нет плана → запустите /plan-new $ticket"
  exit 2
fi
tasklist_path="docs/tasklist/$ticket.md"
if [[ ! -f "$tasklist_path" ]]; then
  ensure_template "docs/tasklist/template.md" "$tasklist_path"
  echo "BLOCK: нет задач → запустите /tasks-new $ticket (docs/tasklist/$ticket.md)"
  exit 2
fi

# Проверим артефакты
[[ -f "docs/prd/$ticket.prd.md" ]] || { echo "BLOCK: нет PRD → запустите /idea-new $ticket"; exit 2; }
analyst_cmd=(claude-workflow analyst-check --target "$ROOT_DIR" --ticket "$ticket")
if [[ -n "$current_branch" ]]; then
  analyst_cmd+=(--branch "$current_branch")
fi
if ! analyst_output="$("${analyst_cmd[@]}" 2>&1)"; then
  if [[ -n "$analyst_output" ]]; then
    echo "$analyst_output" >&2
  fi
  exit 2
fi
if [[ -f "docs/plan/$ticket.md" ]]; then
  if ! review_msg="$(claude-workflow plan-review-gate --target "$ROOT_DIR" --ticket "$ticket" --file-path "$file_path" --branch "$current_branch" --skip-on-plan-edit)"; then
    if [[ -n "$review_msg" ]]; then
      echo "$review_msg"
    else
      echo "BLOCK: Plan Review не готов → выполните /review-spec $ticket"
    fi
    exit 2
  fi
fi
if [[ -f "docs/plan/$ticket.md" ]]; then
  if ! review_msg="$(claude-workflow prd-review-gate --target "$ROOT_DIR" --ticket "$ticket" --slug-hint "$slug_hint" --file-path "$file_path" --branch "$current_branch" --skip-on-prd-edit)"; then
    if [[ -n "$review_msg" ]]; then
      echo "$review_msg"
    else
      echo "BLOCK: PRD Review не готов → выполните /review-spec $ticket"
    fi
    exit 2
  fi
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
doc_text_lower = doc_text.lower()
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
            baseline_ok = bool(baseline_phrase and baseline_phrase in doc_text_lower)
            if baseline_ok:
                try:
                    context = json.loads(context_path.read_text(encoding="utf-8"))
                except FileNotFoundError:
                    print(f"BLOCK: отсутствует {context_path}; выполните claude-workflow research для {ticket}.")
                    raise SystemExit(1)
                except json.JSONDecodeError:
                    print(f"BLOCK: повреждён {context_path}; пересоздайте его.")
                    raise SystemExit(1)
                profile = context.get("profile") or {}
                is_new_project = bool(profile.get("is_new_project"))
                auto_mode = bool(context.get("auto_mode"))
                if is_new_project and auto_mode:
                    print("ALLOW_PENDING_BASELINE")
                    raise SystemExit(0)
            print(
                "BLOCK: статус Researcher `pending` допустим только для baseline (требуется отметка и auto_mode для нового проекта)."
            )
            raise SystemExit(1)
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
  EVENT_STATUS="pass"
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
    or "aidd/reports/reviewer/{ticket}.json"
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
if not marker_path.is_absolute() and marker_path.parts and marker_path.parts[0] == "aidd" and Path.cwd().name == "aidd":
    marker_path = Path(*marker_path.parts[1:])
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
import json
import sys
from pathlib import Path

ticket = sys.argv[1]
slug_hint = sys.argv[2] if len(sys.argv) > 2 else ""
tasklist_path = Path("docs/tasklist") / f"{ticket}.md"
prefix = "aidd/" if Path.cwd().name == "aidd" else ""
if not tasklist_path.exists():
    raise SystemExit(0)

def resolve_report(path: Path) -> Path | None:
    if path.exists():
        return path
    if path.suffix == ".json":
        for suffix in (".pack.yaml", ".pack.toon"):
            candidate = path.with_suffix(suffix)
            if candidate.exists():
                return candidate
    return None

def read_tasklist_section(lines: list[str]) -> str:
    start = None
    end = len(lines)
    for idx, line in enumerate(lines):
        if line.strip().lower().startswith("## aidd:handoff_inbox"):
            start = idx
            break
    if start is not None:
        for idx in range(start + 1, len(lines)):
            if lines[idx].strip().startswith("##"):
                end = idx
                break
        return "\n".join(lines[start:end]).lower()
    return "\n".join(lines).lower()

reports = []
qa_path = resolve_report(Path("reports/qa") / f"{ticket}.json")
if qa_path:
    reports.append(("qa", qa_path, f"{prefix}{qa_path.as_posix()}"))
research_path = resolve_report(Path("reports/research") / f"{ticket}-context.json")
if research_path:
    reports.append(("research", research_path, f"{prefix}{research_path.as_posix()}"))

review_path = None
try:
    config = json.loads(Path("config/gates.json").read_text(encoding="utf-8"))
except Exception:
    config = {}
reviewer_cfg = config.get("reviewer") or {}
review_template = (
    reviewer_cfg.get("marker")
    or reviewer_cfg.get("tests_marker")
    or "aidd/reports/reviewer/{ticket}.json"
)
slug_value = slug_hint.strip() or ticket
raw_path = str(review_template).replace("{ticket}", ticket).replace("{slug}", slug_value)
review_path = Path(raw_path)
if not review_path.is_absolute() and review_path.parts and review_path.parts[0] == "aidd" and Path.cwd().name == "aidd":
    review_path = Path(*review_path.parts[1:])
if review_path.exists():
    has_review_report = False
    try:
        review_payload = json.loads(review_path.read_text(encoding="utf-8"))
    except Exception:
        review_payload = {}
        has_review_report = True
    if isinstance(review_payload, dict):
        kind = str(review_payload.get("kind") or "").strip().lower()
        stage = str(review_payload.get("stage") or "").strip().lower()
        if kind == "review" or stage == "review":
            has_review_report = True
        elif "findings" in review_payload:
            has_review_report = True
    else:
        has_review_report = True
    if has_review_report:
        reports.append(("review", review_path, f"{prefix}{review_path.as_posix()}"))
try:
    lines = tasklist_path.read_text(encoding="utf-8").splitlines()
except Exception:
    raise SystemExit(0)
text = read_tasklist_section(lines)
missing = []
for name, report_path, marker in reports:
    marker_lower = marker.lower()
    alt_marker = marker_lower.replace("aidd/", "")
    if marker_lower not in text and alt_marker not in text:
        missing.append((name, marker))
if missing:
    items = ", ".join(f"{name}: {marker}" for name, marker in missing)
    print(
        f"BLOCK: handoff-задачи не добавлены в tasklist ({items}). "
        f"Запустите `claude-workflow tasks-derive --source <qa|research|review> --append --ticket {ticket}`."
    )
    raise SystemExit(1)
PY
)"
  if [[ -n "$handoff_block" ]]; then
    echo "$handoff_block"
    exit 2
  fi
fi

progress_args=("--target" "$ROOT_DIR" "--ticket" "$ticket" "--source" "gate")
if [[ -n "$slug_hint" ]]; then
  progress_args+=("--slug-hint" "$slug_hint")
fi
if [[ -n "$current_branch" ]]; then
  progress_args+=("--branch" "$current_branch")
fi
set +e
progress_output="$(claude-workflow progress "${progress_args[@]}" 2>&1)"
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

EVENT_STATUS="pass"
exit 0
