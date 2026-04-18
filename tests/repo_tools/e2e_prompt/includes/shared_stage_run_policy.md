## 5) Политика запуска, ожидания и зависаний

### 5.0 Обязательный launcher (для каждого stage-run)

- Для всех stage-run обязателен canonical launcher `python3 $PLUGIN_DIR/tests/repo_tools/aidd_stage_launcher.py ...`; ad-hoc shell wrappers/inline-launchers запрещены.
- Для stage-run с budget обязательно передавать `--budget-seconds <N>` в canonical launcher; budget kill должен фиксироваться через `*_termination_attribution.txt` с `killed_flag=1` и `watchdog_marker=1`.
- Для `stream-json` режимов используй шаблон:
  - `cd "$PROJECT_DIR"`
  - `claude -p "<stage command>" $CLAUDE_ARGS $CLAUDE_STREAM_FLAGS $CLAUDE_PLUGIN_FLAGS`
- Для `text` режимов используй шаблон:
  - `cd "$PROJECT_DIR"`
  - `claude -p "<stage command>" $CLAUDE_ARGS $CLAUDE_PLUGIN_FLAGS`
- Shell-safe launch: передавать каждый флаг отдельным аргументом, без склейки в одну строку/токен.
- Перед первым stage-run (и перед retry после `cwd_wrong`) выполнить shell-safe topology precheck:
  - `[ "$(cd "$PROJECT_DIR" && pwd -P)" != "$(cd "$PLUGIN_DIR" && pwd -P)" ] || { echo "ENV_MISCONFIG(cwd_wrong): PROJECT_DIR must differ from PLUGIN_DIR"; exit 12; }`
- Перед каждым stage-run делать disk-preflight:
  - `df -Pk "$PROJECT_DIR"` и проверка свободного места (`>= 1073741824` bytes);
  - если свободного места меньше, классифицировать как `ENV_MISCONFIG(no_space_left_on_device)` и не стартовать stage-run.
- Любой запуск stage-команды должен писать `stdout+stderr` в `AUDIT_DIR/<step>_run<N>.log`.
- Для каждого stage-run сохраняй `head`, `tail`, heartbeat и `AUDIT_DIR/<step>_stream_paths_run<N>.txt`.
- Для stream-path extraction запрещён глобальный regex-scan по всему run-log; использовать только `system/init` JSON/control-header sources и игнорировать `tool_result`/artifact text fragments.
- Если primary extraction дал только `stream_path_invalid`/`stream_path_missing` или пустой валидный набор, обязателен fallback discovery.

### 5.1 Проверка плагина в каждом stream-json run

- В `init`-событии лога должны присутствовать:
  - `plugins` содержит `feature-dev-aidd`.
  - `slash_commands` содержит `feature-dev-aidd:status` и stage-команду текущего шага.
- Если в `init` нет `feature-dev-aidd` или `slash_commands` без `feature-dev-aidd:*`:
  - классифицируй как `ENV_BLOCKER(plugin_not_loaded)`;
  - шаг = `NOT VERIFIED (env blocker)`;
  - останови аудит.

### 5.2 Общие правила ожидания

- Silent stdout допустим.
- Не прерывай команды раньше бюджетов.
- Heartbeat раз в ~30s.
- Для каждого stage-run проверяй рост `main log`, `stream_jsonl`, `stream log` и `stream jsonl`.
- Если используешь text-режим, live-tail всё равно обязателен.

### 5.3 Буферизация/зависания

- Если лог = `0 bytes` дольше 120 секунд:
  - сначала классифицируй как `prompt-exec buffering/quoting risk`;
  - сделай один перезапуск той же команды в `stream-json` режиме.
- Если `main log = 0 bytes`, но stream-файлы растут, продолжать run как `active_stream`.
- Если в stage-логе нет новых строк >20 минут:
  - сначала выполни fallback discovery и пересчитай liveness;
  - если stream растёт, это `active_stream`;
  - если не растут и `main log`, и stream — это `silent stall`.
- Если `main log` и/или stream растут, но top-level `result` не появляется, до budget **не** делать `kill`; помечать как `WARN(prompt-exec no_convergence_yet)`.
- Для `silent stall` делай ровно один debug-retry с `ANTHROPIC_LOG=debug`.
- При завершении процесса с `exit_code=143` обязателен `AUDIT_DIR/<step>_termination_attribution.txt`.

### 5.4 Порядок классификации инцидентов (строгий)

- Сначала `ENV_BLOCKER`.
- Затем `ENV_MISCONFIG/external_terminate`.
- Затем `prompt-exec issue` (включая `project_contract_missing|tests_cwd_mismatch` как primary blockers; `no_top_level_result` в таких кейсах считать secondary symptom; `seed_scope_cascade_detected|tests_env_dependency_missing` — terminal в `strict_shadow`, а при `CLASSIFICATION_PROFILE=soft_default` для `06_implement` публикуются как `WARN` c продолжением `7/8`).
- Отдельно `contract mismatch`.
- Только потом `flow bug`.

### 5.5 Фильтрация WARN/DRIFT сигналов

- Stage-level классификацию делай по текущему stage-return, `init` и top-level result.
- `WARN/Q*/AIDD:ANSWERS/Question` внутри вложенных артефактов не считать trigger-ом инцидента.
- `blocking_findings` внутри review/report артефактов не считать trigger-ом сам по себе.
- Упоминание internal subagent внутри успешного `tasks-new` не является drift.
- Legacy aliases как primary next action фиксируй как `WARN(prompt_flow_drift_legacy_handoff_alias)`.
- `WARN(tasklist_hygiene)` выставлять только по command-полям секции `AIDD:TEST_EXECUTION`.
