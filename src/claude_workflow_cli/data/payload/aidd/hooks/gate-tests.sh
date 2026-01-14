#!/usr/bin/env bash
# Требует наличие теста для редактируемого исходника (soft/hard режим)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${CLAUDE_PROJECT_DIR:-${CLAUDE_PLUGIN_ROOT:-$(cd "${SCRIPT_DIR}/../.." && pwd)}}"
if [[ "$(basename "$ROOT_DIR")" != "aidd" && ( -d "$ROOT_DIR/aidd/docs" || -d "$ROOT_DIR/aidd/hooks" ) ]]; then
  echo "[gate-tests] WARN: detected workspace root; using ${ROOT_DIR}/aidd as project root"
  ROOT_DIR="$ROOT_DIR/aidd"
fi
if [[ ! -d "$ROOT_DIR/docs" ]]; then
  echo "BLOCK: aidd/docs not found at $ROOT_DIR/docs. Run init with '--target <workspace>' to install payload." >&2
  exit 2
fi
# shellcheck source=hooks/lib.sh
source "${SCRIPT_DIR}/lib.sh"

EVENT_TYPE="gate-tests"
EVENT_STATUS=""
EVENT_SHOULD_LOG=0
EVENT_SOURCE="hook gate-tests"
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
  done < <(git ls-files --others --exclude-standard 2>/dev/null || true)
  if ((${#files[@]} == 0)); then
    return 0
  fi
  printf '%s\n' "${files[@]}" | awk '!seen[$0]++'
}

if [[ "${CLAUDE_SKIP_STAGE_CHECKS:-0}" != "1" ]]; then
  active_stage="$(hook_resolve_stage "docs/.active_stage" || true)"
  if [[ "$active_stage" != "implement" ]]; then
    exit 0
  fi
fi

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
    or "aidd/reports/reviewer/{ticket}.json"
)
field = str(reviewer_cfg.get("tests_field") or reviewer_cfg.get("field") or "tests")
required_values_source = reviewer_cfg.get("requiredValues", reviewer_cfg.get("required_values", ["required"]))
required_values = [
    str(value).strip().lower()
    for value in (required_values_source if isinstance(required_values_source, list) else ["required"])
]

slug_value = slug_hint.strip() or ticket
marker_path = Path(template.replace("{ticket}", ticket).replace("{slug}", slug_value))
if not marker_path.is_absolute() and marker_path.parts and marker_path.parts[0] == "aidd" and Path.cwd().name == "aidd":
    marker_path = Path(*marker_path.parts[1:])
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

CONFIG_PATH="config/gates.json"
TESTS_CFG=()
while IFS= read -r line; do
  TESTS_CFG+=("$line")
done < <(
  python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    data = {}

cfg = data.get("tests_gate")
if not isinstance(cfg, dict):
    cfg = {}

DEFAULT_SOURCE_ROOTS = [
    "src/main",
    "src",
    "app",
    "apps",
    "packages",
    "services",
    "service",
    "lib",
    "libs",
    "backend",
    "frontend",
]
DEFAULT_SOURCE_EXTS = [
    ".kt",
    ".java",
    ".kts",
    ".groovy",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rb",
    ".rs",
    ".cs",
    ".php",
]
DEFAULT_TEST_PATTERNS = [
    "src/test/{rel_dir}/{base}Test{ext}",
    "src/test/{rel_dir}/{base}Tests{ext}",
    "tests/{rel_dir}/test_{base}{ext}",
    "tests/{rel_dir}/{base}_test{ext}",
    "tests/{rel_dir}/{base}.test{ext}",
    "tests/{rel_dir}/{base}.spec{ext}",
    "test/{rel_dir}/test_{base}{ext}",
    "test/{rel_dir}/{base}_test{ext}",
    "spec/{rel_dir}/{base}_spec{ext}",
    "spec/{rel_dir}/{base}Spec{ext}",
    "__tests__/{rel_dir}/{base}.test{ext}",
    "__tests__/{rel_dir}/{base}.spec{ext}",
]
DEFAULT_EXCLUDE_DIRS = [
    "test",
    "tests",
    "spec",
    "specs",
    "__tests__",
    "androidTest",
    "integrationTest",
    "functionalTest",
    "testFixtures",
]

def norm_list(value, default):
    if value is None:
        value = default
    if isinstance(value, str):
        value = [value]
    elif not isinstance(value, (list, tuple)):
        value = default
    items = []
    for raw in value:
        text = str(raw).strip()
        if not text:
            continue
        text = text.lstrip("./")
        text = text.rstrip("/")
        if not text:
            continue
        items.append(text)
    return items

def norm_exts(value, default):
    if value is None:
        value = default
    if isinstance(value, str):
        value = [value]
    elif not isinstance(value, (list, tuple)):
        value = default
    items = []
    for raw in value:
        text = str(raw).strip()
        if not text:
            continue
        if not text.startswith("."):
            text = f".{text}"
        items.append(text.lower())
    return items

def unique(seq):
    seen = set()
    out = []
    for item in seq:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out

source_roots = unique(norm_list(cfg.get("source_roots"), DEFAULT_SOURCE_ROOTS))
source_roots.sort(key=len, reverse=True)
source_exts = unique(norm_exts(cfg.get("source_extensions"), DEFAULT_SOURCE_EXTS))
test_patterns = unique(norm_list(cfg.get("test_patterns"), DEFAULT_TEST_PATTERNS))
test_exts = unique(norm_exts(cfg.get("test_extensions"), []))
exclude_dirs = unique(
    norm_list(cfg.get("exclude_dirs") or cfg.get("source_exclude_dirs"), DEFAULT_EXCLUDE_DIRS)
)

SEP = "\x1f"

def emit(name, values):
    print(f"{name}=" + SEP.join(values))

emit("SOURCE_ROOTS", source_roots)
emit("SOURCE_EXTS", source_exts)
emit("TEST_PATTERNS", test_patterns)
emit("TEST_EXTS", test_exts)
emit("EXCLUDE_DIRS", exclude_dirs)
PY
) || true

source_roots=()
source_exts=()
test_patterns=()
test_exts=()
exclude_dirs=()
list_sep=$'\x1f'

for line in "${TESTS_CFG[@]}"; do
  case "$line" in
    SOURCE_ROOTS=*)
      IFS="$list_sep" read -r -a source_roots <<< "${line#SOURCE_ROOTS=}"
      ;;
    SOURCE_EXTS=*)
      IFS="$list_sep" read -r -a source_exts <<< "${line#SOURCE_EXTS=}"
      ;;
    TEST_PATTERNS=*)
      IFS="$list_sep" read -r -a test_patterns <<< "${line#TEST_PATTERNS=}"
      ;;
    TEST_EXTS=*)
      IFS="$list_sep" read -r -a test_exts <<< "${line#TEST_EXTS=}"
      ;;
    EXCLUDE_DIRS=*)
      IFS="$list_sep" read -r -a exclude_dirs <<< "${line#EXCLUDE_DIRS=}"
      ;;
  esac
done

emit_research_hint() {
  local target_path="$1"
  [[ -z "$ticket" || -z "$target_path" ]] && return 0
  local message
  message="$(python3 - "$target_path" "$ticket" "$slug_hint" <<'PY'
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

is_excluded_path() {
  local path="$1"
  local part exclude parts
  for exclude in "${exclude_dirs[@]}"; do
    [[ -z "$exclude" ]] && continue
    if [[ "$exclude" == *"/"* ]]; then
      if [[ "$path" == "$exclude" || "$path" == "$exclude/"* ]]; then
        return 0
      fi
      continue
    fi
    IFS='/' read -r -a parts <<< "$path"
    for part in "${parts[@]}"; do
      if [[ "$part" == "$exclude" ]]; then
        return 0
      fi
    done
  done
  return 1
}

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

target_files=()
target_roots=()
for candidate in "${changed_files[@]}"; do
  ext_raw="${candidate##*.}"
  if [[ -z "$ext_raw" || "$ext_raw" == "$candidate" ]]; then
    continue
  fi
  ext_raw="$(printf '%s' "$ext_raw" | tr '[:upper:]' '[:lower:]')"
  ext=".${ext_raw}"
  matched_ext=0
  for allowed in "${source_exts[@]}"; do
    if [[ "$ext" == "$allowed" ]]; then
      matched_ext=1
      break
    fi
  done
  (( matched_ext == 1 )) || continue
  if ((${#exclude_dirs[@]} > 0)) && is_excluded_path "$candidate"; then
    continue
  fi
  match_root=""
  for root in "${source_roots[@]}"; do
    if [[ "$candidate" == "$root/"* ]]; then
      match_root="$root"
      break
    fi
  done
  [[ -n "$match_root" ]] || continue
  target_files+=("$candidate")
  target_roots+=("$match_root")
done

# интересует только code paths из tests_gate
if ((${#target_files[@]} == 0)); then
  exit 0
fi

EVENT_SHOULD_LOG=1
EVENT_STATUS="fail"

missing_files=()
missing_tests=()
for i in "${!target_files[@]}"; do
  path="${target_files[$i]}"
  root="${target_roots[$i]}"
  rel="${path#"${root}"/}"
  rel_dir="$(dirname "$rel")"
  [[ "$rel_dir" == "." ]] && rel_dir=""
  base="${rel##*/}"
  base="${base%.*}"
  ext_raw="${path##*.}"
  ext_raw="$(printf '%s' "$ext_raw" | tr '[:upper:]' '[:lower:]')"
  ext=".${ext_raw}"

  expected_paths=()
  for pattern in "${test_patterns[@]}"; do
    [[ -z "$pattern" ]] && continue
    use_test_ext=0
    if [[ "$pattern" == *"{test_ext}"* ]]; then
      use_test_ext=1
    fi
    if (( use_test_ext == 1 )) && ((${#test_exts[@]} > 0)); then
      ext_candidates=("${test_exts[@]}")
    else
      ext_candidates=("$ext")
    fi
    for test_ext in "${ext_candidates[@]}"; do
      candidate_path="$pattern"
      candidate_path="${candidate_path//\{rel_dir\}/$rel_dir}"
      candidate_path="${candidate_path//\{rel_path\}/$rel}"
      candidate_path="${candidate_path//\{base\}/$base}"
      candidate_path="${candidate_path//\{ext\}/$ext}"
      candidate_path="${candidate_path//\{test_ext\}/$test_ext}"
      while [[ "$candidate_path" == *"//"* ]]; do
        candidate_path="${candidate_path//\/\//\/}"
      done
      candidate_path="${candidate_path#./}"
      expected_paths+=("$candidate_path")
    done
  done

  if ((${#expected_paths[@]} > 0)); then
    deduped=()
    while IFS= read -r candidate; do
      [[ -n "$candidate" ]] && deduped+=("$candidate")
    done < <(printf '%s\n' "${expected_paths[@]}" | awk '!seen[$0]++')
    expected_paths=("${deduped[@]}")
  fi

  has_tests=0
  for candidate_path in "${expected_paths[@]}"; do
    if [[ -f "$candidate_path" ]]; then
      has_tests=1
      break
    fi
  done

  if [[ "$has_tests" -eq 1 ]]; then
    emit_research_hint "$path"
    continue
  fi

  hint=""
  if ((${#expected_paths[@]} == 1)); then
    hint="${expected_paths[0]}"
  elif ((${#expected_paths[@]} >= 2)); then
    hint="${expected_paths[0]} или ${expected_paths[1]}"
    if ((${#expected_paths[@]} > 2)); then
      hint="${hint} (и ещё $(( ${#expected_paths[@]} - 2 )))"
    fi
  else
    hint="(не настроены шаблоны тестов)"
  fi

  missing_files+=("$path")
  missing_tests+=("$hint")
done

if ((${#missing_files[@]} == 0)); then
  EVENT_STATUS="pass"
  exit 0
fi

if [[ "$mode" == "soft" ]]; then
  for i in "${!missing_files[@]}"; do
    echo "WARN: отсутствует тест для ${missing_files[$i]}. Рекомендуется создать ${missing_tests[$i]}." 1>&2
    emit_research_hint "${missing_files[$i]}"
  done
  EVENT_STATUS="warn"
  exit 0
fi

for i in "${!missing_files[@]}"; do
  echo "BLOCK: нет теста для ${missing_files[$i]}. Создайте ${missing_tests[$i]} либо переведите tests_required в config/gates.json в soft/disabled." 1>&2
  emit_research_hint "${missing_files[$i]}"
done
exit 2
