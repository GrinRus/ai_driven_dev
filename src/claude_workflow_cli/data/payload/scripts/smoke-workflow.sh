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
  output="$(CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/gate-workflow.sh <<<"$PAYLOAD" 2>&1)"
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
bash "$INIT_SCRIPT" --force >/dev/null

log "create demo source file"
mkdir -p src/main/kotlin
cat <<'KT' >src/main/kotlin/App.kt
package demo

class App {
    fun run(): String = "ok"
}
KT

log "gate allows edits when feature inactive"
assert_gate_exit 0 "no active feature"

log "activate feature ticket"
python3 tools/set_active_feature.py "$TICKET" >/dev/null

log "auto-collect research context before analyst"
run_cli research --ticket "$TICKET" --target . --auto >/dev/null

log "expect block while PRD в статусе draft"
assert_gate_exit 2 "draft PRD"

log "apply preset feature-prd"
bash "$INIT_SCRIPT" --preset feature-prd --ticket "$TICKET" >/dev/null

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

log "expect block until research report ready"
assert_gate_exit 2 "missing research report"

log "mark research summary as reviewed"
python3 - "$TICKET" <<'PY'
from pathlib import Path
import sys

ticket = sys.argv[1]
path = Path("docs/research") / f"{ticket}.md"
content = path.read_text(encoding="utf-8")
if "Status: reviewed" not in content:
    content = content.replace("Status: pending", "Status: reviewed", 1)
path.write_text(content, encoding="utf-8")
PY

log "expect block until plan exists"
assert_gate_exit 2 "missing plan"

log "apply preset feature-plan"
bash "$INIT_SCRIPT" --preset feature-plan --ticket "$TICKET" >/dev/null

log "expect block until tasks recorded"
assert_gate_exit 2 "missing tasklist items"

log "apply preset feature-impl"
bash "$INIT_SCRIPT" --preset feature-impl --ticket "$TICKET" >/dev/null
log "tasklist snapshot"
tail -n 10 "docs/tasklist/${TICKET}.md"

log "gate now allows source edits"
assert_gate_exit 0 "all artifacts ready"

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
if ! run_cli qa --ticket "$TICKET" --target . --report "reports/qa/${TICKET}.json" --gate --emit-json >/dev/null; then
  echo "[smoke] qa command failed" >&2
  exit 1
fi
[[ -f "reports/qa/${TICKET}.json" ]] || {
  echo "[smoke] qa report not generated" >&2
  exit 1
}

log "gate blocks, если изменена только RU-версия промпта"
python3 - <<'PY'
from pathlib import Path

path = Path('.claude/agents/analyst.md')
text = path.read_text(encoding='utf-8')
text = text.replace('prompt_version: 1.0.0', 'prompt_version: 1.0.1', 1)
text = text.replace('source_version: 1.0.0', 'source_version: 1.0.1', 1)
path.write_text(text, encoding='utf-8')
PY

PROMPT_PAYLOAD='{"tool_input":{"file_path":".claude/agents/analyst.md"}}'
set +e
prompt_output="$(CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/gate-workflow.sh <<<"$PROMPT_PAYLOAD" 2>&1)"
prompt_rc=$?
set -e
if [[ "$prompt_rc" -ne 2 ]]; then
  printf '[smoke] gate-workflow should block RU-only prompt change: rc=%s\n%s\n' "$prompt_rc" "$prompt_output" >&2
  exit 1
fi
echo "$prompt_output" | grep -q "Lang-Parity" || {
  printf '[smoke] expected Lang-Parity hint:\n%s\n' "$prompt_output" >&2
  exit 1
}

log "синхронизируем EN-локаль и убеждаемся, что gate пропускает"
python3 - <<'PY'
from pathlib import Path

path = Path('prompts/en/agents/analyst.md')
text = path.read_text(encoding='utf-8')
text = text.replace('prompt_version: 1.0.0', 'prompt_version: 1.0.1', 1)
text = text.replace('source_version: 1.0.0', 'source_version: 1.0.1', 1)
path.write_text(text, encoding='utf-8')
PY

if ! CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/gate-workflow.sh <<<"$PROMPT_PAYLOAD" >/dev/null; then
  echo "[smoke] gate-workflow should pass after EN sync" >&2
  exit 1
fi

log "verify generated artifacts"
[[ -f "docs/prd/${TICKET}.prd.md" ]]
[[ -f "docs/plan/${TICKET}.md" ]]
grep -q "Claude Code" "docs/prd/${TICKET}.prd.md"

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

popd >/dev/null
log "smoke scenario passed"
log "аналогичная проверка для команд"
python3 - <<'PY'
from pathlib import Path

path = Path('.claude/commands/plan-new.md')
text = path.read_text(encoding='utf-8')
text = text.replace('prompt_version: 1.0.0', 'prompt_version: 1.0.1', 1)
text = text.replace('source_version: 1.0.0', 'source_version: 1.0.1', 1)
path.write_text(text, encoding='utf-8')
PY

CMD_PAYLOAD='{"tool_input":{"file_path":".claude/commands/plan-new.md"}}'
set +e
cmd_output="$(CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/gate-workflow.sh <<<"$CMD_PAYLOAD" 2>&1)"
cmd_rc=$?
set -e
if [[ "$cmd_rc" -ne 2 ]]; then
  printf '[smoke] gate-workflow should block RU-only command change: rc=%s\n%s\n' "$cmd_rc" "$cmd_output" >&2
  exit 1
fi
log "gate message: $cmd_output"

log "удаляем EN-команду, но включаем Lang-Parity: skip"
python3 - <<'PY'
from pathlib import Path

ru_path = Path('.claude/commands/plan-new.md')
text = ru_path.read_text(encoding='utf-8')
if 'Lang-Parity: skip' not in text:
    text = text.replace('model: inherit', 'model: inherit\nLang-Parity: skip', 1)
ru_path.write_text(text, encoding='utf-8')
en_path = Path('prompts/en/commands/plan-new.md')
if en_path.exists():
    en_path.unlink()
PY

if ! CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/gate-workflow.sh <<<"$CMD_PAYLOAD" >/dev/null; then
  echo "[smoke] gate-workflow should pass with Lang-Parity skip" >&2
  exit 1
fi

log "возвращаем EN-команду и удаляем skip"
python3 - "$ROOT_DIR" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
template = root / "prompts" / "en" / "commands" / "plan-new.md"
dest = Path('prompts/en/commands/plan-new.md')
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(template.read_text(encoding='utf-8'), encoding='utf-8')
ru_path = Path('.claude/commands/plan-new.md')
text = ru_path.read_text(encoding='utf-8')
text = text.replace('\nLang-Parity: skip', '', 1)
ru_path.write_text(text, encoding='utf-8')
PY

if ! CLAUDE_PROJECT_DIR="$PWD" ./.claude/hooks/gate-workflow.sh <<<"$CMD_PAYLOAD" >/dev/null; then
  echo "[smoke] gate-workflow should pass after restoring EN command" >&2
  exit 1
fi
