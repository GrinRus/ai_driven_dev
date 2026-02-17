#!/usr/bin/env bash
# Smoke scenario for the Claude workflow bootstrap.
# This script is executed directly via tests/repo_tools/smoke-workflow.sh.
# Creates a temporary project, runs init script, mimics the idea→plan→review-spec→spec-interview→tasks cycle,
# then performs a minimal loop (tasks → implement → review → qa) via CLI tools,
# and asserts that gate-workflow blocks/permits source edits as expected.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TICKET="demo-checkout"
PAYLOAD='{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
export PYTHONDONTWRITEBYTECODE="1"
WORKDIR=""
WORKSPACE_ROOT=""
PLUGIN_GIT_STATUS_BEFORE="$(git -C "$PLUGIN_ROOT" status --porcelain --untracked-files=all 2>/dev/null || true)"

run_cli() {
  local cmd="$1"
  shift
  local entrypoint=""
  local mode="exec"
  case "$cmd" in
    init)
      entrypoint="$PLUGIN_ROOT/skills/aidd-init/runtime/init.py"
      mode="python"
      ;;
    loop-pack|loop-step|loop-run|preflight-prepare|preflight-result-validate|output-contract)
      local loop_runtime=""
      case "$cmd" in
        loop-pack) loop_runtime="loop_pack.py" ;;
        loop-step) loop_runtime="loop_step.py" ;;
        loop-run) loop_runtime="loop_run.py" ;;
        preflight-prepare) loop_runtime="preflight_prepare.py" ;;
        preflight-result-validate) loop_runtime="preflight_result_validate.py" ;;
        output-contract) loop_runtime="output_contract.py" ;;
      esac
      entrypoint="$PLUGIN_ROOT/skills/aidd-loop/runtime/${loop_runtime}"
      mode="python"
      ;;
    analyst-check)
      entrypoint="$PLUGIN_ROOT/skills/idea-new/runtime/analyst_check.py"
      mode="python"
      ;;
    research-check)
      entrypoint="$PLUGIN_ROOT/skills/plan-new/runtime/research_check.py"
      mode="python"
      ;;
    prd-review)
      entrypoint="$PLUGIN_ROOT/skills/review-spec/runtime/prd_review_cli.py"
      mode="python"
      ;;
    spec-interview)
      entrypoint="$PLUGIN_ROOT/skills/spec-interview/runtime/spec_interview.py"
      mode="python"
      ;;
    tasks-new)
      entrypoint="$PLUGIN_ROOT/skills/tasks-new/runtime/tasks_new.py"
      mode="python"
      ;;
    research)
      entrypoint="$PLUGIN_ROOT/skills/researcher/runtime/research.py"
      mode="python"
      ;;
    reports-pack|rlm-nodes-build|rlm-links-build|rlm-jsonl-compact|rlm-finalize|rlm-verify)
      local rlm_runtime=""
      case "$cmd" in
        reports-pack) rlm_runtime="reports_pack.py" ;;
        rlm-nodes-build) rlm_runtime="rlm_nodes_build.py" ;;
        rlm-links-build) rlm_runtime="rlm_links_build.py" ;;
        rlm-jsonl-compact) rlm_runtime="rlm_jsonl_compact.py" ;;
        rlm-finalize) rlm_runtime="rlm_finalize.py" ;;
        rlm-verify) rlm_runtime="rlm_verify.py" ;;
      esac
      entrypoint="$PLUGIN_ROOT/skills/aidd-rlm/runtime/${rlm_runtime}"
      mode="python"
      ;;
    review-pack|review-report|reviewer-tests|context-pack)
      local review_runtime=""
      case "$cmd" in
        review-pack) review_runtime="review_pack.py" ;;
        review-report) review_runtime="review_report.py" ;;
        reviewer-tests) review_runtime="reviewer_tests.py" ;;
        context-pack) review_runtime="context_pack.py" ;;
      esac
      entrypoint="$PLUGIN_ROOT/skills/review/runtime/${review_runtime}"
      mode="python"
      ;;
    qa)
      entrypoint="$PLUGIN_ROOT/skills/qa/runtime/qa.py"
      mode="python"
      ;;
    status|index-sync)
      local status_runtime=""
      case "$cmd" in
        status) status_runtime="status.py" ;;
        index-sync) status_runtime="index_sync.py" ;;
      esac
      entrypoint="$PLUGIN_ROOT/skills/status/runtime/${status_runtime}"
      mode="python"
      ;;
    *)
      local docio_runtime=""
      local flow_state_runtime=""
      local observability_runtime=""
      local rlm_runtime=""
      local core_runtime=""
      case "$cmd" in
        actions-apply) docio_runtime="actions_apply.py" ;;
        actions-validate) docio_runtime="actions_validate.py" ;;
        context-expand) docio_runtime="context_expand.py" ;;
        context-map-validate) docio_runtime="context_map_validate.py" ;;
        dag-export) observability_runtime="dag_export.py" ;;
        diff-boundary-check) core_runtime="diff_boundary_check.py" ;;
        doctor) observability_runtime="doctor.py" ;;
        identifiers) observability_runtime="identifiers.py" ;;
        md-patch) docio_runtime="md_patch.py" ;;
        md-slice) docio_runtime="md_slice.py" ;;
        plan-review-gate) core_runtime="plan_review_gate.py" ;;
        prd-check) flow_state_runtime="prd_check.py" ;;
        prd-review-gate) core_runtime="prd_review_gate.py" ;;
        progress) flow_state_runtime="progress_cli.py" ;;
        rlm-slice) rlm_runtime="rlm_slice.py" ;;
        set-active-feature) flow_state_runtime="set_active_feature.py" ;;
        set-active-stage) flow_state_runtime="set_active_stage.py" ;;
        skill-contract-validate) core_runtime="skill_contract_validate.py" ;;
        stage-result) flow_state_runtime="stage_result.py" ;;
        status-summary) flow_state_runtime="status_summary.py" ;;
        tasklist-check|tasklist-normalize) flow_state_runtime="tasklist_check.py" ;;
        tasks-derive) flow_state_runtime="tasks_derive.py" ;;
        tests-log) observability_runtime="tests_log.py" ;;
        tools-inventory) observability_runtime="tools_inventory.py" ;;
      esac
      if [[ -n "$docio_runtime" ]]; then
        entrypoint="$PLUGIN_ROOT/skills/aidd-docio/runtime/${docio_runtime}"
        mode="python"
      elif [[ -n "$flow_state_runtime" ]]; then
        entrypoint="$PLUGIN_ROOT/skills/aidd-flow-state/runtime/${flow_state_runtime}"
        mode="python"
      elif [[ -n "$observability_runtime" ]]; then
        entrypoint="$PLUGIN_ROOT/skills/aidd-observability/runtime/${observability_runtime}"
        mode="python"
      elif [[ -n "$rlm_runtime" ]]; then
        entrypoint="$PLUGIN_ROOT/skills/aidd-rlm/runtime/${rlm_runtime}"
        mode="python"
      elif [[ -n "$core_runtime" ]]; then
        entrypoint="$PLUGIN_ROOT/skills/aidd-core/runtime/${core_runtime}"
        mode="python"
      else
        echo "[smoke] unsupported command in run_cli(): $cmd" >&2
        return 2
      fi
      ;;
  esac
  if [[ "$mode" == "python" ]]; then
    env CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" PYTHONPATH="$PLUGIN_ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 "$entrypoint" "$@"
  else
    env CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" "$entrypoint" "$@"
  fi
}

run_hook() {
  local hook="$1"
  shift
  env CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" "$PLUGIN_ROOT/hooks/${hook}" "$@"
}

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aidd-smoke.XXXXXX")"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

log() {
  printf '[smoke] %s\n' "$*"
}

validate_wave_status_sot() {
  python3 - "$PLUGIN_ROOT/backlog.md" <<'PY'
import re
import sys
from pathlib import Path

backlog_path = Path(sys.argv[1])
lines = backlog_path.read_text(encoding="utf-8").splitlines()
wave_entries = {}

for idx, raw in enumerate(lines):
    match = re.match(r"^##\s+Wave\s+(\d+)\b(.*)$", raw.strip(), flags=re.IGNORECASE)
    if not match:
        continue
    wave = match.group(1)
    heading_tail = (match.group(2) or "").strip().lower()
    status = ""
    for look_ahead in lines[idx + 1 : idx + 12]:
        probe = look_ahead.strip()
        if probe.startswith("## "):
            break
        status_match = re.search(r"Статус:\s*([^,_]+)", probe, flags=re.IGNORECASE)
        if status_match:
            status = status_match.group(1).strip().lower()
            break
    archive = any(
        marker in heading_tail for marker in ("archive", "архив", "historical", "history", "истор")
    ) or any(marker in status for marker in ("archive", "архив", "не sot"))
    wave_entries.setdefault(wave, []).append({"line": idx + 1, "status": status, "archive": archive})

issues = []
target_wave = "96"
entries = wave_entries.get(target_wave, [])
active_entries = [entry for entry in entries if not entry["archive"]]
statuses = {entry["status"] for entry in active_entries if entry["status"]}
if len(active_entries) > 1:
    lines_set = ", ".join(str(entry["line"]) for entry in active_entries)
    issues.append(f"wave {target_wave}: multiple active sections ({lines_set})")
if len(statuses) > 1:
    issues.append(f"wave {target_wave}: conflicting active statuses ({', '.join(sorted(statuses))})")

if issues:
    for issue in issues:
        print(f"[smoke] backlog status policy violation: {issue}", file=sys.stderr)
    raise SystemExit(1)
PY
}

seed_preflight_contract_artifacts() {
  local ticket="$1"
  local stage="$2"
  local scope_key="$3"
  local actions_dir="$WORKDIR/reports/actions/${ticket}/${scope_key}"
  local context_dir="$WORKDIR/reports/context/${ticket}"
  local loops_dir="$WORKDIR/reports/loops/${ticket}/${scope_key}"
  local logs_dir="$WORKDIR/reports/logs/${stage}/${ticket}/${scope_key}"

  mkdir -p "$actions_dir" "$context_dir" "$loops_dir" "$logs_dir"

  cat >"$actions_dir/${stage}.actions.template.json" <<'JSON'
{"schema_version":"aidd.actions.v1","actions":[]}
JSON
  cat >"$actions_dir/${stage}.actions.json" <<'JSON'
{"schema_version":"aidd.actions.v1","actions":[]}
JSON
  cat >"$context_dir/${scope_key}.readmap.json" <<'JSON'
{"schema":"aidd.context_map.v1","allowed_paths":["src/**"]}
JSON
  cat >"$context_dir/${scope_key}.readmap.md" <<'MD'
# readmap
MD
  cat >"$context_dir/${scope_key}.writemap.json" <<'JSON'
{"schema":"aidd.context_map.v1","allowed_paths":["src/**"]}
JSON
  cat >"$context_dir/${scope_key}.writemap.md" <<'MD'
# writemap
MD
  cat >"$loops_dir/stage.preflight.result.json" <<'JSON'
{"schema":"aidd.stage_result.preflight.v1","status":"ok"}
JSON
  echo "ok" >"$logs_dir/wrapper.preflight.log"
  echo "ok" >"$logs_dir/wrapper.run.log"
  echo "ok" >"$logs_dir/wrapper.postflight.log"
  cat >"$loops_dir/output.contract.json" <<JSON
{"status":"ok","actions_log":"aidd/reports/actions/${ticket}/${scope_key}/${stage}.actions.json"}
JSON
}

assert_gate_exit() {
  local expected="$1"
  local note="$2"
  local output rc
  set +e
  output="$(CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" "$PLUGIN_ROOT/hooks/gate-workflow.sh" <<<"$PAYLOAD" 2>&1)"
  rc=$?
  set -e
  if [[ "$rc" -ne "$expected" ]]; then
    printf '[smoke] gate-workflow mismatch (%s): expected %s, got %s\n' "$note" "$expected" "$rc" >&2
    printf '[smoke] gate output:\n%s\n' "$output" >&2
    exit 1
  fi
  log "gate-workflow -> ${rc} (${note})"
}

log "working directory: $TMP_DIR"
pushd "$TMP_DIR" >/dev/null
log "initialise git repository"
git init -q
git config user.name "Smoke Bot"
git config user.email "smoke@example.com"

log "bootstrap workflow scaffolding"
run_cli init --force >/dev/null
WORKDIR="${TMP_DIR}/aidd"
WORKSPACE_ROOT="${TMP_DIR}"
export CLAUDE_PLUGIN_ROOT="${PLUGIN_ROOT}"

log "tune gates for smoke (optional deps)"
python3 - "$WORKDIR" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
gates_path = root / "config" / "gates.json"
data = json.loads(gates_path.read_text(encoding="utf-8"))
rlm = data.get("rlm") or {}
rlm["required_for_langs"] = []
data["rlm"] = rlm
gates_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
PY

log "validate plugin hooks wiring"
if [[ ! -f "$PLUGIN_ROOT/hooks/hooks.json" ]]; then
  echo "[smoke] missing plugin hooks at $PLUGIN_ROOT/hooks/hooks.json" >&2
  exit 1
fi
python3 - "$PLUGIN_ROOT" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
hooks_path = root / "hooks" / "hooks.json"
hooks = json.loads(hooks_path.read_text(encoding="utf-8"))

def commands(event: str) -> list[str]:
    return [
        hook.get("command", "")
        for entry in hooks.get("hooks", {}).get(event, [])
        for hook in entry.get("hooks", [])
    ]

def assert_has(needle: str, event: str) -> None:
    cmds = commands(event)
    if not any(needle in cmd for cmd in cmds):
        raise SystemExit(f"{needle} missing in {event}: {cmds}")

for event in ("PreToolUse", "UserPromptSubmit", "Stop", "SubagentStop"):
    if event == "Stop":
        assert_has("gate-workflow.sh", event)
        assert_has("gate-tests.sh", event)
        assert_has("gate-qa.sh", event)
        assert_has("format-and-test.sh", event)
        assert_has("lint-deps.sh", event)
    if event == "SubagentStop":
        assert_has("context-gc-stop.sh", event)
    if event == "PreToolUse":
        assert_has("context-gc-pretooluse.sh", event)
    if event == "UserPromptSubmit":
        assert_has("context-gc-userprompt.sh", event)
PY

log "validate backlog wave status source-of-truth policy"
validate_wave_status_sot

log "run context-gc hooks"
run_hook context-gc-precompact.sh >/dev/null
run_hook context-gc-sessionstart.sh >/dev/null
run_hook context-gc-pretooluse.sh >/dev/null
run_hook context-gc-userprompt.sh >/dev/null

log "create demo source file"
mkdir -p "$WORKDIR/src/main/kotlin"
cat <<'KT' >"$WORKDIR/src/main/kotlin/App.kt"
package demo

class App {
    fun run(): String = "ok"
}
KT
cat <<'KT' >"$WORKDIR/src/main/kotlin/CheckoutService.kt"
package demo

class CheckoutService {
    fun checkout(): String {
        val app = App()
        return app.run()
    }
}
KT

log "gate allows edits when feature inactive"
assert_gate_exit 0 "no active feature"

log "activate feature ticket"
run_cli set-active-feature "$TICKET" >/dev/null
[[ -f "$WORKDIR/docs/.active.json" ]] || {
  echo "[smoke] failed to set active ticket" >&2
  exit 1
}

log "run research targets-only"
run_cli research --ticket "$TICKET" --targets-only --paths src/main --rlm-paths src/main --keywords checkout >/dev/null
[[ -f "$WORKDIR/reports/research/${TICKET}-rlm-targets.json" ]] || {
  echo "[smoke] research did not create rlm-targets" >&2
  exit 1
}

log "simulate idea-new: seed draft PRD with questions and pending research"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
base = Path("docs")
(base / "prd").mkdir(parents=True, exist_ok=True)
(base / "research").mkdir(parents=True, exist_ok=True)
(base / "plan").mkdir(parents=True, exist_ok=True)
(base / "tasklist").mkdir(parents=True, exist_ok=True)
prd_path = base / "prd" / f"{ticket}.prd.md"
research_path = base / "research" / f"{ticket}.md"
if not prd_path.exists():
    prd_path.write_text(
        "# PRD\n\n"
        "## Диалог analyst\n"
        "Status: draft\n\n"
        f"Researcher: docs/research/{ticket}.md (Status: pending)\n\n"
        "Вопрос 1: Какие ограничения по среде?\n"
        "Ответ 1: TBD\n\n"
        "## AIDD:RESEARCH_HINTS\n"
        "- **Paths**: src/main\n"
        "- **Keywords**: checkout\n"
        "- **Notes**: smoke baseline\n\n"
        "## PRD Review\n"
        "Status: pending\n",
        encoding="utf-8",
    )
if not research_path.exists():
    research_path.write_text("# Research\n\nStatus: pending\n", encoding="utf-8")
PY

log "run researcher stage (generate RLM artifacts)"
pushd "$WORKDIR" >/dev/null
run_cli research --ticket "$TICKET" --auto --paths src/main --rlm-paths src/main --keywords checkout >/dev/null
python3 - "$TICKET" <<'PY'
import sys
from pathlib import Path

ticket = sys.argv[1]
base = Path("reports/research")
required = [
    base / f"{ticket}-rlm-targets.json",
    base / f"{ticket}-rlm-manifest.json",
    base / f"{ticket}-rlm.worklist.pack.json",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit(f"[smoke] missing RLM artifacts: {missing}")
PY
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/research") / f"{ticket}.md"
if not path.exists():
    raise SystemExit(f"[smoke] missing research doc: {path}")
text = path.read_text(encoding="utf-8")
for marker in ("Status: warn", "Status: pending", "Status: draft"):
    if marker in text:
        text = text.replace(marker, "Status: reviewed", 1)
        break
path.write_text(text, encoding="utf-8")
PY

log "research-check pending reason must be rlm_status_pending before finalize"
set +e
research_pending_output="$(run_cli research-check --ticket "$TICKET" --expected-stage plan 2>&1)"
research_pending_rc=$?
set -e
if [[ $research_pending_rc -eq 0 ]]; then
  echo "[smoke] research-check unexpectedly passed before finalize readiness" >&2
  exit 1
fi
if ! grep -Eq "reason_code=(rlm_status_pending|rlm_links_empty_warn|rlm_nodes_missing|finalize_prereqs_missing)" <<<"$research_pending_output"; then
  echo "[smoke] research-check pending reason mismatch (expected deterministic pending/finalize reason)" >&2
  echo "$research_pending_output" >&2
  exit 1
fi
if grep -q "reason_code=baseline_missing" <<<"$research_pending_output"; then
  echo "[smoke] research-check emitted forbidden baseline_missing in downstream probe" >&2
  echo "$research_pending_output" >&2
  exit 1
fi

log "seed minimal RLM nodes"
python3 - "$TICKET" <<'PY'
import json
import sys
from pathlib import Path
import os

ticket = sys.argv[1]
nodes_path = Path("reports/research") / f"{ticket}-rlm.nodes.jsonl"
nodes_path.parent.mkdir(parents=True, exist_ok=True)
plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", "")).resolve()
if plugin_root and str(plugin_root) not in sys.path:
    sys.path.insert(0, str(plugin_root))
from aidd_runtime.rlm_config import (
    file_id_for_path,
    load_rlm_settings,
    paths_base_for,
    prompt_version,
    rev_sha_for_bytes,
    detect_lang,
)

project_root = Path.cwd().resolve()
base_root = paths_base_for(project_root).resolve()
settings = load_rlm_settings(project_root)
prompt_ver = prompt_version(settings)

def make_node(rel_source: str, *, summary: str, public_symbols: list[str], key_calls: list[str], type_refs: list[str]) -> dict:
    source_path = (project_root / rel_source).resolve()
    data = source_path.read_bytes()
    try:
        rel_path = source_path.relative_to(base_root)
    except ValueError:
        rel_path = source_path
    rel_norm = rel_path.as_posix().lstrip("./")
    file_id = file_id_for_path(Path(rel_norm))
    return {
        "schema": "aidd.rlm_node.v2",
        "schema_version": "v2",
        "node_kind": "file",
        "file_id": file_id,
        "id": file_id,
        "path": rel_norm,
        "rev_sha": rev_sha_for_bytes(data),
        "lang": detect_lang(source_path),
        "prompt_version": prompt_ver,
        "summary": summary,
        "public_symbols": public_symbols,
        "type_refs": type_refs,
        "key_calls": key_calls,
        "framework_roles": ["service"],
        "test_hooks": [],
        "risks": [],
        "verification": "passed",
        "missing_tokens": [],
    }

nodes = [
    make_node(
        "src/main/kotlin/App.kt",
        summary="Smoke baseline node.",
        public_symbols=["App"],
        key_calls=[],
        type_refs=[],
    ),
    make_node(
        "src/main/kotlin/CheckoutService.kt",
        summary="Smoke consumer node.",
        public_symbols=["CheckoutService"],
        key_calls=["App"],
        type_refs=["App"],
    ),
]
nodes_path.write_text("\n".join(json.dumps(item) for item in nodes) + "\n", encoding="utf-8")
PY
log "finalize RLM evidence"
run_cli rlm-finalize --ticket "$TICKET" >/dev/null
python3 - "$TICKET" <<'PY'
import sys
from pathlib import Path

ticket = sys.argv[1]
base = Path("reports/research")
required = [
    base / f"{ticket}-rlm-targets.json",
    base / f"{ticket}-rlm-manifest.json",
    base / f"{ticket}-rlm.worklist.pack.json",
    base / f"{ticket}-rlm.nodes.jsonl",
    base / f"{ticket}-rlm.links.jsonl",
    base / f"{ticket}-rlm.pack.json",
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit(f"[smoke] missing finalized RLM artifacts: {missing}")
PY
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/research") / f"{ticket}.md"
text = path.read_text(encoding="utf-8") if path.exists() else "# Research\n\nStatus: pending\n"
text = text.replace("Status: draft", "Status: pending")
if "Status: reviewed" not in text:
    text = text.replace("Status: pending", "Status: reviewed", 1)
if "Baseline" not in text:
    text += "\nBaseline: автоматическая генерация\n"
path.write_text(text, encoding="utf-8")
PY

log "research-check must pass"
run_cli research-check --ticket "$TICKET" --expected-stage plan >/dev/null

log "expect block while PRD draft / research handoff pending"
assert_gate_exit 2 "draft PRD"

log "analyst answers questions and marks PRD READY"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
prd_path = Path("docs/prd") / f"{ticket}.prd.md"
content = prd_path.read_text(encoding="utf-8")
if "## PRD Review" not in content:
    content += "\n## PRD Review\nStatus: PENDING\n"
if "Вопрос 1:" in content and "TBD" in content:
    content = content.replace("Ответ 1: TBD", "Ответ 1: Покрываем стандартный happy-path и ошибку оплаты.", 1)
if "Status: draft" in content:
    content = content.replace("Status: draft", "Status: READY", 1)
if "Researcher:" not in content:
    content = content.replace("## Диалог analyst", f"## Диалог analyst\nResearcher: docs/research/{ticket}.md (Status: reviewed)", 1)
prd_path.write_text(content, encoding="utf-8")
PY

log "mark analyst dialog ready"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import re
import sys

ticket = sys.argv[1]
path = Path("docs/prd") / f"{ticket}.prd.md"
text = path.read_text(encoding="utf-8")
section_re = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def find_section(text: str, title: str) -> tuple[int | None, int | None]:
    matches = list(section_re.finditer(text))
    for idx, match in enumerate(matches):
        if match.group(1).strip() == title:
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            return start, end
    return None, None


def replace_section(text: str, title: str, new_body: str) -> str:
    start, end = find_section(text, title)
    if start is None or end is None:
        return text
    return text[:start] + "\n" + new_body.strip("\n") + "\n\n" + text[end:]
if "## Диалог analyst" not in text:
    raise SystemExit("an analyst dialog block is expected in the PRD template")
if "Вопрос 1:" in text:
    text = text.replace(
        "Вопрос 1: `<Что нужно уточнить?>`",
        "Вопрос 1: Какие этапы checkout нужно покрыть в демо?",
        1,
    )
if "Ответ 1:" in text:
    text = text.replace(
        "Ответ 1: `<Ответ или TBD>`",
        "Ответ 1: Покрываем стандартный happy-path и ошибку оплаты.",
        1,
    )
if "Status: draft" in text:
    text = text.replace("Status: draft", "Status: READY", 1)
answers_body = "- Answer 1: Покрываем стандартный happy-path и ошибку оплаты."
text = replace_section(text, "AIDD:ANSWERS", answers_body)
open_questions_body = "- `none`"
text = replace_section(text, "AIDD:OPEN_QUESTIONS", open_questions_body)
path.write_text(text, encoding="utf-8")
PY

log "analyst-check must pass"
run_cli analyst-check --ticket "$TICKET" >/dev/null

log "expect block until plan exists"
assert_gate_exit 2 "missing plan"

log "ensure plan template exists"
if [[ ! -f "docs/plan/${TICKET}.md" ]]; then
  cp "docs/plan/template.md" "docs/plan/${TICKET}.md"
fi
log "ensure plan содержит Design & Patterns и reuse"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/plan") / f"{ticket}.md"
text = path.read_text(encoding="utf-8")
if "Design & Patterns" not in text:
    text += (
        "\n## Design & Patterns\n"
        "- Pattern: service layer + adapters/ports (KISS/YAGNI/DRY/SOLID)\n"
        f"- Reuse: docs/research/{ticket}.md\n"
        "- Scope: domain/application/infra boundaries fixed; avoid over-engineering.\n"
    )
elif "service layer" not in text.lower():
    text += "\n- Pattern: service layer + adapters/ports (KISS/YAGNI/DRY/SOLID)\n"
path.write_text(text, encoding="utf-8")
PY

log "mark Plan Review as READY"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/plan") / f"{ticket}.md"
text = path.read_text(encoding="utf-8")
if "## Plan Review" not in text:
    text += "\n## Plan Review\nStatus: READY\n"
elif "Status: READY" not in text:
    text = text.replace("Status: PENDING", "Status: READY", 1)
path.write_text(text, encoding="utf-8")
PY

log "plan-review-gate passes"
run_cli plan-review-gate --ticket "$TICKET" --file-path "src/main/kotlin/App.kt" >/dev/null

log "expect block until PRD review READY"
assert_gate_exit 2 "pending PRD review"

log "mark PRD review as READY"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/prd") / f"{ticket}.prd.md"
content = path.read_text(encoding="utf-8")
if "## PRD Review" not in content:
    raise SystemExit("PRD Review section missing in smoke scenario")
if "Status: READY" not in content:
    if "Status: PENDING" in content:
        content = content.replace("Status: PENDING", "Status: READY", 1)
    else:
        content = content.replace("Status: pending", "Status: READY", 1)
path.write_text(content, encoding="utf-8")
PY

log "run prd-review and prd-review-gate"
run_cli prd-review --ticket "$TICKET" --report "aidd/reports/prd/${TICKET}.json" --emit-text >/dev/null
[[ -f "$WORKDIR/reports/prd/${TICKET}.json" ]] || {
  echo "[smoke] prd-review did not create report" >&2
  exit 1
}
run_cli prd-review-gate --ticket "$TICKET" --file-path "src/main/kotlin/App.kt" >/dev/null

log "expect block until tasks recorded"
assert_gate_exit 2 "missing tasklist items"

log "run stage-owned spec-interview/tasks-new python entrypoints"
run_cli spec-interview --ticket "$TICKET" >/dev/null
run_cli tasks-new --ticket "$TICKET" >/dev/null

log "ensure tasklist template exists"
if [[ ! -f "docs/tasklist/${TICKET}.md" ]]; then
  cp "docs/tasklist/template.md" "docs/tasklist/${TICKET}.md"
fi
log "ensure spec template exists"
if [[ ! -f "docs/spec/${TICKET}.spec.yaml" ]]; then
  mkdir -p "docs/spec"
  cp "docs/spec/template.spec.yaml" "docs/spec/${TICKET}.spec.yaml"
fi

log "mark spec ready"
python3 - "$TICKET" <<'PY'
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ticket = sys.argv[1]
path = Path("docs/spec") / f"{ticket}.spec.yaml"
text = path.read_text(encoding="utf-8")
today = date.today().isoformat()
lines = []
has_status = False
has_updated = False
for line in text.splitlines():
    if line.startswith("status:"):
        lines.append("status: ready")
        has_status = True
        continue
    if line.startswith("updated_at:"):
        lines.append(f'updated_at: "{today}"')
        has_updated = True
        continue
    lines.append(line)
if not has_status:
    lines.insert(0, "status: ready")
if not has_updated:
    lines.insert(1, f'updated_at: "{today}"')
path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

log "update tasklist summary"
python3 - "$TICKET" <<'PY'
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

ticket = sys.argv[1]
path = Path("docs/tasklist") / f"{ticket}.md"
text = path.read_text(encoding="utf-8")
section_re = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
today = date.today().isoformat()


def find_section(text: str, title: str) -> tuple[int | None, int | None]:
    matches = list(section_re.finditer(text))
    for idx, match in enumerate(matches):
        if match.group(1).strip() == title:
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
            return start, end
    return None, None


def replace_section(text: str, title: str, new_body: str) -> str:
    start, end = find_section(text, title)
    if start is None or end is None:
        return text
    return text[:start] + "\n" + new_body.strip("\n") + "\n\n" + text[end:]


spec_pack_body = f"""Updated: {today}
Spec: aidd/docs/spec/{ticket}.spec.yaml (status: ready)
- Goal: smoke spec ready
- Non-goals:
  - none
- Key decisions:
  - smoke decision
- Risks:
  - low"""
text = replace_section(text, "AIDD:SPEC_PACK", spec_pack_body)

test_strategy_body = """- Unit: smoke
- Integration: smoke
- Contract: smoke
- E2E/Stand: smoke
- Test data: fixtures"""
text = replace_section(text, "AIDD:TEST_STRATEGY", test_strategy_body)

test_execution_body = """- profile: none
- tasks: []
- filters: []
- when: manual
- reason: smoke baseline"""
text = replace_section(text, "AIDD:TEST_EXECUTION", test_execution_body)

handoff_body = "- (none)"
text = replace_section(text, "AIDD:HANDOFF_INBOX", handoff_body)

iterations_full_body = f"""- [ ] I1: Smoke bootstrap (iteration_id: I1)
  - parent_iteration_id: none
  - Goal: satisfy tasklist gate
  - Outputs: tasklist ready for implement
  - DoD: tasklist ready for implement
  - Boundaries: docs/tasklist/{ticket}.md
  - Priority: low
  - Blocking: false
  - deps: []
  - locks: []
  - Expected paths:
    - docs/tasklist/{ticket}.md
  - Size budget:
    - max_files: 1
    - max_loc: 200
  - Commands:
    - update tasklist sections
  - Exit criteria:
    - gate-workflow allows source edits
  - Steps:
    - update tasklist sections
    - verify gate
    - record progress
  - Tests:
    - profile: none
    - tasks: []
    - filters: []
  - Acceptance mapping: AC-1
  - Risks & mitigations: low → none
  - Dependencies: none"""
text = replace_section(text, "AIDD:ITERATIONS_FULL", iterations_full_body)

next_3_body = f"""- [ ] I1: Smoke bootstrap (ref: iteration_id=I1)"""
text = replace_section(text, "AIDD:NEXT_3", next_3_body)

path.write_text(text, encoding="utf-8")
PY
log "tasklist snapshot"
tail -n 10 "docs/tasklist/${TICKET}.md"

log "expect block when test execution incomplete"
cp "docs/tasklist/${TICKET}.md" "docs/tasklist/${TICKET}.bak"
python3 - "$TICKET" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

ticket = sys.argv[1]
path = Path("docs/tasklist") / f"{ticket}.md"
text = path.read_text(encoding="utf-8")
section_re = re.compile(r"^##\s+AIDD:TEST_EXECUTION\s*$", re.MULTILINE)
match = section_re.search(text)
if not match:
    raise SystemExit("missing AIDD:TEST_EXECUTION")
start = match.end()
tail = text[start:]
next_heading = re.search(r"^##\s+", tail, re.MULTILINE)
end = start + (next_heading.start() if next_heading else len(tail))
section_lines = text[start:end].splitlines()
section_lines = [line for line in section_lines if "profile:" not in line]
new_section = "\n".join(section_lines).strip("\n")
text = text[:start] + "\n" + new_section + "\n\n" + text[end:]
path.write_text(text, encoding="utf-8")
PY
assert_gate_exit 2 "missing test execution profile"
mv "docs/tasklist/${TICKET}.bak" "docs/tasklist/${TICKET}.md"

log "expect block when plan iteration missing from tasklist"
cp "docs/plan/${TICKET}.md" "docs/plan/${TICKET}.bak"
python3 - "$TICKET" <<'PY'
from __future__ import annotations

import re
import sys
from pathlib import Path

ticket = sys.argv[1]
path = Path("docs/plan") / f"{ticket}.md"
text = path.read_text(encoding="utf-8")
section_re = re.compile(r"^##\s+AIDD:ITERATIONS\s*$", re.MULTILINE)
match = section_re.search(text)
if not match:
    raise SystemExit("missing AIDD:ITERATIONS")
start = match.end()
tail = text[start:]
next_heading = re.search(r"^##\s+", tail, re.MULTILINE)
end = start + (next_heading.start() if next_heading else len(tail))
section = text[start:end].rstrip("\n")
section += "\n- iteration_id: I4\n  - Goal: extra scope\n"
text = text[:start] + "\n" + section.lstrip("\n") + "\n" + text[end:]
path.write_text(text, encoding="utf-8")
PY
assert_gate_exit 2 "plan iteration mismatch"
mv "docs/plan/${TICKET}.bak" "docs/plan/${TICKET}.md"

log "gate now allows source edits"
run_cli set-active-stage implement >/dev/null
run_cli reviewer-tests --ticket "$TICKET" --status optional >/dev/null
run_cli tasks-derive --source research --ticket "$TICKET" --append >/dev/null
run_cli tasklist-normalize --ticket "$TICKET" --fix >/dev/null
seed_preflight_contract_artifacts "$TICKET" "implement" "$TICKET"
# Skip progress gate for preset-created artifacts: no code changes yet
CLAUDE_SKIP_TASKLIST_PROGRESS=1 assert_gate_exit 0 "all artifacts ready"

log "commit baseline state"
git add .
git commit -qm "chore: smoke baseline"

log "modify source without updating tasklist"
cat <<'KT' >src/main/kotlin/App.kt
package demo

class App {
    fun run(): String = "updated"
}
KT

log "configure test policy for format-and-test smoke"
python3 - "$WORKSPACE_ROOT/.claude/settings.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.parent.mkdir(parents=True, exist_ok=True)
if path.exists():
    data = json.loads(path.read_text(encoding="utf-8"))
else:
    data = {}
tests = data.setdefault("automation", {}).setdefault("tests", {})
tests["runner"] = ["/bin/echo"]
tests["fastTasks"] = ["smoke-fast"]
tests["fullTasks"] = ["smoke-full"]
tests["targetedTask"] = "smoke-target"
tests["commonPatterns"] = ["**/package.json"]
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
mkdir -p "$WORKDIR/.cache"
cat >"$WORKDIR/.cache/test-policy.env" <<'EOF'
AIDD_TEST_PROFILE=fast
EOF

log "set review stage for format-and-test"
run_cli set-active-stage review >/dev/null

log "format-and-test uses profile and dedupe"
fmt_first="$("$PLUGIN_ROOT/hooks/format-and-test.sh" 2>&1)"
echo "$fmt_first" | grep -q "Выбранные задачи тестов (targeted): smoke-target" || {
  echo "[smoke] format-and-test did not use targeted profile" >&2
  echo "$fmt_first" >&2
  exit 1
}
log "verify format-and-test log created"
log_file="$(printf '%s\n' "$fmt_first" | sed -n 's/.*Test log: //p' | tail -n 1)"
[[ -f "$log_file" ]] || {
  echo "[smoke] format-and-test log file not found" >&2
  exit 1
}
grep -q "smoke-target" "$log_file" || {
  echo "[smoke] format-and-test log missing expected output" >&2
  cat "$log_file" >&2
  exit 1
}
fmt_second="$("$PLUGIN_ROOT/hooks/format-and-test.sh" 2>&1)"
echo "$fmt_second" | grep -q "Dedupe: тесты уже запускались" || {
  echo "[smoke] dedupe did not skip repeated run" >&2
  echo "$fmt_second" >&2
  exit 1
}
fmt_force="$(AIDD_TEST_FORCE=1 "$PLUGIN_ROOT/hooks/format-and-test.sh" 2>&1)"
echo "$fmt_force" | grep -q "AIDD_TEST_FORCE=1" || {
  echo "[smoke] force flag did not bypass dedupe" >&2
  echo "$fmt_force" >&2
  exit 1
}

log "common patterns trigger full profile"
run_cli set-active-stage qa >/dev/null
cat <<'JSON' >package.json
{
  "name": "smoke-demo",
  "dependencies": {
    "leftpad": "1.0.0"
  }
}
JSON
fmt_common="$("$PLUGIN_ROOT/hooks/format-and-test.sh" 2>&1)"
echo "$fmt_common" | grep -q "Выбранные задачи тестов (full): smoke-full" || {
  echo "[smoke] common patterns did not trigger full profile" >&2
  echo "$fmt_common" >&2
  exit 1
}

log "gate blocks when checkbox is missing"
assert_gate_exit 2 "missing progress checkbox"

log "progress CLI reports missing checkbox"
if progress_output="$(run_cli progress --ticket "$TICKET" --source implement 2>&1)"; then
  printf '[smoke] expected progress CLI to fail but it succeeded:\n%s\n' "$progress_output" >&2
  exit 1
fi
echo "$progress_output" | grep -q "новых \`- \[x\]\`" || {
  printf '[smoke] unexpected progress CLI output:\n%s\n' "$progress_output" >&2
  exit 1
}

log "mark checkbox as completed in tasklist"
today="$(date +%Y-%m-%d)"
printf '\n- [x] Smoke iteration — %s • итерация 1\n' "$today" >> "docs/tasklist/${TICKET}.md"

log "progress CLI passes after checkbox update"
if ! progress_ok="$(run_cli progress --ticket "$TICKET" --source implement --verbose 2>&1)"; then
  printf '[smoke] expected progress CLI to pass after checkbox update:\n%s\n' "$progress_ok" >&2
  exit 1
fi
seed_preflight_contract_artifacts "$TICKET" "qa" "$TICKET"
assert_gate_exit 0 "progress checkbox added"

log "run QA command and ensure report created"
run_cli set-active-stage qa >/dev/null
# pre-mark QA checklist items to avoid false blockers from template
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/tasklist") / f"{ticket}.md"
text = path.read_text(encoding="utf-8")
replacements = {
    "- [ ] Прогнаны unit/integration/e2e": "- [x] Прогнаны unit/integration/e2e",
    "- [ ] Проведено ручное тестирование или UAT": "- [x] Проведено ручное тестирование или UAT",
}
for previous, updated in replacements.items():
    if previous in text:
        text = text.replace(previous, updated, 1)
path.write_text(text, encoding="utf-8")
PY

qa_exit=0
if ! run_cli qa --ticket "$TICKET" --report "aidd/reports/qa/${TICKET}.json" --emit-json >/dev/null; then
  qa_exit=$?
fi
if [[ "$qa_exit" -ne 0 && "$qa_exit" -ne 2 ]]; then
  echo "[smoke] qa command failed (exit=$qa_exit)" >&2
  exit 1
fi
[[ -f "$WORKDIR/reports/qa/${TICKET}.json" ]] || {
  echo "[smoke] qa report not generated" >&2
  exit 1
}
# Inject a finding to exercise tasks-derive handoff path
python3 - "$TICKET" <<'PY'
from pathlib import Path
import json, sys

ticket = sys.argv[1]
report_path = Path("reports/qa") / f"{ticket}.json"
data = json.loads(report_path.read_text(encoding="utf-8"))
data.setdefault("findings", []).append(
    {"severity": "major", "scope": "api", "title": "Smoke coverage", "recommendation": "Add explicit handoff tasks"}
)
report_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
PY

log "derive tasklist items from QA report (handoff)"
run_cli tasks-derive --source qa --ticket "$TICKET" --append >/dev/null
run_cli tasks-derive --source qa --ticket "$TICKET" --append >/dev/null
grep -q "handoff:qa" "docs/tasklist/${TICKET}.md" || {
  echo "[smoke] tasks-derive did not update tasklist" >&2
  exit 1
}
qa_handoff_count="$(grep -c "handoff:qa start" "docs/tasklist/${TICKET}.md" || true)"
[[ "$qa_handoff_count" -eq 1 ]] || {
  echo "[smoke] expected single QA handoff block, got ${qa_handoff_count}" >&2
  exit 1
}
if ! progress_handoff="$(run_cli progress --ticket "$TICKET" --source handoff --verbose 2>&1)"; then
  printf '[smoke] expected progress handoff check to pass:\n%s\n' "$progress_handoff" >&2
  exit 1
fi

log "minimal loop: create loop packs"
run_cli set-active-stage implement >/dev/null
run_cli loop-pack --ticket "$TICKET" --stage implement >/dev/null
[[ -f "reports/loops/${TICKET}/iteration_id_I1.loop.pack.md" ]] || {
  echo "[smoke] loop-pack (implement) did not create pack" >&2
  exit 1
}
run_cli set-active-stage review >/dev/null
python3 <<'PY'
import json
from pathlib import Path

path = Path("docs/.active.json")
payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
payload["work_item"] = "iteration_id=I1"
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
run_cli loop-pack --ticket "$TICKET" --stage review --work-item "iteration_id=I1" >/dev/null

log "create review report and derive handoff tasks"
cat <<'JSON' >"reports/reviewer/${TICKET}-findings.json"
[
  {
    "severity": "major",
    "scope": "api",
    "title": "Review coverage",
    "recommendation": "Add regression checks"
  }
]
JSON
run_cli review-report --ticket "$TICKET" --work-item-key "iteration_id=I1" --findings-file "reports/reviewer/${TICKET}-findings.json" --status warn >/dev/null
run_cli review-pack --ticket "$TICKET" >/dev/null
[[ -f "reports/loops/${TICKET}/iteration_id_I1/review.latest.pack.md" ]] || {
  echo "[smoke] review-pack did not create pack" >&2
  exit 1
}
run_cli tasks-derive --source review --ticket "$TICKET" --append >/dev/null
run_cli tasks-derive --source review --ticket "$TICKET" --append >/dev/null
grep -q "handoff:review" "docs/tasklist/${TICKET}.md" || {
  echo "[smoke] review handoff tasks missing" >&2
  exit 1
}
review_handoff_count="$(grep -c "handoff:review start" "docs/tasklist/${TICKET}.md" || true)"
[[ "$review_handoff_count" -eq 1 ]] || {
  echo "[smoke] expected single review handoff block, got ${review_handoff_count}" >&2
  exit 1
}

log "verify generated artifacts"
[[ -f "docs/prd/${TICKET}.prd.md" ]]
[[ -f "docs/plan/${TICKET}.md" ]]

log "reviewer requests automated tests"
run_cli reviewer-tests --ticket "$TICKET" --status required >/dev/null
[[ -f "$WORKDIR/reports/reviewer/${TICKET}/iteration_id_I1.tests.json" ]] || {
  echo "[smoke] reviewer marker was not created" >&2
  exit 1
}

log "reviewer clears test requirement"
run_cli reviewer-tests --ticket "$TICKET" --status optional >/dev/null
grep -q "Status: READY" "docs/prd/${TICKET}.prd.md"
grep -q "Tasklist:" "docs/tasklist/${TICKET}.md"

log "loop RCA regression guard (TST-001)"
(
  cd "$PLUGIN_ROOT"
  env CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" PYTHONPATH="$PLUGIN_ROOT${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m pytest -q \
      tests/test_loop_step.py::LoopStepTests::test_loop_step_tst001_fixture_stale_stage_missing_stage_result \
      tests/test_loop_run.py::LoopRunTests::test_loop_run_tst001_rca_fixture_reason_precedence_strict \
      tests/test_loop_run.py::LoopRunTests::test_loop_run_tst001_rca_fixture_reason_precedence_ralph \
      tests/test_loop_run.py::LoopRunTests::test_loop_run_marks_marker_report_noise_without_signal
)

log "smoke scenario passed"
popd >/dev/null
popd >/dev/null

log "negative scenario: gate fails on incorrect target without aidd workflow"
BAD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aidd-smoke-bad-target.XXXXXX")"
set +e
bad_output="$(cd "$BAD_DIR" && CLAUDE_PLUGIN_ROOT="$PLUGIN_ROOT" "$PLUGIN_ROOT/hooks/gate-workflow.sh" <<<"$PAYLOAD" 2>&1)"
bad_rc=$?
set -e
if [[ "$bad_rc" -eq 0 ]]; then
  echo "[smoke] expected gate-workflow to fail for missing aidd/docs" >&2
  echo "$bad_output" >&2
  exit 1
fi
echo "$bad_output" | grep -qi "aidd/docs not found" || {
  echo "[smoke] unexpected gate-workflow output for bad target:" >&2
  echo "$bad_output" >&2
  exit 1
}
rm -rf "$BAD_DIR"

PLUGIN_GIT_STATUS_AFTER="$(git -C "$PLUGIN_ROOT" status --porcelain --untracked-files=all 2>/dev/null || true)"
if [[ "$PLUGIN_GIT_STATUS_AFTER" != "$PLUGIN_GIT_STATUS_BEFORE" ]]; then
  echo "[smoke] plugin write-safety violation: plugin git status changed during smoke run" >&2
  echo "[smoke] before:" >&2
  printf '%s\n' "$PLUGIN_GIT_STATUS_BEFORE" >&2
  echo "[smoke] after:" >&2
  printf '%s\n' "$PLUGIN_GIT_STATUS_AFTER" >&2
  exit 1
fi
