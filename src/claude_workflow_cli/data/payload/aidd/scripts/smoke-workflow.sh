#!/usr/bin/env bash
# Smoke scenario for the Claude workflow bootstrap.
# This script is executed directly and via `claude-workflow smoke`.
# Creates a temporary project, runs init script, mimics the idea→plan→tasks cycle,
# and asserts that gate-workflow blocks/permits source edits as expected.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INIT_SCRIPT="${ROOT_DIR}/init-claude-workflow.sh"
TICKET="demo-checkout"
PAYLOAD='{"tool_input":{"file_path":"src/main/kotlin/App.kt"}}'
CLI_HELPER="${ROOT_DIR}/tools/run_cli.py"
REPO_SRC="$(cd "${ROOT_DIR}/../../../../../" && pwd)/src"
VENDOR_PATH="${ROOT_DIR}/.claude/hooks/_vendor"
export PYTHONPATH="${REPO_SRC}:${VENDOR_PATH}:${PYTHONPATH:-}"
export CLAUDE_WORKFLOW_PYTHON="python3"
export CLAUDE_WORKFLOW_DEV_SRC="${REPO_SRC}"
WORKDIR=""

run_cli() {
  python3 "$CLI_HELPER" "$@"
}

[[ -x "$INIT_SCRIPT" ]] || {
  echo "[smoke] missing init script at $INIT_SCRIPT" >&2
  exit 1
}

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/claude-workflow-smoke.XXXXXX")"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

log() {
  printf '[smoke] %s\n' "$*"
}

assert_gate_exit() {
  local expected="$1"
  local note="$2"
  local output rc
  set +e
  output="$(CLAUDE_PROJECT_DIR="$WORKDIR" "$WORKDIR/.claude/hooks/gate-workflow.sh" <<<"$PAYLOAD" 2>&1)"
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
run_cli init --target . --force >/dev/null
WORKDIR="${TMP_DIR}/aidd"

log "validate plugin hooks wiring"
if [[ ! -f "$WORKDIR/hooks/hooks.json" ]]; then
  echo "[smoke] missing plugin hooks at $WORKDIR/hooks/hooks.json" >&2
  exit 1
fi
python3 - "$WORKDIR" <<'PY'
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
    assert_has("gate-workflow.sh", event)

assert_has("gate-tests.sh", "PreToolUse")
assert_has("gate-qa.sh", "PreToolUse")
assert_has("format-and-test.sh", "PostToolUse")
PY

log "create demo source file"
mkdir -p "$WORKDIR/src/main/kotlin"
cat <<'KT' >"$WORKDIR/src/main/kotlin/App.kt"
package demo

class App {
    fun run(): String = "ok"
}
KT

log "gate allows edits when feature inactive"
assert_gate_exit 0 "no active feature"

log "activate feature ticket"
python3 "$WORKDIR/tools/set_active_feature.py" "$TICKET" --target "$WORKDIR" >/dev/null
[[ -f "$WORKDIR/docs/.active_ticket" ]] || {
  echo "[smoke] failed to set active ticket" >&2
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
        "## PRD Review\n"
        "Status: pending\n",
        encoding="utf-8",
    )
if not research_path.exists():
    research_path.write_text("# Research\n\nStatus: pending\n", encoding="utf-8")
PY

log "auto-collect research context after idea-new (thin context → auto)"
pushd "$WORKDIR" >/dev/null
run_cli research --ticket "$TICKET" --target . --auto --deep-code --call-graph >/dev/null
if ! grep -q "\"call_graph\"" "reports/research/${TICKET}-context.json"; then
  echo "[smoke] expected call_graph in research context" >&2
  exit 1
fi
python3 - "$TICKET" <<'PY'
from pathlib import Path
import json
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
context_path = Path("reports/research") / f"{ticket}-context.json"
targets_path = Path("reports/research") / f"{ticket}-targets.json"
if context_path.exists():
    data = json.loads(context_path.read_text(encoding="utf-8"))
    data.setdefault("status", "reviewed")
    data["status"] = "reviewed"
    data.setdefault("docs", [f"docs/research/{ticket}.md"])
    context_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
if targets_path.exists():
    data = json.loads(targets_path.read_text(encoding="utf-8"))
    docs = data.get("docs") or []
    if f"docs/research/{ticket}.md" not in docs:
        docs.append(f"docs/research/{ticket}.md")
    data["docs"] = docs
    targets_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
PY

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
    content += "\n## PRD Review\nStatus: pending\n"
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
import sys

ticket = sys.argv[1]
path = Path("docs/prd") / f"{ticket}.prd.md"
text = path.read_text(encoding="utf-8")
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
path.write_text(text, encoding="utf-8")
PY

log "analyst-check must pass"
run_cli analyst-check --ticket "$TICKET" --target . >/dev/null

log "expect block until PRD review approved"
assert_gate_exit 2 "pending PRD review"

log "mark PRD review as approved"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/prd") / f"{ticket}.prd.md"
content = path.read_text(encoding="utf-8")
if "## PRD Review" not in content:
    raise SystemExit("PRD Review section missing in smoke scenario")
if "Status: approved" not in content:
    content = content.replace("Status: pending", "Status: approved", 1)
path.write_text(content, encoding="utf-8")
PY

log "expect block until plan exists"
assert_gate_exit 2 "missing plan"

log "apply preset feature-plan"
bash "$INIT_SCRIPT" --preset feature-plan --ticket "$TICKET" >/dev/null
log "ensure plan содержит Architecture & Patterns и reuse"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/plan") / f"{ticket}.md"
text = path.read_text(encoding="utf-8")
if "Architecture & Patterns" not in text:
    text += (
        "\n## Architecture & Patterns\n"
        "- Pattern: service layer + adapters/ports (KISS/YAGNI/DRY/SOLID)\n"
        f"- Reuse: docs/research/{ticket}.md\n"
        "- Scope: domain/application/infra boundaries fixed; avoid over-engineering.\n"
    )
elif "service layer" not in text.lower():
    text += "\n- Pattern: service layer + adapters/ports (KISS/YAGNI/DRY/SOLID)\n"
path.write_text(text, encoding="utf-8")
PY

log "expect block until tasks recorded"
assert_gate_exit 2 "missing tasklist items"

log "apply preset feature-impl"
bash "$INIT_SCRIPT" --preset feature-impl --ticket "$TICKET" >/dev/null
log "tasklist snapshot"
tail -n 10 "docs/tasklist/${TICKET}.md"

log "gate now allows source edits"
run_cli reviewer-tests --ticket "$TICKET" --target . --status optional >/dev/null
run_cli tasks-derive --source research --ticket "$TICKET" --target . --append >/dev/null
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

log "gate blocks when checkbox is missing"
assert_gate_exit 2 "missing progress checkbox"

log "progress CLI reports missing checkbox"
if progress_output="$(run_cli progress --target . --ticket "$TICKET" --source implement 2>&1)"; then
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
if ! progress_ok="$(run_cli progress --target . --ticket "$TICKET" --source implement --verbose 2>&1)"; then
  printf '[smoke] expected progress CLI to pass after checkbox update:\n%s\n' "$progress_ok" >&2
  exit 1
fi
assert_gate_exit 0 "progress checkbox added"

log "run QA command and ensure report created"
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
for old, new in replacements.items():
    if old in text:
        text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
PY

if ! run_cli qa --ticket "$TICKET" --target . --report "reports/qa/${TICKET}.json" --gate --emit-json >/dev/null; then
  echo "[smoke] qa command failed" >&2
  exit 1
fi
[[ -f "reports/qa/${TICKET}.json" ]] || {
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
run_cli tasks-derive --source qa --ticket "$TICKET" --target . --append >/dev/null
grep -q "handoff:qa" "docs/tasklist/${TICKET}.md" || {
  echo "[smoke] tasks-derive did not update tasklist" >&2
  exit 1
}
if ! progress_handoff="$(run_cli progress --target . --ticket "$TICKET" --source handoff --verbose 2>&1)"; then
  printf '[smoke] expected progress handoff check to pass:\n%s\n' "$progress_handoff" >&2
  exit 1
fi

log "verify generated artifacts"
[[ -f "docs/prd/${TICKET}.prd.md" ]]
[[ -f "docs/plan/${TICKET}.md" ]]

log "reviewer requests automated tests"
run_cli reviewer-tests --ticket "$TICKET" --target . --status required >/dev/null
[[ -f "reports/reviewer/${TICKET}.json" ]] || {
  echo "[smoke] reviewer marker was not created" >&2
  exit 1
}

log "reviewer clears test requirement"
run_cli reviewer-tests --ticket "$TICKET" --target . --status optional >/dev/null
grep -q "Status: approved" "docs/prd/${TICKET}.prd.md"
grep -q "Demo Checkout" "docs/tasklist/${TICKET}.md"

log "smoke scenario passed"
popd >/dev/null
popd >/dev/null

log "negative scenario: gate fails on incorrect target without aidd workflow"
BAD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/claude-workflow-smoke-bad-target.XXXXXX")"
set +e
bad_output="$(CLAUDE_PLUGIN_ROOT="$BAD_DIR" "$WORKDIR/.claude/hooks/gate-workflow.sh" <<<"$PAYLOAD" 2>&1)"
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
