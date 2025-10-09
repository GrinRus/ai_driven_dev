#!/usr/bin/env bash
set -euo pipefail

# format-and-test.sh
# ------------------
# Универсальный hook: запускает автоформатирование и тесты согласно
# конфигурации в .claude/settings.json → automation.format/tests.
# Переменные окружения:
#   SKIP_FORMAT=1      — пропустить форматирование.
#   FORMAT_ONLY=1      — выполнить только форматирование и завершиться.
#   TEST_SCOPE=":app:test,:lib:test" — явный список задач Gradle.
#   TEST_CHANGED_ONLY=0 — принудительно выполнить полный набор тестов.
#   STRICT_TESTS=0/1    — контролирует поведение при падении тестов
#                         (значение по умолчанию берётся из конфигурации).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CONFIG_FILE="${ROOT_DIR}/.claude/settings.json"

log() {
  printf '[format-and-test] %s\n' "$*" >&2
}

run_command() {
  local -a cmd=("$@")
  log "→ ${cmd[*]}"
  if ! "${cmd[@]}"; then
    return 1
  fi
}

collect_changed_files() {
  local -a files=()
  if git rev-parse --verify HEAD >/dev/null 2>&1; then
    while IFS= read -r line; do
      [[ -n "$line" ]] && files+=("$line")
    done < <(git diff --name-only HEAD)
  fi
  while IFS= read -r line; do
    [[ -n "$line" ]] && files+=("$line")
  done < <(git ls-files --others --exclude-standard)

  if ((${#files[@]})); then
    printf '%s\n' "${files[@]}" | sort -u
  fi
}

if [[ ! -f "$CONFIG_FILE" ]]; then
  log "Конфигурация ${CONFIG_FILE} не найдена — шаги пропущены."
  exit 0
fi

eval "$(
python3 - "$CONFIG_FILE" <<'PY'
import json
import shlex
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
data = json.loads(config_path.read_text(encoding="utf-8"))
automation = data.get("automation", {})

fmt_cfg = automation.get("format", {})
commands = fmt_cfg.get("commands", [])
print(f"FORMAT_COMMAND_COUNT={len(commands)}")
for idx, cmd in enumerate(commands):
    joined = " ".join(shlex.quote(part) for part in cmd)
    print(f"FORMAT_COMMAND_{idx}=({joined})")

tests_cfg = automation.get("tests", {})
print(f"TEST_RUNNER={shlex.quote(tests_cfg.get('runner', './gradlew'))}")

default_tasks = tests_cfg.get("defaultTasks", [":test"])
print(f"TEST_DEFAULT_COUNT={len(default_tasks)}")
for idx, task in enumerate(default_tasks):
    print(f"TEST_DEFAULT_{idx}={shlex.quote(task)}")

fallback_tasks = tests_cfg.get("fallbackTasks", [":jvmTest", ":testDebugUnitTest"])
print(f"TEST_FALLBACK_COUNT={len(fallback_tasks)}")
for idx, task in enumerate(fallback_tasks):
    print(f"TEST_FALLBACK_{idx}={shlex.quote(task)}")

changed_only = tests_cfg.get("changedOnly", True)
print(f"CHANGED_ONLY_DEFAULT={'1' if changed_only else '0'}")

strict_default = tests_cfg.get("strictDefault", 1)
print(f"STRICT_TESTS_DEFAULT={'1' if strict_default else '0'}")

module_matrix = tests_cfg.get("moduleMatrix", [])
print(f"MODULE_MATRIX_COUNT={len(module_matrix)}")
for idx, item in enumerate(module_matrix):
    match = shlex.quote(item.get("match", ""))
    tasks = " ".join(shlex.quote(t) for t in item.get("tasks", []))
    print(f"MODULE_MATRIX_{idx}_MATCH={match}")
    print(f"MODULE_MATRIX_{idx}_TASKS=({tasks})")
PY
)"

# ---------- Format stage ----------
if [[ "${SKIP_FORMAT:-0}" == "1" ]]; then
  log "SKIP_FORMAT=1 — форматирование пропущено."
else
  if (( FORMAT_COMMAND_COUNT == 0 )); then
    log "Команды форматирования не настроены (automation.format.commands)."
  else
    for ((i = 0; i < FORMAT_COMMAND_COUNT; i++)); do
      eval "cmd=(\"\${FORMAT_COMMAND_${i}[@]}\")"
      if ! run_command "${cmd[@]}"; then
        log "Форматирование завершилось с ошибкой."
        exit 1
      fi
    done
  fi
fi

if [[ "${FORMAT_ONLY:-0}" == "1" ]]; then
  log "FORMAT_ONLY=1 — стадия тестов пропущена."
  exit 0
fi

# ---------- Test stage ----------
eval "TEST_RUNNER_CMD=(${TEST_RUNNER})"
strict_flag="${STRICT_TESTS:-$STRICT_TESTS_DEFAULT}"
changed_only_flag="${TEST_CHANGED_ONLY:-$CHANGED_ONLY_DEFAULT}"

declare -a test_tasks=()
declare -A seen_tasks=()

if [[ -n "${TEST_SCOPE:-}" ]]; then
  IFS=', ' read -r -a manual_tasks <<< "${TEST_SCOPE//,/ }"
  for task in "${manual_tasks[@]}"; do
    [[ -n "$task" && -z "${seen_tasks["$task"]:-}" ]] || continue
    seen_tasks["$task"]=1
    test_tasks+=("$task")
  done
else
  if [[ "$changed_only_flag" == "1" ]]; then
    mapfile -t changed_files < <(collect_changed_files || true)
    if ((${#changed_files[@]})); then
      mapfile -t module_tasks < <(
        python3 - "$CONFIG_FILE" "${changed_files[@]}" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
changed = sys.argv[2:]
data = json.loads(config_path.read_text(encoding="utf-8"))
matrix = data.get("automation", {}).get("tests", {}).get("moduleMatrix", [])

tasks = []
for item in matrix:
    match = item.get("match")
    if not match:
        continue
    if any(path.startswith(match) for path in changed):
        for task in item.get("tasks", []):
            if task not in tasks:
                tasks.append(task)

print("\n".join(tasks))
PY
      )
      for task in "${module_tasks[@]}"; do
        [[ -n "$task" && -z "${seen_tasks["$task"]:-}" ]] || continue
        seen_tasks["$task"]=1
        test_tasks+=("$task")
      done
    fi
  fi

  if ((${#test_tasks[@]} == 0)); then
    for ((i = 0; i < TEST_DEFAULT_COUNT; i++)); do
      eval "task=\${TEST_DEFAULT_${i}}"
      [[ -n "$task" && -z "${seen_tasks["$task"]:-}" ]] || continue
      seen_tasks["$task"]=1
      test_tasks+=("$task")
    done
  fi

  if ((${#test_tasks[@]} == 0)); then
    for ((i = 0; i < TEST_FALLBACK_COUNT; i++)); do
      eval "task=\${TEST_FALLBACK_${i}}"
      [[ -n "$task" && -z "${seen_tasks["$task"]:-}" ]] || continue
      seen_tasks["$task"]=1
      test_tasks+=("$task")
    done
  fi
fi

if ((${#test_tasks[@]} == 0)); then
  log "Нет задач для запуска тестов — проверка пропущена."
  exit 0
fi

command=( "${TEST_RUNNER_CMD[@]}" "${test_tasks[@]}" )
log "Запуск тестов: ${command[*]}"
if run_command "${command[@]}"; then
  log "Тесты завершились успешно."
else
  if [[ "$strict_flag" == "1" ]]; then
    log "Тесты завершились с ошибкой (STRICT_TESTS=1)."
    exit 1
  else
    log "Тесты завершились с ошибкой, но STRICT_TESTS != 1 — продолжаем."
  fi
fi
