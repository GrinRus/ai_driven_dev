#!/usr/bin/env bash
# init-claude-workflow.sh
# Bootstraps Claude Code workflow for Java/Kotlin monorepos.
# Creates .claude commands/agents/hooks, commit/branch conventions,
# Gradle selective-tests logic, and basic docs (PRD/ADR templates).
#
# Usage:
#   bash init-claude-workflow.sh [--commit-mode MODE] [--enable-ci] [--force] [--dry-run]
#     --commit-mode   ticket-prefix | conventional | mixed   (default: ticket-prefix)
#     --enable-ci     add a minimal GitHub Actions workflow (manual trigger)
#     --force         overwrite existing files
#     --dry-run       log planned actions without touching the filesystem
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"
ROOT_DIR="$(pwd)"

COMMIT_MODE="ticket-prefix"
ENABLE_CI=0
FORCE=0
DRY_RUN=0

log_info()   { printf '[INFO] %s\n' "$*"; }
log_warn()   { printf '[WARN] %s\n' "$*" >&2; }
log_error()  { printf '[ERROR] %s\n' "$*" >&2; }
die()        { log_error "$*"; exit 1; }

usage() {
  cat <<'EOF'
Usage: bash init-claude-workflow.sh [options]
  --commit-mode MODE   ticket-prefix | conventional | mixed   (default: ticket-prefix)
  --enable-ci          add GitHub Actions workflow (manual trigger)
  --force              overwrite existing files
  --dry-run            show planned actions without writing files
  -h, --help           print this help
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --commit-mode)
        [[ $# -ge 2 ]] || die "--commit-mode requires a value"
        COMMIT_MODE="$2"; shift 2;;
      --enable-ci) ENABLE_CI=1; shift;;
      --force)     FORCE=1; shift;;
      --dry-run)   DRY_RUN=1; shift;;
      -h|--help)   usage; exit 0;;
      *)           die "Unknown argument: $1";;
    esac
  done

  case "$COMMIT_MODE" in
    ticket-prefix|conventional|mixed) ;;
    *) die "Unsupported --commit-mode: $COMMIT_MODE";;
  esac
}

require_command() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || die "Missing dependency: $cmd"
}

check_dependencies() {
  log_info "Checking prerequisites"
  require_command bash
  require_command git
  require_command python3

  local has_gradle=0
  if [[ -x "$ROOT_DIR/gradlew" ]]; then
    has_gradle=1
  elif command -v gradle >/dev/null 2>&1; then
    has_gradle=1
  fi

  if [[ "$has_gradle" -eq 1 ]]; then
    log_info "Gradle detected"
  else
    log_warn "Gradle not found (expect ./gradlew or gradle). Selective tests will be unavailable until installed."
  fi

  if command -v ktlint >/dev/null 2>&1; then
    log_info "ktlint detected"
  else
    log_warn "ktlint not found. Formatting step will be skipped if Spotless is absent."
  fi
}

ensure_directory() {
  local dir="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] ensure directory $dir/"
  else
    mkdir -p "$dir"
  fi
}

write_template() {
  local path="$1"
  if [[ -e "$path" && "$FORCE" -ne 1 ]]; then
    log_warn "skip: $path (exists, use --force to overwrite)"
    cat >/dev/null
    return
  fi

  local dir
  dir="$(dirname "$path")"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] write $path"
    cat >/dev/null
  else
    mkdir -p "$dir"
    cat >"$path"
    log_info "wrote: $path"
  fi
}

set_executable() {
  local path="$1"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] chmod +x $path"
  else
    chmod +x "$path"
  fi
}

replace_commit_mode() {
  local path="config/conventions.json"
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[dry-run] set commit mode to $COMMIT_MODE in $path"
    return
  fi
  python3 - <<PY
import json, pathlib
path = pathlib.Path("$path")
data = json.loads(path.read_text(encoding="utf-8"))
data.setdefault("commit", {})["mode"] = "$COMMIT_MODE"
path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
  log_info "commit mode set to $COMMIT_MODE"
}

generate_directories() {
  log_info "Ensuring directory structure"
  local dirs=(
    ".claude"
    ".claude/commands"
    ".claude/agents"
    ".claude/hooks"
    ".claude/gradle"
    ".claude/cache"
    "config"
    "scripts"
    "docs"
    "docs/prd"
    "docs/adr"
  )
  for dir in "${dirs[@]}"; do
    ensure_directory "$dir"
  done
}

generate_core_docs() {
  write_template "CLAUDE.md" <<'MD'
# CLAUDE.md
Стек: Java/Kotlin (Gradle монорепо).
Ветки: feature/<TICKET> | feat/<scope> | mixed (см. config/conventions.json).
Коммиты: ticket-prefix | conventional | mixed.
Не трогать без подтверждения: infra/prod/**, секреты и prod‑конфиги.
MD

  write_template "conventions.md" <<'MD'
# conventions.md
- Kotlin/Java стиль: JetBrains/Google; KISS/YAGNI/MVP.
- Форматирование: Spotless/ktlint (если подключены).
- Коммиты/ветки управляются `config/conventions.json`.
- Юнит‑тесты обязательны; PR не должен ломать build.
MD

  write_template "workflow.md" <<'MD'
# workflow.md
1) PRD → `/feature-new <short> [TICKET]`
2) ADR → `/feature-adr <short>`
3) Tasks → `/feature-tasks <short>`
4) Реализация (правки → хуки: форматирование + выборочные тесты)
5) Документация → `/docs-generate`
6) Коммиты → `/commit "msg"`; ветки → `/branch-new ...`
MD

  write_template "tasklist.md" <<'MD'
# tasklist.md
- [ ] PRD
- [ ] ADR
- [ ] UC1 + unit
- [ ] Документация
MD
}

generate_templates() {
  write_template "docs/prd.template.md" <<'MD'
# PRD — $SHORT
## Why/Idea
## Audience
## User stories
## Success criteria
## Non-goals
## Constraints/Risks
## Tracking: <TICKET>
MD

  write_template "docs/adr.template.md" <<'MD'
# ADR: $TITLE
Дата: $TODAY
## Контекст
## Альтернативы (trade-off)
## Решение
## Последствия (+/−, миграции)
MD
}

generate_claude_settings() {
  write_template ".claude/settings.json" <<'JSON'
{
  "model": "sonnet",
  "outputStyle": "Explanatory",
  "permissions": {
    "allow": [
      "Read","Write","Edit","Grep","Glob",
      "Bash(git status:*)","Bash(git diff:*)","Bash(git rev-parse:*)",
      "Bash(git checkout:*)",
      "Bash(./gradlew:*)","Bash(gradle:*)",
      "Bash(.claude/hooks/*:*)",
      "Bash(python3 scripts/*:*)"
    ],
    "ask": [
      "Bash(git add:*)","Bash(git commit:*)","Bash(git push:*)"
    ],
    "deny": [
      "Bash(curl:*)",
      "Read(./.env)","Read(./.env.*)","Read(./secrets/**)",
      "Write(./infra/prod/**)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "Write|Edit",
        "hooks": [ { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/protect-prod.sh", "timeout": 5 } ] }
    ],
    "PostToolUse": [
      { "matcher": "Write|Edit",
        "hooks": [ { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/format-and-test.sh", "timeout": 900 } ] }
    ]
  }
}
JSON

  write_template ".claude/hooks/protect-prod.sh" <<'BASH'
#!/usr/bin/env bash
set -euo pipefail
payload="$(cat)"
file_path="$(printf '%s' "$payload" | python3 - <<'PY'
import json,sys
try:
  data=json.load(sys.stdin)
  print(data.get("tool_input",{}).get("file_path",""))
except: print("")
PY
)"
deny_re='(^|/)(infra/prod|k8s/prod|helm/prod)/|src/main/resources/application-prod'
if [[ -n "$file_path" && "$file_path" =~ $deny_re ]]; then
  echo "Blocked unsafe edit: $file_path" 1>&2; exit 2
fi
exit 0
BASH
  set_executable ".claude/hooks/protect-prod.sh"

  write_template ".claude/gradle/init-print-projects.gradle" <<'GRADLE'
gradle.settingsEvaluated {
  gradle.rootProject {
    tasks.register("ccPrintProjectDirs") {
      doLast { allprojects { println("${it.path}=${it.projectDir.absolutePath}") } }
    }
  }
}
GRADLE
}

generate_hook_format_test() {
  write_template ".claude/hooks/format-and-test.sh" <<'BASH'
#!/usr/bin/env bash
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}"

have(){ command -v "$1" >/dev/null 2>&1; }
gq(){ if [[ -x ./gradlew ]]; then ./gradlew -q "$@" || return $?; elif have gradle; then gradle -q "$@" || return $?; else return 127; fi }
gr(){ if [[ -x ./gradlew ]]; then ./gradlew "$@" || return $?; elif have gradle; then gradle "$@" || return $?; else return 127; fi }

# best-effort format
gq spotlessApply || true
if have ktlint; then ktlint -F '**/*.kt' || true; fi

mkdir -p .claude/cache .claude/gradle
MAP=".claude/cache/project-dirs.txt"
SET=""
[[ -f settings.gradle.kts ]] && SET="settings.gradle.kts"
[[ -z "$SET" && -f settings.gradle ]] && SET="settings.gradle"
if [[ ! -f "$MAP" || ( -n "$SET" && "$MAP" -ot "$SET" ) ]]; then
  if gq -I .claude/gradle/init-print-projects.gradle ccPrintProjectDirs > "$MAP.tmp" 2>/dev/null; then
    mv "$MAP.tmp" "$MAP"
  else
    : > "$MAP"
  fi
fi

declare -A P2D=() D2P=()
while IFS='=' read -r p abs; do
  [[ -z "$p" || -z "$abs" ]] && continue
  rel="${abs/#$PWD\//}"
  P2D["$p"]="$rel"; D2P["$rel"]="$p"
done < "$MAP"

# changed files
CHANGED=()
if git rev-parse --verify HEAD >/dev/null 2>&1; then
  while IFS= read -r f; do [[ -n "$f" ]] && CHANGED+=("$f"); done < <(git diff --name-only HEAD)
else
  while IFS= read -r f; do [[ -n "$f" ]] && CHANGED+=("$f"); done < <(git ls-files)
fi
while IFS= read -r f; do [[ -n "$f" ]] && CHANGED+=("$f"); done < <(git ls-files --others --exclude-standard)

is_rel(){ f="$1"; [[ "$f" == *"/src/"* || "$f" =~ (^|/)build.gradle(\.kts)?$ || "$f" == "settings.gradle" || "$f" == "settings.gradle.kts" || "$f" == "gradle/libs.versions.toml" ]]; }

REL=()
for f in "${CHANGED[@]:-}"; do is_rel "$f" && REL+=("$f"); done
[[ ${#REL[@]:-0} -eq 0 ]] && exit 0

declare -A AFX=()
for f in "${REL[@]}"; do
  best=""; bestlen=0
  for p in "${!P2D[@]}"; do
    d="${P2D[$p]}"; [[ -z "$d" ]] && continue
    if [[ "$f" == "$d"* ]]; then
      l=${#d}; (( l > bestlen )) && { best="$p"; bestlen=$l; }
    fi
  done
  if [[ -z "$best" ]]; then
    d="$f"
    while [[ "$d" != "." && "$d" != "/" ]]; do
      d="$(dirname "$d")"
      if [[ -f "$d/build.gradle" || -f "$d/build.gradle.kts" ]]; then
        [[ -n "${D2P[$d]:-}" ]] && best="${D2P[$d]}"; break
      fi
    done
  fi
  [[ -n "$best" ]] && AFX["$best"]=1
done

TASKS=()
for p in "${!AFX[@]}"; do [[ "$p" != :* ]] && p=":$p"; TASKS+=("${p}:clean" "${p}:test"); done
if [[ ${#TASKS[@]} -eq 0 ]]; then gr test || true; exit 0; fi

echo "[claude] affected modules: ${!AFX[@]}"
if ! gr --continue "${TASKS[@]}"; then
  for p in "${!AFX[@]}"; do
    [[ "$p" != :* ]] && p=":$p"
    gr "${p}:clean" "${p}:test" \
      || gr "${p}:clean" "${p}:jvmTest" \
      || gr "${p}:clean" "${p}:testDebugUnitTest" \
      || true
  done
fi
BASH
  set_executable ".claude/hooks/format-and-test.sh"
}

generate_agents() {
  write_template ".claude/agents/feature-architect.md" <<'MD'
---
name: feature-architect
description: "Архитектор фич: ADR по PRD (KISS/YAGNI/MVP, trade-off)."
tools: Read,Edit,Grep,Glob,Bash
model: sonnet
---
Сгенерируй ADR на основе PRD: контекст, альтернативы, решение, последствия.
MD

  write_template ".claude/agents/test-runner.md" <<'MD'
---
name: test-runner
description: "Запускает тесты по затронутым модулям, предлагает фиксы."
tools: Read,Edit,Bash,Grep,Glob
model: sonnet
---
После правок вызывай .claude/hooks/format-and-test.sh; при падениях — дай краткий отчёт и предложи исправления.
MD
}

generate_commands() {
  write_template ".claude/commands/feature-new.md" <<'MD'
---
description: "Создать PRD и стартовые артефакты"
argument-hint: "<short> [TICKET]"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Используй @docs/prd.template.md, @conventions.md, @workflow.md.
Создай `docs/prd/$1.prd.md` (idea, audience, stories, success, non-goals).
Если передан TICKET ($2) — добавь в Tracking.
MD

  write_template ".claude/commands/feature-adr.md" <<'MD'
---
description: "Сформировать ADR из PRD"
argument-hint: "<short>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Вызови саб-агента **feature-architect** и создай `docs/adr/$1.md` на основе @docs/prd/$1.prd.md.
MD

  write_template ".claude/commands/feature-tasks.md" <<'MD'
---
description: "Обновить tasklist.md под фичу"
argument-hint: "<short>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Проанализируй @docs/prd/$1.prd.md и @docs/adr/$1.md. Обнови @tasklist.md (чекбоксы, статусы, метрики).
MD

  write_template ".claude/commands/docs-generate.md" <<'MD'
---
description: "Сгенерировать docs/intro.md и обновить README"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Создай/обнови `docs/intro.md` (mermaid-диаграммы, сценарии), проставь ссылки на PRD/ADR/tasklist в README.
MD

  write_template ".claude/commands/test-changed.md" <<'MD'
---
description: "Прогнать тесты по затронутым Gradle-модулям"
allowed-tools: Bash("$CLAUDE_PROJECT_DIR/.claude/hooks/format-and-test.sh:*"),Read
---
!`"$CLAUDE_PROJECT_DIR/.claude/hooks/format-and-test.sh"`
MD

  write_template ".claude/commands/conventions-sync.md" <<'MD'
---
description: "Синхронизировать conventions.md с Gradle конфигами"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Просмотри build.gradle*, settings.gradle*, gradle/libs.versions.toml; обнови @conventions.md разделы стиль/линт/тесты.
MD

  write_template ".claude/commands/branch-new.md" <<'MD'
---
description: "Создать ветку по пресету (feature/..., feat/..., mixed)"
argument-hint: "<type> <args>"
allowed-tools: Bash(git checkout:*),Bash(python3 scripts/branch_new.py:*),Read
---
!`python3 scripts/branch_new.py $ARGUMENTS | { read n; git checkout -b "$n" || git checkout "$n"; echo "branch: $n"; }`
MD

  write_template ".claude/commands/commit.md" <<'MD'
---
description: "Собрать коммит согласно config/conventions.json"
argument-hint: "<summary>"
allowed-tools: Bash(git add:*),Bash(git commit:*),Bash(python3 scripts/commit_msg.py:*),Read
---
!`msg="$(python3 scripts/commit_msg.py --summary "$ARGUMENTS")"; git add -A && git commit -m "$msg" && echo "$msg"`
MD

  write_template ".claude/commands/commit-validate.md" <<'MD'
---
description: "Проверить сообщение коммита по текущему пресету"
argument-hint: "<message>"
allowed-tools: Bash(python3 scripts/commit_msg.py:*),Read
---
!`python3 scripts/commit_msg.py --validate "$ARGUMENTS" && echo "OK"`
MD

  write_template ".claude/commands/conventions-set.md" <<'MD'
---
description: "Переключить режим: ticket-prefix | conventional | mixed"
argument-hint: "<commit-mode>"
allowed-tools: Bash(python3 scripts/conventions_set.py:*),Read,Edit,Write
---
!`python3 scripts/conventions_set.py --commit-mode "$ARGUMENTS" && echo "commit.mode set to $ARGUMENTS"`
MD
}

generate_config_and_scripts() {
  write_template "config/conventions.json" <<'JSON'
{
  "commit": {
    "mode": "__COMMIT_MODE__",
    "ticket": {
      "branch_pattern": "^feature/(?P<ticket>[A-Z]+-\\d+)(?:/.*)?$",
      "format": "{ticket}: {summary}"
    },
    "conventional": {
      "types": ["feat","fix","chore","docs","test","refactor","perf","build","ci","revert"],
      "branch_pattern": "^(?P<type>feat|fix|chore|docs|test|refactor|perf|build|ci|revert)/(?P<scope>[\\w\\-]+)$",
      "format": "{type}({scope}): {summary}"
    },
    "mixed": {
      "branch_pattern": "^feature/(?P<ticket>[A-Z]+-\\d+)/(?:)(?P<type>feat|fix|chore|docs|refactor|perf)/(?P<scope>[\\w\\-]+)$",
      "format": "{ticket} {type}({scope}): {summary}"
    }
  },
  "branch": {
    "allowed": [
      "^feature/[A-Z]+-\\d+(?:/.*)?$",
      "^(feat|fix|chore|docs|test|refactor|perf|build|ci|revert)/[\\w\\-]+$",
      "^hotfix/[A-Z]+-\\d+$",
      "^release/v\\d+\\.\\d+\\.\\d+$"
    ],
    "mainline": "main"
  }
}
JSON

  write_template "scripts/commit_msg.py" <<'PY'
#!/usr/bin/env python3
import json,re,subprocess,sys,argparse
CFG='config/conventions.json'
def load_cfg():
  with open(CFG,'r',encoding='utf-8') as f: return json.load(f)
def git_branch():
  try: return subprocess.check_output(["git","rev-parse","--abbrev-ref","HEAD"]).decode().strip()
  except: return ""
def validate_msg(mode,msg):
  pats={
    "ticket-prefix": r"^[A-Z]+-\\d+: .+",
    "conventional":  r"^(feat|fix|chore|docs|test|refactor|perf|build|ci|revert)(\\([\\w\\-\\*]+\\))?: .+",
    "mixed":         r"^[A-Z]+-\\d+ (feat|fix|chore|docs|refactor|perf)(\\([\\w\\-\\*]+\\))?: .+"
  }
  return re.match(pats.get(mode,"^.+$"), msg or "") is not None
def build(cfg,mode,branch,summary,typ=None):
  c=cfg["commit"]
  if mode=="ticket-prefix":
    m=re.match(c["ticket"]["branch_pattern"], branch or "") or sys.exit(f"[commit] Branch '{branch}' not ticket-prefix")
    ticket=m.group("ticket");  return c["ticket"]["format"].format(ticket=ticket,summary=summary)
  if mode=="conventional":
    m=re.match(c["conventional"]["branch_pattern"], branch or "") or sys.exit("[commit] Branch must be 'feat/scope' etc")
    typ=(typ or m.group("type")); scope=m.group("scope"); return c["conventional"]["format"].format(type=typ,scope=scope,summary=summary)
  if mode=="mixed":
    m=re.match(c["mixed"]["branch_pattern"], branch or "") or sys.exit("[commit] Branch must be 'feature/TICKET/{type}/{scope}'")
    ticket=m.group("ticket"); typ=(typ or m.group("type")); scope=m.group("scope"); return c["mixed"]["format"].format(ticket=ticket,type=typ,scope=scope,summary=summary)
  sys.exit(f"[commit] Unknown mode: {mode}")
def main():
  ap=argparse.ArgumentParser()
  ap.add_argument("--summary", required=False, default="")
  ap.add_argument("--type")
  ap.add_argument("--branch")
  ap.add_argument("--mode")
  ap.add_argument("--validate")
  a=ap.parse_args()
  cfg=load_cfg(); mode=a.mode or cfg["commit"]["mode"]
  if a.validate is not None:
    print("OK" if validate_msg(mode, a.validate.strip()) else "FAIL"); sys.exit(0)
  if not a.summary.strip(): sys.exit("[commit] require --summary")
  branch=a.branch or git_branch()
  print(build(cfg,mode,branch,a.summary.strip(),a.type))
if __name__=="__main__": main()
PY
  set_executable "scripts/commit_msg.py"

  write_template "scripts/branch_new.py" <<'PY'
#!/usr/bin/env python3
import re,sys,argparse
ap=argparse.ArgumentParser()
ap.add_argument("type"); ap.add_argument("arg1", nargs="?"); ap.add_argument("arg2", nargs="?"); ap.add_argument("arg3", nargs="?")
a=ap.parse_args()
t=a.type; name=""
if t=="feature":
  if not a.arg1 or not re.match(r"^[A-Z]+-\\d+$", a.arg1): sys.exit("Use: feature <TICKET>")
  name=f"feature/{a.arg1}"
elif t in ("feat","fix","chore","docs","test","refactor","perf","build","ci","revert"):
  if not a.arg1: sys.exit(f"Use: {t} <scope>")
  name=f"{t}/{a.arg1}"
elif t=="hotfix":
  if not a.arg1 or not re.match(r"^[A-Z]+-\\d+$", a.arg1): sys.exit("Use: hotfix <TICKET>")
  name=f"hotfix/{a.arg1}"
elif t=="mixed":
  if not (a.arg1 and a.arg2 and a.arg3): sys.exit("Use: mixed <TICKET> <type> <scope>")
  if not re.match(r"^[A-Z]+-\\d+$", a.arg1): sys.exit("TICKET must be A-Z+-digits")
  if a.arg2 not in ("feat","fix","chore","docs","refactor","perf"): sys.exit("type must be feat|fix|chore|docs|refactor|perf")
  name=f"feature/{a.arg1}/{a.arg2}/{a.arg3}"
else: sys.exit("Unknown branch type")
print(name)
PY
  set_executable "scripts/branch_new.py"

  write_template "scripts/conventions_set.py" <<'PY'
#!/usr/bin/env python3
import json,sys,argparse
CFG='config/conventions.json'
ap=argparse.ArgumentParser(); ap.add_argument("--commit-mode", choices=["ticket-prefix","conventional","mixed"], required=True)
a=ap.parse_args()
with open(CFG,'r+',encoding='utf-8') as f:
  cfg=json.load(f); cfg.setdefault("commit",{})["mode"]=a.commit_mode
  f.seek(0); json.dump(cfg,f,indent=2,ensure_ascii=False); f.truncate()
print(a.commit_mode)
PY
  set_executable "scripts/conventions_set.py"
}

generate_ci_workflow() {
  if [[ "$ENABLE_CI" -eq 1 ]]; then
    write_template ".github/workflows/gradle.yml" <<'YML'
name: Gradle (selective modules)
on: { workflow_dispatch: {} }  # enable pull_request later if needed
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-java@v4
        with: { distribution: 'temurin', java-version: '21' }
      - name: Cache Gradle
        uses: actions/cache@v4
        with:
          path: |
            ~/.gradle/caches
            ~/.gradle/wrapper
          key: gradle-${{ runner.os }}-${{ hashFiles('**/*.gradle*','**/gradle-wrapper.properties','gradle/libs.versions.toml') }}
          restore-keys: gradle-${{ runner.os }}-
      - name: Run selective tests
        run: bash .claude/hooks/format-and-test.sh
YML
  fi
}

final_message() {
  log_info "Claude Code workflow is ready."
  cat <<'EOF'
Open the project in Claude Code and try:
  /branch-new feature STORE-123
  /feature-new checkout-discounts STORE-123
  /feature-adr checkout-discounts
  /feature-tasks checkout-discounts
  /commit "UC1: implement rule engine"
  /test-changed
EOF
  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "Dry run completed. No files were written."
  fi
}

main() {
  parse_args "$@"
  check_dependencies
  generate_directories
  generate_core_docs
  generate_templates
  generate_claude_settings
  generate_hook_format_test
  generate_agents
  generate_commands
  generate_config_and_scripts
  replace_commit_mode
  generate_ci_workflow
  final_message
}

main "$@"
