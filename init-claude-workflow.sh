#!/usr/bin/env bash
#
# init-claude-workflow.sh
# One-shot initializer for Claude Code Java/Kotlin workflow (monorepo-friendly).
# Installs .claude commands/agents/hooks, commit/branch conventions,
# and Gradle selective-tests support.
#
# Usage:
#   bash init-claude-workflow.sh [--commit-mode MODE] [--enable-ci] [--force]
#
#     --commit-mode   ticket-prefix | conventional | mixed   (default: ticket-prefix)
#     --enable-ci     add a GitHub Actions workflow template (manual trigger by default)
#     --force         overwrite existing files
#
# After running:
#   - Open the repo in Claude Code and try:
#       /branch-new feature STORE-123
#       /feature-new checkout-discounts STORE-123
#       /feature-adr checkout-discounts
#       /feature-tasks checkout-discounts
#       /commit "UC1: implement rule engine"
#       /test-changed
#

set -euo pipefail

COMMIT_MODE="ticket-prefix"   # ticket-prefix | conventional | mixed
ENABLE_CI=0
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --commit-mode) COMMIT_MODE="${2:-ticket-prefix}"; shift 2;;
    --enable-ci)   ENABLE_CI=1; shift;;
    --force)       FORCE=1; shift;;
    -h|--help)
      sed -n '1,40p' "$0"; exit 0;;
    *) echo "Unknown arg: $1"; exit 2;;
  esac
done

write() {
  # write <path> <<'EOF' ... EOF
  local path="$1"
  shift || true
  if [[ -e "$path" && "$FORCE" -ne 1 ]]; then
    echo "⚠️  Skip (exists): $path  — use --force to overwrite"
    # shellcheck disable=SC2002
    cat >/dev/null  # drain heredoc that follows
    return 0
  fi
  mkdir -p "$(dirname "$path")"
  cat > "$path"
  echo "✅ Wrote: $path"
}

say() { printf "\n\033[1m%s\033[0m\n" "$*"; }

say "→ Initializing Claude Code workflow (commit-mode=$COMMIT_MODE, ci=$ENABLE_CI, force=$FORCE)"

mkdir -p .claude/{commands,agents,hooks,gradle,cache} config scripts .github/ISSUE_TEMPLATE docs/{prd,adr}

# ---------------- .gitignore ----------------
write ".gitignore" <<'TXT'
# build
.gradle/
build/
out/
**/build/
# IDE
.idea/
.vscode/
# OS
.DS_Store
# Claude Code cache
.claude/cache/
TXT

# ---------------- LICENSE ----------------
write "LICENSE" <<'TXT'
MIT License
Copyright (c) 2025
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
TXT

# ---------------- README ----------------
write "README.md" <<'MD'
# Claude Code Workflow — Java/Kotlin Monorepo

Готовый каркас для Claude Code:
- Слэш‑команды по воркфлоу (PRD → ADR → Tasks → Docs)
- Монорепо Gradle: выборочные тесты по изменённым модулям
- Настраиваемые ветки/коммиты (ticket-prefix | conventional | mixed)
- Хуки безопасности и автоформатирование

## Установка
Сохраните `init-claude-workflow.sh` в корне и выполните:
```bash
bash init-claude-workflow.sh --commit-mode ticket-prefix --enable-ci
```

## Быстрый старт
Откройте репозиторий в Claude Code и используйте команды:
```
/branch-new feature STORE-123
/feature-new checkout-discounts STORE-123
/feature-adr checkout-discounts
/feature-tasks checkout-discounts
/commit "implement rule engine"
/test-changed
```

## Монорепо Gradle — выборочные тесты
Хук определяет изменённые модули по `git diff` и запускает `:mod:clean :mod:test` (fallback `:jvmTest`/Android).

## Безопасность
PreToolUse‑хук блокирует правки в `infra/prod/**`, prod‑конфиги и секреты. PostToolUse форматирует и запускает выборочные тесты.
MD

# ---------------- CONTRIBUTING / CODE_OF_CONDUCT ----------------
write "CONTRIBUTING.md" <<'MD'
# Contributing
- Ветки: `feature/<TICKET>` или `<type>/<scope>` (feat, fix, chore, docs...).
- Коммиты через `/commit` (режимы см. config/conventions.json).
- Юнит‑тесты обязательны. Запускайте `/test-changed`.
MD

write "CODE_OF_CONDUCT.md" <<'MD'
# Code of Conduct
Будьте уважительны к коллегам и сообществу.
MD

# ---------------- Issue/PR templates ----------------
write ".github/PULL_REQUEST_TEMPLATE.md" <<'MD'
## Что сделано
-

## Как проверить
-

## Ссылки
- PRD/ADR/Tasks: (ссылки)
- Тикеты: (например STORE-123)
MD

write ".github/ISSUE_TEMPLATE/bug_report.md" <<'MD'
---
name: Bug report
about: Сообщить об ошибке
---
**Что произошло**
**Шаги для воспроизведения**
**Ожидаемое поведение**
**Логи/скриншоты**
MD

write ".github/ISSUE_TEMPLATE/feature_request.md" <<'MD'
---
name: Feature request
about: Запрос новой фичи
---
**Проблема/возможность**
**Предлагаемое решение**
**Альтернативы**
**Контекст**
MD

# ---------------- Project memory & workflow ----------------
write "CLAUDE.md" <<'MD'
# CLAUDE.md
Стек: Java/Kotlin (Gradle монорепо).
Ветки: feature/<TICKET> | feat/<scope> | mixed (см. config/conventions.json).
Коммиты: ticket-prefix | conventional | mixed.
Не трогать без подтверждения: infra/prod/**, секреты и prod‑конфиги.
MD

write "conventions.md" <<'MD'
# conventions.md
- Kotlin/Java стиль: JetBrains/Google; KISS/YAGNI/MVP.
- Форматирование: Spotless/ktlint (если подключены).
- Коммиты/ветки управляются `config/conventions.json`.
- Юнит‑тесты обязательны; PR не должен ломать build.
MD

write "workflow.md" <<'MD'
# workflow.md
1) PRD → `/feature-new <short> [TICKET]`
2) ADR → `/feature-adr <short>`
3) Tasks → `/feature-tasks <short>`
4) Реализация (агентные правки → хуки: форматирование + выборочные тесты)
5) Документация → `/docs-generate`
6) Коммиты → `/commit "msg"`; ветки → `/branch-new ...`
MD

write "tasklist.md" <<'MD'
# tasklist.md
- [ ] PRD
- [ ] ADR
- [ ] UC1 + unit
- [ ] Документация
MD

write "docs/prd.template.md" <<'MD'
# PRD — $SHORT
## Why/Idea
## Audience
## User stories
## Success criteria
## Non-goals
## Constraints/Risks
## Tracking: <TICKET>
MD

write "docs/adr.template.md" <<'MD'
# ADR: $TITLE
Дата: $TODAY
## Контекст
## Альтернативы (trade-off)
## Решение
## Последствия (+/−, миграции)
MD

# ---------------- Claude settings/hooks/agents ----------------
write ".claude/settings.json" <<'JSON'
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

write ".claude/hooks/protect-prod.sh" <<'BASH'
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
chmod +x .claude/hooks/protect-prod.sh

write ".claude/gradle/init-print-projects.gradle" <<'GRADLE'
gradle.settingsEvaluated {
  gradle.rootProject {
    tasks.register("ccPrintProjectDirs") {
      doLast { allprojects { println("${it.path}=${it.projectDir.absolutePath}") } }
    }
  }
}
GRADLE

write ".claude/hooks/format-and-test.sh" <<'BASH'
#!/usr/bin/env bash
set -euo pipefail
cd "${CLAUDE_PROJECT_DIR:-.}"

have(){ command -v "$1" >/dev/null 2>&1; }
gq(){ if [[ -x ./gradlew ]]; then ./gradlew -q "$@" || return $?; elif have gradle; then gradle -q "$@" || return $?; else return 127; fi }
gr(){ if [[ -x ./gradlew ]]; then ./gradlew "$@" || return $?; elif have gradle; then gradle "$@" || return $?; else return 127; fi }

# форматирование (best-effort)
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

# изменённые файлы
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
chmod +x .claude/hooks/format-and-test.sh

# agents
write ".claude/agents/feature-architect.md" <<'MD'
---
name: feature-architect
description: "Архитектор фич: ADR по PRD (KISS/YAGNI/MVP, trade-off)."
tools: Read,Edit,Grep,Glob,Bash
model: sonnet
---
Сгенерируй ADR на основе PRD: контекст, альтернативы, решение, последствия.
MD

write ".claude/agents/test-runner.md" <<'MD'
---
name: test-runner
description: "Запускает тесты по затронутым модулям, предлагает фиксы."
tools: Read,Edit,Bash,Grep,Glob
model: sonnet
---
После правок вызывай .claude/hooks/format-and-test.sh; при падениях — дай краткий отчёт и предложи исправления.
MD

# ---------------- Slash commands ----------------
write ".claude/commands/feature-new.md" <<'MD'
---
description: "Создать PRD и стартовые артефакты"
argument-hint: "<short> [TICKET]"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Используй @docs/prd.template.md, @conventions.md, @workflow.md.
Создай `docs/prd/$1.prd.md` (idea, audience, stories, success, non-goals).
Если передан TICKET ($2) — добавь в Tracking.
MD

write ".claude/commands/feature-adr.md" <<'MD'
---
description: "Сформировать ADR из PRD"
argument-hint: "<short>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Вызови саб-агента **feature-architect** и создай `docs/adr/$1.md` на основе @docs/prd/$1.prd.md.
MD

write ".claude/commands/feature-tasks.md" <<'MD'
---
description: "Обновить tasklist.md под фичу"
argument-hint: "<short>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Проанализируй @docs/prd/$1.prd.md и @docs/adr/$1.md. Обнови @tasklist.md (чекбоксы, статусы, метрики).
MD

write ".claude/commands/docs-generate.md" <<'MD'
---
description: "Сгенерировать docs/intro.md и обновить README"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Создай/обнови `docs/intro.md` (mermaid-диаграммы, сценарии), проставь ссылки на PRD/ADR/tasklist в README.
MD

write ".claude/commands/test-changed.md" <<'MD'
---
description: "Прогнать тесты по затронутым Gradle-модулям"
allowed-tools: Bash("$CLAUDE_PROJECT_DIR/.claude/hooks/format-and-test.sh:*"),Read
---
!`"$CLAUDE_PROJECT_DIR/.claude/hooks/format-and-test.sh"`
MD

write ".claude/commands/conventions-sync.md" <<'MD'
---
description: "Синхронизировать conventions.md с Gradle конфигами"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Просмотри build.gradle*, settings.gradle*, gradle/libs.versions.toml; обнови @conventions.md разделы стиль/линт/тесты.
MD

write ".claude/commands/branch-new.md" <<'MD'
---
description: "Создать ветку по пресету (feature/..., feat/..., mixed)"
argument-hint: "<type> <args>"
allowed-tools: Bash(git checkout:*),Bash(python3 scripts/branch_new.py:*),Read
---
!`python3 scripts/branch_new.py $ARGUMENTS | { read n; git checkout -b "$n" || git checkout "$n"; echo "branch: $n"; }`
MD

write ".claude/commands/commit.md" <<'MD'
---
description: "Собрать коммит согласно config/conventions.json"
argument-hint: "<summary>"
allowed-tools: Bash(git add:*),Bash(git commit:*),Bash(python3 scripts/commit_msg.py:*),Read
---
!`msg="$(python3 scripts/commit_msg.py --summary "$ARGUMENTS")"; git add -A && git commit -m "$msg" && echo "$msg"`
MD

write ".claude/commands/commit-validate.md" <<'MD'
---
description: "Проверить сообщение коммита по текущему пресету"
argument-hint: "<message>"
allowed-tools: Bash(python3 scripts/commit_msg.py:*),Read
---
!`python3 scripts/commit_msg.py --validate "$ARGUMENTS" && echo "OK"`
MD

write ".claude/commands/conventions-set.md" <<'MD'
---
description: "Переключить режим: ticket-prefix | conventional | mixed"
argument-hint: "<commit-mode>"
allowed-tools: Bash(python3 scripts/conventions_set.py:*),Read,Edit,Write
---
!`python3 scripts/conventions_set.py --commit-mode "$ARGUMENTS" && echo "commit.mode set to $ARGUMENTS"`
MD

# ---------------- Conventions JSON + scripts ----------------
write "config/conventions.json" <<'JSON'
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

# replace placeholder with selected mode
if command -v sed >/dev/null 2>&1; then
  sed -i.bak "s/__COMMIT_MODE__/${COMMIT_MODE}/g" "config/conventions.json" && rm -f "config/conventions.json.bak"
else
  # minimal fallback
  python3 - <<PY || true
import json
p='config/conventions.json'
cfg=json.load(open(p,'r',encoding='utf-8'))
cfg['commit']['mode']="${COMMIT_MODE}"
json.dump(cfg,open(p,'w',encoding='utf-8'),indent=2,ensure_ascii=False)
PY
fi

write "scripts/commit_msg.py" <<'PY'
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
    "ticket-prefix": r"^[A-Z]+-\d+: .+",
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
chmod +x scripts/commit_msg.py

write "scripts/branch_new.py" <<'PY'
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
chmod +x scripts/branch_new.py

write "scripts/conventions_set.py" <<'PY'
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
chmod +x scripts/conventions_set.py

# ---------------- CI (optional) ----------------
if [[ "$ENABLE_CI" -eq 1 ]]; then
  mkdir -p .github/workflows
  write ".github/workflows/gradle.yml" <<'YML'
name: Gradle (selective modules)
on: { workflow_dispatch: {} }  # включите pull_request позже
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

say "✔ All files emitted."
echo "Next:"
echo "  1) git add -A && git commit -m \"chore: bootstrap Claude Code workflow\""
echo "  2) Open in Claude Code and run: /branch-new feature STORE-123 → /feature-new → /feature-adr → /feature-tasks → /commit → /test-changed"
