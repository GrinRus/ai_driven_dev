#!/usr/bin/env bash
# Требует наличие теста для редактируемого исходника (soft/hard режим)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${CLAUDE_PLUGIN_ROOT:-${CLAUDE_PROJECT_DIR:-$(cd "${SCRIPT_DIR}/../.." && pwd)}}"
if [[ "$(basename "$ROOT_DIR")" != "aidd" && -d "$ROOT_DIR/aidd/.claude" ]]; then
  echo "WARN: detected workspace root; using ${ROOT_DIR}/aidd as project root" >&2
  ROOT_DIR="$ROOT_DIR/aidd"
fi
if [[ ! -d "$ROOT_DIR/docs" ]]; then
  echo "BLOCK: aidd/docs not found at $ROOT_DIR/docs. Run init with '--target <workspace>' to install payload." >&2
  exit 2
fi
# shellcheck source=.claude/hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

cd "$ROOT_DIR"

payload="$(cat)"
file_path="$(hook_payload_file_path "$payload")"
ticket_source="$(hook_config_get_str config/gates.json feature_ticket_source docs/.active_ticket)"
slug_hint_source="$(hook_config_get_str config/gates.json feature_slug_hint_source docs/.active_feature)"
ticket="$(hook_read_ticket "$ticket_source" "$slug_hint_source" || true)"
slug_hint="$(hook_read_slug "$slug_hint_source" || true)"

if [[ -n "$ticket" ]]; then
  reviewer_tests_msg="$(python3 - "$ticket" "$slug_hint" <<'PY'
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

slug_value = slug_hint.strip() or ticket
marker_path = Path(template.replace("{ticket}", ticket).replace("{slug}", slug_value))
if not marker_path.exists():
    raise SystemExit(0)

try:
    data = json.loads(marker_path.read_text(encoding="utf-8"))
except Exception:
    print(
        f"WARN: reviewer маркер повреждён ({marker_path}). Пересоздайте его командой `claude-workflow reviewer-tests --status required`."
    )
    raise SystemExit(0)

value = str(data.get(field, "")).strip().lower()
if value in required_values:
    label = ticket if not slug_hint or slug_hint == ticket else f"{ticket} (slug hint: {slug_hint})"
    print(
        f"WARN: reviewer запросил обязательный запуск тестов для {label} ({marker_path}). Не забудьте подтвердить выполнение перед merge."
    )
PY
)"
  if [[ -n "$reviewer_tests_msg" ]]; then
    echo "$reviewer_tests_msg" 1>&2
  fi
fi

mode="$(hook_config_get_str config/gates.json tests_required disabled)"
mode="$(printf '%s' "$mode" | tr '[:upper:]' '[:lower:]')"
[[ "$mode" == "disabled" ]] && exit 0

# интересует только src/main и *.kt|*.java
if [[ ! "$file_path" =~ (^|/)src/main/ ]] || [[ ! "$file_path" =~ \.(kt|java)$ ]]; then
  exit 0
fi

# выведем ожидаемые имена тестов (Kotlin/Java)
rel="${file_path#*src/main/}"
test1="src/test/${rel%.*}Test.${file_path##*.}"
test2="src/test/${rel%.*}Tests.${file_path##*.}"
has_tests=0
if [[ -f "$test1" || -f "$test2" ]]; then
  has_tests=1
fi

emit_research_hint() {
  [[ -z "$ticket" ]] && return 0
  local message
  message="$(python3 - "$file_path" "$ticket" "$slug_hint" <<'PY'
import json
import sys
from pathlib import Path

file_path = Path(sys.argv[1]).as_posix()
ticket = sys.argv[2]
slug_hint = sys.argv[3] if len(sys.argv) > 3 else ""
config_path = Path("config/gates.json")
try:
    config = json.loads(config_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

research = config.get("researcher") or {}
if not research.get("enabled", True):
    raise SystemExit(0)

targets_path = Path("reports/research") / f"{ticket}-targets.json"
try:
    targets = json.loads(targets_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(0)

paths = targets.get("paths") or []
cwd = Path.cwd()
for candidate in paths:
    raw = Path(candidate)
    if raw.is_absolute():
        try:
            candidate_rel = raw.relative_to(cwd).as_posix()
        except ValueError:
            continue
    else:
        candidate_rel = raw.as_posix().lstrip("./")
    if not candidate_rel:
        continue
    normalized = candidate_rel.rstrip("/")
    if file_path.startswith(normalized + "/") or file_path == normalized:
        raise SystemExit(0)

label = ticket if not slug_hint or slug_hint == ticket else f"{ticket} (slug hint: {slug_hint})"
print(f"WARN: {file_path} не входит в список Researcher targets → обновите claude-workflow research для {label} или настройте paths.")
PY
)"
  if [[ -n "$message" ]]; then
    echo "$message" 1>&2
  fi
}

if [[ "$has_tests" -eq 1 ]]; then
  emit_research_hint
  exit 0
fi

if [[ "$mode" == "soft" ]]; then
  echo "WARN: отсутствует тест для ${file_path}. Рекомендуется создать ${test1}." 1>&2
  emit_research_hint
  exit 0
fi

echo "BLOCK: нет теста для ${file_path}. Создайте ${test1} (или ${test2}) либо переведите tests_required в config/gates.json в soft/disabled." 1>&2
emit_research_hint
exit 2
