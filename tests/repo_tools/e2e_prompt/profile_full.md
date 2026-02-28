Задача: **AIDD E2E Flow Audit (TST-001) + Ralph Loop Compliance + Full-flow task selection**  
База канона: **skill-first, python-only runtime, RLM-only research, no-fork stage orchestration**.

Роль: ты — один аудитор-агент. Проведи **полный** e2e прогон AIDD flow в одном репозитории и собери доказательства (логи/артефакты).  
**НЕ** исправляй проект и **НЕ** делай ручные правки `aidd/docs/**` или `aidd/reports/**` ради прохождения гейтов.
Используй только canonical stage-result contract (`aidd.stage_result.v1`); legacy stage-result schema не использовать как валидный runtime-path.

## 1) Канон и границы

- Stage content templates (SoT): `$PLUGIN_DIR/skills/*/templates/*`
- Workspace bootstrap source: `$PLUGIN_DIR/templates/aidd/**`
- Runtime workspace memory: `$PROJECT_DIR/aidd/**` (после `aidd-init`)
- Runtime API (canonical): `$PLUGIN_DIR/skills/*/runtime/*.py`
- Hooks/platform glue: `$PLUGIN_DIR/hooks/**`
- `tools/*.sh`: retired (не использовать)
- `tools/*.py`: только repo-only tooling/stubs (если есть)

## 2) Переменные

- `PROJECT_DIR=/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new`
- `PLUGIN_DIR=/Users/griogrii_riabov/grigorii_projects/ai_driven_dev`
- `CLAUDE_PLUGIN_ROOT=$PLUGIN_DIR`
- `TICKET=TST-001`
- `PROFILE=full|smoke` (default: `full`)
- `IDEA_NOTE=<формируется на шаге 3>`
- `LOOP_MODE=loop-run|loop-step` (default: `loop-run`)
- `BLOCKED_POLICY=strict|ralph` (default: `strict`)
- `RECOVERABLE_BLOCK_RETRIES=<int>` (default: `2`)
- `AIDD_HOOKS_MODE=fast|strict` (default: `fast`)
- `CLAUDE_ARGS=--dangerously-skip-permissions`
- `STAGE_OUTPUT_MODE=stream-json|text` (default: `stream-json`)
- `LOG_POLL_SECONDS=15` (default: `15`)
- `CLAUDE_STREAM_FLAGS=--verbose --output-format stream-json --include-partial-messages`
- `CLAUDE_PLUGIN_FLAGS=--plugin-dir "$PLUGIN_DIR"`
- `PLUGIN_HEALTHCHECK_CMD=/feature-dev-aidd:status $TICKET`
- `SEVERITY_PROFILE=conservative` (default: `conservative`)

## 3) Режимы

- `PROFILE=smoke`
  - Цель: быстрый health-check.
  - Выполняются шаги: `0,1,2,3,4,5,8,99`.
  - Шаги `6,7` помечаются `SKIPPED (profile=smoke)`.
- `PROFILE=full`
  - Цель: полный регрессионный аудит.
  - Выполняются шаги: `0,1,2,3,4,5,6,7,8,99`.

## 4) Ключевые правила

- R0: Первый запуск каждого stage (кроме `idea-new`) — только `ticket`.
- R0.1: Для `idea-new` используется только `ticket + IDEA_NOTE`; `slug_hint` генерируется внутри команды.
- R1: Для `full` разрешена ровно одна ручная пара `implement -> review` перед auto-loop.
- R2: Никаких ручных правок runtime-артефактов.
- R3: Не читать/не печатать секреты (`.env`, keys, tokens).
- R4: Только Python runtime surfaces (`skills/*/runtime/*.py`), без shell wrappers.
- R5: Stage-chain orchestration должны быть включены:
- R6: Все slash stage-команды запускать только из `PROJECT_DIR`.
- R6.1: Если `STAGE_OUTPUT_MODE=stream-json`, запускать `claude -p` только с `--verbose` (иначе CLI вернёт ошибку формата вывода).
- R6.2: Для `claude -p` stage-команд обязательно добавлять `--plugin-dir "$PLUGIN_DIR"`.
- R7: Перед первым stage-run обязателен plugin-load healthcheck (см. Шаг 1). Если плагин не загружен — это `ENV_BLOCKER` и аудит останавливается.
- R8: `Unknown skill: feature-dev-aidd:*` классифицируется как `ENV_BLOCKER(plugin_not_loaded)`; **не** классифицировать как `flow bug`.
- R9: Python fallback разрешён только после успешного plugin-load healthcheck и только для `blocked/hang/killed`. Python fallback запрещён как recovery для `Unknown skill`.
- R10: Ошибка `refusing to use plugin repository as workspace root` классифицируется как `ENV_MISCONFIG(cwd_wrong)`; исправь `cwd` на `PROJECT_DIR` и повтори ровно 1 раз.
- R11: Для шага 7 (Auto-loop через Python runtime) runner должен быть non-interactive:
  - перед запуском установить `AIDD_LOOP_RUNNER="claude --dangerously-skip-permissions"`;
  - если в stream `init` видно `permissionMode=default` и дальше идут `requires approval`, классифицировать как `ENV_MISCONFIG(loop_runner_permissions)` (не как flow bug).
- R12: В `stream-json` режиме liveness проверяется по двум источникам одновременно:
  - `AUDIT_DIR/<step>_run<N>.log` (main log),
  - stream-файлы (`*.stream.jsonl` и `*.stream.log`) из header/метаданных.
  Стагнация только main log при растущем stream не является `silent stall`.
- R12.1: Извлечение stream-путей обязано поддерживать абсолютные и относительные пути из `init/header/metadata`; относительные пути нормализуются относительно `PROJECT_DIR` и сохраняются в нормализованном виде.
- R12.2: Если stream-пути не извлеклись из main log/metadata, обязателен fallback discovery в `aidd/reports/loops/<ticket>/` (по `*.stream.jsonl` и `*.stream.log`) с выбором самых свежих файлов; этот fallback фиксируется в `AUDIT_DIR/<step>_stream_paths_run<N>.txt`.
- R12.3: После нормализации stream-путей оставлять в liveness-множестве только пути внутри `PROJECT_DIR`, которые физически существуют на момент проверки; абсолютные пути вне workspace (например, `/reports/...`) фиксировать как `stream_path_invalid`, отсутствующие пути внутри workspace фиксировать как `stream_path_missing`, оба типа исключать из расчёта stall.
- R12.4: Если primary extraction дал только `stream_path_invalid`/`stream_path_missing` или пустой валидный набор, обязателен fallback discovery; отсутствие fallback при таком случае — `prompt-exec issue (stream_path_resolution_incomplete)`.
- R13: Stage-result contract canonical-only: принимается только `schema=aidd.stage_result.v1` (alias через `schema_version` допустим только для canonical значения). Legacy `aidd.stage_result.<stage>.v1` считать историческим payload.
- R13.0: Для preflight write-path также canonical-only: `schema=aidd.stage_result.v1`, `stage=preflight`, `details.target_stage=<implement|review|qa>`; legacy preflight schema payload трактуется как historical `invalid-schema` (не runtime-path).
- R13.1: Если `reason_code=stage_result_missing_or_invalid` и diagnostics указывает fallback `invalid-schema` (включая legacy schema payload), классифицировать как `contract_mismatch(stage_result_shape)` и фиксировать отдельно от `prompt-exec issue`.
- R13.2: Для loop/review `reason_code=blocking_findings` трактовать как ожидаемый `REVISE`-сигнал (не flow bug по умолчанию).
- R13.3: Прямая запись/редактирование `aidd/reports/loops/**/stage.*.result.json` запрещена; stage-result должен эмититься только canonical runtime/stage-chain путём.
- R13.4: Если `stage_result_missing_or_invalid` сопровождается diagnostics-маркером `scope_fallback_stale_ignored`/`scope_shape_invalid`, классифицировать как `scope_drift_recoverable` (prompt-exec/policy), а не как `contract_mismatch(stage_result_shape)`.
- R14: Если в stage-логе (включая nested tool calls) есть запуск `python3 skills/.../runtime/*.py` из `PROJECT_DIR` и ошибка вида `can't open file .../skills/...`, классифицировать как `prompt-flow drift (non-canonical runtime path)`; не как env blocker.
- R14.1: Если такой drift встречается только во вложенном tool-call, но тот же stage завершился валидным top-level result (`exit_code=0` и `result_count>=1` или эквивалентный `done/success` payload), классифицировать как `WARN(prompt_flow_drift_recovered)`, не как `NOT VERIFIED`.
- R14.2: Для `runtime_path_missing_or_drift` (включая direct вызовы non-canonical `preflight*.py`) применять fail-fast: immediate `blocked`, без guessed retries и без manual recovery path.
- R14.3: Если в stage-логе есть direct вызов внутреннего stage-chain preflight entrypoint вне canonical stage-chain, классифицировать как `prompt-flow drift (non-canonical stage orchestration)` и останавливать manual recovery для текущего шага.
- R15: Если `*_run<N>.summary.txt` содержит `result_count=0` при валидном `init` (plugin/slash_commands/skills присутствуют), классифицировать как `prompt-exec issue (no_top_level_result)` и фиксировать отдельно.
- R15.1: Если `result_count` в summary отсутствует или пустой (`result_count=`), не трактовать это как `0` автоматически; сначала проверять top-level result/event в run-log, и только при подтверждённом отсутствии результата классифицировать `no_top_level_result`.
- R15.2: Для `loop-run` в `text`-режиме валидным top-level result считать JSON event `{"type":"result","schema":"aidd.loop_result.v1",...}` (в дополнение к строке summary `[loop-run] status=...`).
- R15.3: Для `review-spec` источником истины по finding/recommended status считать `aidd/reports/prd/<ticket>.json` (или `*.pack.json`); narrative top-level текста использовать только как supplementary telemetry.
- R16: Для launcher избегать tokenization drift: не передавать флаги как один неразделённый токен; при первом фейле quoting/tokenization делать ровно один shell-safe retry с явными отдельными аргументами.
- R17: Early-kill prohibition (strict):
  - не останавливать stage-run до исчерпания budget этапа, если есть liveness (`main log` и/или stream-файлы растут);
  - до budget случаи `result_count=0`, token-limit, repeated nested tool errors классифицировать как `WARN(prompt-exec no_convergence_yet)`, а не `killed`;
  - исключения: `ENV_BLOCKER`, `silent stall` (`main+stream` не растут >20 минут), явный process crash, user interrupt.
- R17.1: `kill` допускается только если не растут `main log` и все резолвленные stream-файлы (из primary extraction или fallback discovery) более 20 минут.
- R17.2: Если завершение с `exit_code=143` произошло при `killed=0` (или без явного watchdog kill marker), классифицируй как `ENV_MISCONFIG(parent_terminated|external_terminate)`, а не как `silent stall`/`prompt-exec issue`.
- R17.3: Если завершение с `exit_code=143` произошло при `killed=1` и подтверждённом `watchdog_marker=1`, классифицируй как `NOT VERIFIED (killed)` + `prompt-exec issue (watchdog_terminated)`; не как `ENV_MISCONFIG(parent_terminated|external_terminate)`.
- R17.4: Severity profile `conservative`: `ENV_BLOCKER`, `ENV_MISCONFIG`, `contract_mismatch` остаются terminal; `stream path` parser-noise (`stream_path_invalid|stream_path_missing`) и telemetry-mismatch не являются terminal сами по себе; `result_count=0` трактуется как инцидент только после явной проверки top-level payload.
- R17.5: Для шага 7 `diff_boundary_violation` не считается terminal, если `OUT_OF_SCOPE`/sample-path состоят только из `.aidd_audit/**`; это `prompt-exec issue (diff_boundary_ephemeral_misclassified)` и отдельный bug, но не flow terminal blocker.
- R18: Перед запуском `plan-new`, `review-spec`, `tasks-new` и любого шага `6/7/8` обязателен readiness gate из `AUDIT_DIR/05_precondition_block.txt`.
- R18.1: Readiness gate = `PASS` только при одновременном выполнении условий: `prd_status=READY`, `open_questions_count=0`, `answers_format=compact_q_codes|legacy_answer_alias`, и (`research_status=reviewed|ok` или scoped `research_status=warn`).
- R18.1a: `compact_q_codes` обязателен для retry payload в CLI (`AIDD:ANSWERS Q1=...; Q2=...`), но не как обязательный persisted-формат секции `AIDD:ANSWERS` в PRD/plan/tasklist.
- R18.1b: Scoped `research_status=warn` допускается только при одновременном выполнении условий: существуют `aidd/reports/research/<ticket>-rlm-targets.json`, `...-rlm-manifest.json`, `...-rlm.pack.json`; `aidd/reports/research/<ticket>-rlm.nodes.jsonl` непустой; `aidd/reports/research/<ticket>-rlm.links.stats.json` содержит `empty_reason=no_symbols|no_matches`; в `05_precondition_block.txt` фиксируется `research_warn_scope=links_empty_non_blocking` (иначе `invalid`).
- R18.2: При `FAIL` readiness gate обязателен `reason_code` из набора `prd_not_ready|open_questions_present|answers_format_invalid|research_not_ready|research_warn_unscoped`; шаг 5 классифицируется как `NOT VERIFIED (readiness_gate_failed)` + `prompt-flow gap`.
- R18.2a: Если первичный readiness gate = `FAIL` с `reason_code=prd_not_ready|open_questions_present|answers_format_invalid`, перед terminal-классификацией обязателен ровно один readiness-recovery цикл: закрытие PRD-вопросов (question template + compact `AIDD:ANSWERS` retry для `idea-new`, если trigger валиден) -> `/feature-dev-aidd:spec-interview <ticket>` -> `/feature-dev-aidd:review-spec <ticket>` -> пересчёт `05_precondition_block.txt`.
- R18.2b: Если `reason_code=research_not_ready`, допускается ровно один canonical researcher recovery/probe с последующим пересчётом `05_precondition_block.txt`.
- R18.2c: Если `readiness_gate=PASS` достигнут через scoped `research_status=warn`, фиксировать `WARN(readiness_gate_research_scoped)` и продолжать downstream stages; если scope невалиден — `reason_code=research_warn_unscoped` и terminal FAIL без WARN-relaxation.
- R18.3: При readiness gate `FAIL` после исчерпания recovery-цикла шаги `6/7/8` помечаются как `NOT VERIFIED (upstream_readiness_gate_failed)` без запуска stage-команд.
- R18.4: Если `review-spec` top-level narrative и `aidd/reports/prd/<ticket>.json|*.pack.json` расходятся по числу/типу findings, фиксировать `prompt-exec issue (review_spec_report_mismatch)` и принимать recovery-решение по report payload.
- R18.5: Если `review-spec` вернул `WARN|NEEDS_REVISION`, unresolved `Q*` отсутствуют и spec-файл существует, запускать findings-sync cycle:
  - PRD findings (`aidd/reports/prd/<ticket>.json|*.pack.json`) -> один sync-retry `idea-new` с compact payload `AIDD:SYNC_FROM_REVIEW ...`;
  - Plan findings (`plan_status=NEEDS_REVISION|WARN` в review payload или plan-review report) -> один sync-retry `plan-new` с compact payload `AIDD:SYNC_FROM_REVIEW ...`;
  - после sync-retry обязательно повторить `/feature-dev-aidd:review-spec <ticket>` и пересчитать `05_precondition_block.txt`.
- R18.6: Если после findings-sync cycle `readiness_gate` остаётся `FAIL`, классифицировать как `NOT VERIFIED (findings_sync_not_converged)` + `prompt-flow gap` (без попытки manual stage edits).

## 5) Политика запуска, ожидания и зависаний

### 5.0 Обязательный launcher (для каждого stage-run)

- Для `stream-json` режимов используй шаблон:
  - `cd "$PROJECT_DIR"`
  - `claude -p "<stage command>" $CLAUDE_ARGS $CLAUDE_STREAM_FLAGS $CLAUDE_PLUGIN_FLAGS`
- Для `text` режимов используй шаблон:
  - `cd "$PROJECT_DIR"`
  - `claude -p "<stage command>" $CLAUDE_ARGS $CLAUDE_PLUGIN_FLAGS`
- Shell-safe launch (рекомендуется для всех запусков): передавать каждый флаг отдельным аргументом, без склейки в одну строку/токен.
- Перед каждым stage-run делать disk-preflight:
  - `df -Pk "$PROJECT_DIR"` и проверка свободного места (`>= 1073741824` bytes);
  - если свободного места меньше, классифицировать как `ENV_MISCONFIG(no_space_left_on_device)` и не стартовать stage-run.
- Любой запуск stage-команды должен писать `stdout+stderr` в `AUDIT_DIR/<step>_run<N>.log`.
- Для каждого stage-run сохраняй `head` и `tail` в отдельные файлы (`*.head*.txt`, `*.tail.log`) и heartbeat (`*.heartbeat.log`).
- Для `stream-json` run дополнительно извлекай/сохраняй stream-пути (`*.stream.jsonl`, `*.stream.log`) в `AUDIT_DIR/<step>_stream_paths_run<N>.txt`.
- В `AUDIT_DIR/<step>_stream_paths_run<N>.txt` обязательно сохранять source-attribution для каждого пути (`init/header/metadata|fallback_scan`) и нормализованный абсолютный путь.
- Если primary extraction stream-путей не дал результата, выполнить fallback discovery и явно зафиксировать это в `AUDIT_DIR/<step>_stream_paths_run<N>.txt`.
- Если primary extraction содержит невалидные абсолютные пути вне `PROJECT_DIR`, сохранить их с source-attribution как `stream_path_invalid`, но не использовать для liveness/stall.
- Если primary extraction содержит путь внутри `PROJECT_DIR`, но путь отсутствует на диске, сохранить его как `stream_path_missing` и исключить из liveness/stall.
- В `AUDIT_DIR/<step>_stream_paths_run<N>.txt` каждая запись должна быть в формате `source=<...> path=<abs_path_inside_project>|stream_path_invalid=<abs_path_outside_project>|stream_path_missing=<abs_path_inside_project_missing>`; при отсутствии валидных путей после fallback фиксировать `fallback_scan=1` и `stream_path_not_emitted_by_cli=1`.
- Если stage завершился валидным top-level result, но stream-пути не извлеклись и fallback discovery не нашёл свежих `*.stream.jsonl|*.stream.log`, фиксировать `INFO(stream_path_not_emitted_by_cli)` без инцидента.

### 5.1 Проверка плагина в каждом stream-json run

- В `init`-событии лога должны присутствовать:
  - `plugins` содержит `feature-dev-aidd`.
  - `slash_commands` содержит `feature-dev-aidd:status` и stage-команду текущего шага.
- Если в `init` нет `feature-dev-aidd` или `slash_commands` без `feature-dev-aidd:*`:
  - классифицируй как `ENV_BLOCKER(plugin_not_loaded)`;
  - шаг = `NOT VERIFIED (env blocker)`;
  - останови аудит (не продолжай stage sequence).

### 5.2 Общие правила ожидания

- Silent stdout допустим.
- Не прерывай команды раньше бюджетов.
- Heartbeat раз в ~30s.
- Для **каждого** stage-run обязательно проверять рост логов каждые `LOG_POLL_SECONDS`:
  - `main log` (`size + tail`),
  - в `stream-json` также `stream_jsonl` (`size + tail`) и при наличии `stream_log`.
- Если используешь text-режим, live-tail всё равно обязателен.
- Множество stream-файлов для liveness формируется из `*_stream_paths_run<N>.txt`; при неполном наборе из primary extraction обязателен fallback discovery перед классификацией stall.

### 5.3 Буферизация/зависания

- Если лог = `0 bytes` дольше 120 секунд:
  - сначала классифицируй как `prompt-exec buffering/quoting risk`;
  - сделай один перезапуск той же команды в `stream-json` режиме.
- Если `main log = 0 bytes` дольше 120 секунд, но stream-файлы уже созданы и растут:
  - **не** считать это buffering risk;
  - продолжать run как `active_stream`.
- Если в stage-логе нет новых строк (или не растёт размер) >20 минут:
  - если stream-пути не были надёжно извлечены из main log/metadata, сначала выполни fallback discovery по loop-артефактам и пересчитай liveness;
  - сначала проверь stream-файлы:
    - если stream растёт, это `active_stream` (не stall);
    - если не растут и main log, и stream — это `silent stall`;
  - классифицируй как `silent stall`;
  - собери диагностику (`ps`, `tail`, размеры логов);
  - останови шаг как `NOT VERIFIED (silent stall)`.
- Если `main log` и/или stream растут, но top-level `result` не появляется (включая `result_count=0`, token-limit, repeated nested tool errors):
  - до исчерпания budget этапа **не** делать `kill`;
  - помечать как `WARN(prompt-exec no_convergence_yet)` и продолжать наблюдение.
- Если timeout loop-step произошёл при активном stream, но budget стадии ещё не исчерпан (`reason_code=seed_stage_active_stream_timeout`):
  - трактовать как `WARN(prompt-exec no_convergence_yet)`;
  - продолжать наблюдение/итерации; не завершать шаг terminal-статусом.
- Если timeout loop-step произошёл по исчерпанию budget стадии (`reason_code=seed_stage_budget_exhausted`):
  - трактовать как watchdog budget termination (`NOT VERIFIED (killed)` + `prompt-exec issue (watchdog_terminated)`).
- Для `silent stall` и preflight-предупреждения делай ровно один debug-retry той же команды с `ANTHROPIC_LOG=debug` перед финальной классификацией.
- При завершении процесса с `exit_code=143` обязателен `AUDIT_DIR/<step>_termination_attribution.txt` с полями: `exit_code`, `signal`, `killed_flag`, `watchdog_marker`, `parent_pid`, `classification`, `evidence_paths`.

### 5.4 Порядок классификации инцидентов (строгий)

- Сначала `ENV_BLOCKER`:
  - `Unknown skill: feature-dev-aidd:*`
  - в `init` отсутствуют `plugins/skills/slash_commands` для feature-dev-aidd
  - `refusing to use plugin repository as workspace root`
- Затем `ENV_MISCONFIG/external_terminate`:
  - `exit_code=143` при `killed=0` или без подтверждённого watchdog kill marker;
  - внешнее завершение родительского процесса/TTY/session manager (IDE stop, parent shell terminate, external `SIGTERM`).
- Затем `prompt-exec issue`:
  - buffering/quoting/runner/hang/silent stall
  - `exit_code=127` -> `launcher_tokenization_or_command_not_found` (не `completed`)
  - `reason_code=seed_stage_budget_exhausted` -> `watchdog_terminated` по budget exhaustion
- Отдельно `contract mismatch`:
  - `stage_result_missing_or_invalid` с diagnostics вида `invalid-schema` для fallback candidate (включая legacy stage-result schema payload)
- Только потом `flow bug`:
  - stage logic issue после подтверждения валидного env + retry/probe/fallback

### 5.5 Фильтрация WARN/DRIFT сигналов

- Stage-level классификацию делай по текущему stage-return, `init` и top-level result.
- Текст `WARN/Q*/AIDD:ANSWERS/Question` внутри вложенных артефактов (`tool_result`, excerpts tasklist/PRD/reports) не считать trigger-ом инцидента.
- `blocking_findings` внутри review/report артефактов не считать trigger-ом сам по себе: сигналом является только текущий stage-return (`reason_code`/`status`).
- Для drift extraction фиксируй source line/тип события; без source-attribution помечай как `report_noise`.
- Упоминание internal subagent (`feature-dev-aidd:tasklist-refiner`) внутри успешного `tasks-new` само по себе не является drift; drift фиксируй только если top-level stage-return предлагает non-canonical/manual recovery path как основной путь.
- Если top-level `success|WARN` payload рекомендует legacy alias (`/feature-dev-aidd:tasklist-refiner`, `/feature-dev-aidd:planner`, `/feature-dev-aidd:implementer`, `/feature-dev-aidd:reviewer`) как основной `Next step/Next action`, фиксируй `WARN(prompt_flow_drift_legacy_handoff_alias)`; при валидном stage-return и canonical-артефактах шаг не переводить в `NOT VERIFIED`.
- `WARN(tasklist_hygiene)` выставлять только по command-полям секции `AIDD:TEST_EXECUTION` (`tasks:`, `command:`, `commands:`); токены `&&`, `||`, `;` в prose/notes классифицировать как `report_noise`.
- Счётчики из `*_signal_counts.txt` (`blocked_hits`, `manual_stage_result_write_hits`, `question_prompt_hits` и т.п.) использовать только как telemetry; инцидент фиксировать только при совпадении с top-level stage-return/summary.

Рекомендуемые бюджеты:
- Для этапов: idea-new, research, review-spec, tasks-new предусмотрен бюджет до 20 мин.
- Для этапа `plan-new` предусмотрен бюджет до 30 мин.
- Для этапов: implement до 60 мин, review до 60 мин, loop-run до 120 мин, loop-step до 90 мин.

Если бюджет превышен:
- собрать диагностику (`ps`, `tail`, артефакты),
- остановить команду,
- пометить результаты шага как `NOT VERIFIED (killed)`.
- до превышения budget `kill` запрещён при наличии liveness (см. `R17`), кроме исключений `ENV_BLOCKER`/`silent stall`/process crash/user interrupt.

## 6) Универсальный шаблон обработки вопросов (обязательно)

Используй этот шаблон для всех stage-команд:

1. Запусти первую попытку по R0/R0.1.
2. Если stage задаёт вопросы/возвращает BLOCK из-за отсутствия ответов:
   - retry-триггер разрешён только по текущему stage-return (финальный ответ stage-команды);
   - для `idea-new` и `plan-new` retry-триггер также считается валидным, если top-level `success|WARN` явно требует ответить на `Q*`/закрыть `Ответ N: TBD` и перевести артефакт стадии в `READY`;
   - не считать trigger-ом `Q*`/`AIDD:ANSWERS`/`Question` внутри вложенных артефактов (PRD/tasklist/reports/log excerpts), если stage-return сам не запрашивает ответ;
   - извлеки вопросы в `AUDIT_DIR/<step>_questions.txt`;
   - сформируй `AIDD:ANSWERS` в `AUDIT_DIR/<step>_answers.txt` на основе уже собранных артефактов;
   - дополнительно сохрани `AUDIT_DIR/<step>_questions_raw.txt` и `AUDIT_DIR/<step>_questions_normalized.txt` (нормализация `Q<N>` и choice-кодов перед retry);
   - если source содержит legacy `Answer N:`/`Answer to QN:` или `TBD`, нормализуй в `Q<N>=<choice|short_code>`; при невозможности нормализации фиксируй `reason_code=answers_format_invalid` и не выполняй retry;
   - выполни **ровно один** retry;
   - формат ответов для retry должен быть **компактным**: choice-коды/короткие фразы в одной строке, без длинного многострочного prose;
   - рекомендуемый шаблон: `AIDD:ANSWERS Q1=C; Q2=B; Q3=C; Q4=A; Q5=C`.
3. Retry формат:
   - `idea-new`: `ticket + IDEA_NOTE + AIDD:ANSWERS`;
   - остальные stage: `ticket + AIDD:ANSWERS`;
   - не вставляй в CLI многострочные ответы с большим количеством Unicode/пунктуации; если нужно сохранить детали, держи их в `<step>_answers.txt`, а в команду передавай сжатый вариант.
   - в CLI передавай только нормализованный one-line payload вида `AIDD:ANSWERS Q1=...; Q2=...`; legacy префиксы `Answer N:` в retry запрещены.
   - для runtime retry используй canonical CLI-аргументы runtime (например, `--plan-path` для `plan-review-gate`) без legacy alias-аргументов.
4. Если после retry всё ещё BLOCKED:
   - зафиксируй `WARN`/`FAIL` с причиной,
   - продолжай по сценарию, где это возможно.
5. Если причина BLOCKED связана с отсутствующим spec (`aidd/docs/spec/<ticket>.spec.yaml`), unresolved PRD-вопросами (`Q*`) или `PRD Status != READY` (например `draft`):
   - сначала пройди `/feature-dev-aidd:spec-interview <ticket>` (тот же retry-шаблон),
   - затем пройди `/feature-dev-aidd:review-spec <ticket>`,
   - затем перед повтором stage обязательно перепроверь `aidd/docs/prd/<ticket>.prd.md` (`Status:` и unresolved `Q*`);
   - если после `spec-interview + review-spec` PRD остаётся `Status != READY` и unresolved `Q*` отсутствуют, выполни findings-sync cycle:
     - PRD findings -> `/feature-dev-aidd:idea-new <ticket> <IDEA_NOTE> AIDD:SYNC_FROM_REVIEW ...`;
     - Plan findings -> `/feature-dev-aidd:plan-new <ticket> AIDD:SYNC_FROM_REVIEW ...`;
     - затем повтори `/feature-dev-aidd:review-spec <ticket>` и перепроверь `Status`;
   - если после findings-sync `Status != READY`, классифицируй как `NOT VERIFIED (findings_sync_not_converged)` + `prompt-flow gap` и не запускай stage, который требует `PRD READY`.
6. Если stage-return содержит `Unknown skill` или отсутствуют feature-dev-aidd slash commands в `init`:
   - **не** применять question retry-шаблон;
   - классифицировать как `ENV_BLOCKER(plugin_not_loaded)` и остановить аудит.
7. Если stage-return уводит в ручной preflight/ручную запись `stage.*.result.json`, предлагает direct вызов внутреннего stage-chain preflight entrypoint или рекомендует legacy stage aliases (`/feature-dev-aidd:planner`, `/feature-dev-aidd:tasklist-refiner`, `/feature-dev-aidd:implementer`, `/feature-dev-aidd:reviewer`) как основной recovery path/next action:
   - классифицировать как `prompt-flow drift (non-canonical stage orchestration)` и `policy_violation(stage_result_manual_write)` при попытке ручного stage-result write;
   - не выполнять этот manual path в e2e аудите;
   - зафиксировать `NOT VERIFIED` для шага и продолжить только по разрешённому сценарию.
8. Если nested runtime-команда использует non-canonical путь `python3 skills/...` или runtime CLI-аргументы вне текущего контракта (пример: `--scope_key` вместо `--scope-key`, `--findings_summary`), классифицировать как `prompt-flow drift (runtime_cli_contract_mismatch)`; manual path не выполнять.

Примечание: это и есть ключ к “человекочитаемому” flow. Вопросы — часть happy path, а не исключение.

## 7) MUST-READ

{{MUST_READ_MANIFEST}}

## 8) Каталог задач для шага 3 (выбрать ровно одну)

Контекст анализа:
- `PROJECT_DIR/README.md`
- `PROJECT_DIR/docs/backlog.md`
- `PROJECT_DIR/backend/src/main/java/**/controller/*Controller.java`
- `PROJECT_DIR/frontend/src/pages/*.tsx`
- `PROJECT_DIR/frontend/src/lib/apiClient.ts`

### FS-GA-01 (L) GitHub Analysis Flow: production-ready UX + canonical payload
- Backend scope:
  - Оркестрация `github-analysis-flow` с шагами `fetch_metadata -> fetch_tree -> analysis -> recommendations`.
  - Typed payload/DTO (`analysisStatus`, `retries`, `recommendationBlocks`, `actions`, `stepProgress`) + OpenAPI sync.
  - Идемпотентное хранение результатов анализа.
- Frontend scope:
  - MCP panel блок GitHub Analysis (URL/ref/PR, режим, валидация).
  - Прогресс шагов, ретраи/ошибки, карточка результата.
  - Review actions: `comment`, `approve`, `request changes`.
- Acceptance criteria:
  - Запуск из UI создаёт flow session и даёт прогресс без ручного рефреша.
  - Результат содержит canonical payload и доступен из истории.
  - Типы консистентны между backend DTO и frontend client.

### FS-MP-02 (L) GitHub/GitLab parity для assisted coding flow
- Backend scope:
  - Provider-aware contract (`github|gitlab`) в registry/orchestrator/pipeline.
  - GitLab MCP stack и маршрутизация URL/MR.
  - Общие метрики/логи/fallback policy.
- Frontend scope:
  - Переключатель provider в UI/CLI.
  - Provider-specific ссылки и `workspace_git_state`.
  - Provider-aware cache/recovery.
- Acceptance criteria:
  - Один flow работает для GitHub и GitLab URL без ручной правки payload.
  - UI корректно показывает provider/ссылки/статусы.
  - Интеграционные тесты покрывают fetch -> state -> analysis.

### FS-RBAC-03 (M) Live RBAC enforcement + admin role operations
- Backend scope:
  - Усиление role enforcement на критичных API.
  - Audit trail для role operations и 403.
  - Стабилизация role guard/interceptor.
- Frontend scope:
  - Live обновление ролей в сессии.
  - Role guards для admin/flow controls.
  - Единая обработка 403.
- Acceptance criteria:
  - Изменения ролей видны без перезагрузки.
  - Backend consistently возвращает 403 без роли.
  - Admin roles audit соответствует действиям.

### FS-ID-04 (L) VK OAuth + Telegram Login Widget profile linking
- Backend scope:
  - `GET /auth/vk`, `POST /auth/vk/callback` (PKCE/state/device_id).
  - Refresh/revoke pipeline для VK tokens.
  - Telegram callback hash validation + anti-replay + profile attach.
- Frontend scope:
  - Link/unlink блок внешних провайдеров + Telegram widget.
  - Статусы линковки/ошибок/expiry.
  - Channel-specific UX подсказки.
- Acceptance criteria:
  - VK/Telegram linking end-to-end.
  - Backend валидирует подписи/state и пишет audit events.
  - E2E покрывает happy path + replay/expired/error.

### FS-GRAPH-05 (L) Code graph IDE navigation (outline + anchors + target path)
- Backend scope:
  - Расширение графа (`CONTAINS`, сигнатуры, docstring, visibility, anchors).
  - Улучшение `graph_neighbors`/`graph_path`/`definition`.
  - Кэш/метрики/fallback для graph queries.
- Frontend scope:
  - UI для outline/anchors/previews.
  - Отображение путей до `goalFqn` + relation filters.
  - Визуальная деградация в fallback mode.
- Acceptance criteria:
  - Из UI можно получить outline и перейти к символу по anchors.
  - Path queries возвращают цель по `targetHint`/`goalFqn`.
  - Метрики показывают latency/hit/miss/fallback reasons.

## 9) Пошаговый flow (для агента)

Логи до `aidd-init` сохраняй в:
- `RUN_TS=$(date -u +%Y%m%dT%H%M%SZ)`
- `AUDIT_DIR=$PROJECT_DIR/.aidd_audit/$TICKET/$RUN_TS`

### Шаг 0. Clean state

Зачем: фиксируем чистую базу и репродуцируемость.

Сделать:
- `cd "$PROJECT_DIR"`;
- сохранить pre-status во временный файл: `/tmp/00_git_status_before.${TICKET}.${RUN_TS}.txt`;
- принудительно очистить workspace до `HEAD`:
  - `git reset --hard HEAD`
  - `git clean -fd`
- создать `AUDIT_DIR` после cleanup (иначе untracked аудит-логи могут исчезнуть);
- скопировать pre-status в `AUDIT_DIR/00_git_status_before.txt`;
- сохранить post-status в `AUDIT_DIR/00_git_status_after.txt`;
- если cleanup не удался — `BLOCKER(clean_state_unavailable)` и stop;
- сохранить plugin status baseline в `00_plugin_git_status_before.txt`.

### Шаг 1. Preflight (fail-fast env)

Зачем: зафиксировать режим и окружение. Убедиться, что плагин реально загружается в non-interactive `claude -p`.

Сделать:
- checkout audit branch;
- сохранить head/branch;
- определить `AUDIT_MODE`:
  - SKILL_FIRST если есть `skills/aidd-core/SKILL.md` и `skills/implement/SKILL.md`;
  - иначе `LEGACY_UNSUPPORTED` и stop как N/A;
- выполнить plugin-prompt path scan и сохранить `01_non_canonical_runtime_path_scan.txt`:
  - `rg -n "python3 skills/.*/runtime/" "$PLUGIN_DIR/skills/{implement,review,qa}/SKILL.md"`;
  - при hit пометить `WARN(prompt_surface_non_canonical_runtime_path)` (не блокирует старт аудита).
- зафиксировать `claude plugin list` в `01_plugin_list.txt`;
- зафиксировать `~/.claude/settings.json` (если есть) в `01_claude_settings_snapshot.json`;
- выполнить healthcheck команду (`$PLUGIN_HEALTHCHECK_CMD`) через launcher из секции 5.0;
- проверить `init`-событие healthcheck-лога:
  - есть `plugins: [{"name":"feature-dev-aidd"...}]`;
  - есть `slash_commands` с `feature-dev-aidd:status`;
  - есть `skills` с `feature-dev-aidd:*`.
- если любой пункт не выполнен, или получен `Unknown skill`:
  - классифицировать как `ENV_BLOCKER(plugin_not_loaded)`;
  - сохранить маркер `01_env_blocker.txt`;
  - **остановить аудит** без выполнения шагов 2..99.
- если получен `refusing to use plugin repository as workspace root`:
  - исправить `cwd` на `PROJECT_DIR`;
  - повторить healthcheck 1 раз;
  - при повторном провале -> `ENV_BLOCKER(cwd_wrong)` и stop.

### Шаг 2. Baseline

Зачем: зафиксировать состояние workspace до инициализации.

Сделать:
- `cd "$PROJECT_DIR"`;
- `ls -la`;
- snapshot дерева `aidd` (или `aidd: missing`).

### Шаг 3. Task selection + IDEA_NOTE

Зачем: имитация реального UX выбора задачи.

Сделать:
- короткий анализ repo surfaces;
- сохранить:
  - `03_repo_analysis.txt`
  - `03_task_candidates.md` (>=3 задачи)
  - `03_selected_task.txt` (ровно одна задача)
- сгенерировать `03_problem_statement.txt`:
  - 3–6 предложений,
  - 3–5 acceptance criteria,
  - backend + frontend scope.
- сформировать `IDEA_NOTE` из этого файла (одно строковое значение).

### Шаг 4. aidd-init

Зачем: подготовить workspace runtime-структуру.

Готовность:
- `aidd/AGENTS.md`
- `aidd/docs/shared/stage-lexicon.md`

Если не готово:
- выполнить `/feature-dev-aidd:aidd-init` через launcher.

Если slash-run вернул `Unknown skill`:
- классифицировать `ENV_BLOCKER(plugin_not_loaded)` и stop.

После:
- сохранить `04_aidd_tree_post.txt`.

### Шаг 5. Happy path

Общее правило для 5.1..5.5:
- каждый slash stage-run через launcher;
- при `Unknown skill` -> `ENV_BLOCKER(plugin_not_loaded)` и stop;
- question retry использовать только для реальных stage-вопросов/BLOCK.
- manual internal stage-chain/debug path (включая ручную запись `stage.*.result.json`) не использовать как recovery для slash stage-команд 5.x; использовать только canonical slash-stage путь и fallback'и, явно разрешённые в соответствующем подпункте.

#### 5.1 idea-new

Зачем: создать PRD + активный контекст.

Сделать:
- первый запуск: `/feature-dev-aidd:idea-new $TICKET $IDEA_NOTE`;
- при вопросах: retry по шаблону секции 6;
- снять артефакты:
  - `05_active.json`
  - `05_prd_head.txt`
  - `05_slug_check.txt`

Проверки slug:
- non-empty;
- regex `^[a-z0-9]+(-[a-z0-9]+)*$`;
- не содержит сырой `AIDD:ANSWERS`.

#### 5.1a PRD question-closure (до readiness gate)

Зачем: не допустить ложный `readiness_gate=FAIL`, если `idea-new` завершился success, но PRD остался с неотвеченными вопросами.

Сделать:
- после `5.1` проверить top-level stage-return и `aidd/docs/prd/$TICKET.prd.md`;
- если обнаружены неотвеченные вопросы (`Q*`, `Ответ N: TBD`, `Answer N: TBD`, `Status: draft` при явном требовании stage-return закрыть вопросы), выполнить question retry для `idea-new` по шаблону секции 6;
- сохранить артефакты question-cycle:
  - `05_idea_new_questions_raw.txt`
  - `05_idea_new_questions_normalized.txt`
  - `05_idea_new_answers.txt`
- `AIDD:ANSWERS` для retry передавать compact one-line payload; использовать choice-коды/короткие ответы, опираясь на `Default:`/варианты в PRD;
- после retry повторно снять `05_prd_head.txt` и убедиться, что `Status` и unresolved `Q*` отражают актуальное состояние.

#### 5.2 researcher

Зачем: сформировать research + RLM artifacts.

Сделать:
- первый запуск ticket-only;
- при вопросах: retry;
- в non-interactive path ожидать bounded auto-recovery внутри researcher runtime:
  - canonical finalize orchestration (`rlm_finalize`, при необходимости bootstrap) не более 1 попытки;
  - при unresolved pending обязательны детерминированные поля в `AIDD:RLM_EVIDENCE`: `Pending reason`, `Next action`, `Baseline marker`.
- fallback допускается только если stage blocked/hang (не для `Unknown skill`):
  - `python3 $PLUGIN_DIR/skills/researcher/runtime/research.py --ticket $TICKET --auto --paths backend/src/main/java,frontend/src/pages --keywords github,analysis,flow`
- пометить fallback marker.

RLM artifacts check (после fallback, если был):
- must exist:
  - `${TICKET}-rlm-targets.json`
  - `${TICKET}-rlm-manifest.json`
  - `${TICKET}-rlm.worklist.pack.json`
- must NOT exist:
  - `${TICKET}-context.json`
  - `${TICKET}-targets.json`

#### 5.2.1 Step 5 Readiness Gate (hard-stop)

Зачем: не допускать каскадных блокировок downstream stages при неготовых входных артефактах.

Сделать:
- после `5.1` и `5.2` записать `05_precondition_block.txt` с полями:
  - `prd_status=<READY|draft|...>`
  - `open_questions_count=<int>`
  - `answers_format=<compact_q_codes|legacy_answer_alias|invalid>`
  - `research_status=<reviewed|ok|pending|warn|invalid>`
  - `research_warn_scope=<none|links_empty_non_blocking|invalid>`
  - `readiness_gate=<PASS|FAIL>`
  - `reason_code=<prd_not_ready|open_questions_present|answers_format_invalid|research_not_ready|research_warn_unscoped|->`
- запуск `5.3/5.4/5.5` допускается только при `readiness_gate=PASS`.
- если `readiness_gate=PASS` через scoped `research_status=warn` (`research_warn_scope=links_empty_non_blocking`), зафиксировать `WARN(readiness_gate_research_scoped)` и продолжать downstream stages.
- если `readiness_gate=FAIL`:
  - в `05_precondition_block.txt` обязательно заполнить конкретный `reason_code`;
  - если `reason_code=prd_not_ready|open_questions_present|answers_format_invalid`, выполнить ровно один readiness-recovery цикл:
    1) закрыть PRD/plan-вопросы через question template (включая compact retry для `idea-new` и `plan-new`, если trigger валиден);
    2) выполнить `/feature-dev-aidd:spec-interview $TICKET` (ticket-only, при вопросах один retry);
    3) выполнить `/feature-dev-aidd:review-spec $TICKET` (ticket-only, при вопросах один retry);
    4) перепроверить PRD header (`Status:` + unresolved `Q*`) и пересчитать `05_precondition_block.txt`.
  - если `reason_code=research_not_ready`, выполнить ровно один canonical recovery/probe для researcher и пересчитать `05_precondition_block.txt`.
  - если `reason_code=research_warn_unscoped`, WARN-relaxation не применять; классифицировать шаг 5 как `NOT VERIFIED (readiness_gate_failed)` + `prompt-flow gap` и не запускать `5.3/5.4/5.5`.
  - если после recovery циклa `readiness_gate` всё ещё `FAIL`, шаг 5 классифицировать как `NOT VERIFIED (readiness_gate_failed)` + `prompt-flow gap`;
  - если после recovery циклa `readiness_gate` всё ещё `FAIL`, не запускать `5.3/5.4/5.5`, а шаги `6/7/8` сразу пометить `NOT VERIFIED (upstream_readiness_gate_failed)` и перейти к шагу 99.

#### 5.3 plan-new

Зачем: получить реализуемый план.

Сделать:
- запускать только при `readiness_gate=PASS` (см. 5.2.1);
- first run ticket-only;
- при вопросах: retry;
- если hang/kill: выполнить runtime probe
  - `python3 $PLUGIN_DIR/skills/plan-new/runtime/research_check.py --ticket $TICKET --expected-stage plan`
- для downstream probes (`plan/review/qa`) pending должен классифицироваться как `reason_code=rlm_status_pending` + finalize hint;
- `baseline_missing` в downstream probes считать drift/contract mismatch.
- классифицировать как prompt-exec issue до probe.

#### 5.3.1 Plan question-closure (после первого `plan-new`)

Зачем: закрыть вопросы плана до запуска downstream стадий, даже если первый `plan-new` завершился `success|WARN`.

Сделать:
- если top-level stage-return `plan-new` явно требует закрыть `Q*`/`Answer N: TBD`/`AIDD:ANSWERS`, выполнить ровно один question retry по шаблону секции 6;
- сохранить артефакты:
  - `05_plan_new_questions_raw.txt`
  - `05_plan_new_questions_normalized.txt`
  - `05_plan_new_answers.txt`
- передавать в CLI только compact one-line payload: `AIDD:ANSWERS Q1=...; Q2=...`;
- после retry снять `05_plan_head.txt` (статус/нерешённые вопросы плана).

Anti-cascade:
- если после retry top-level stage-return `plan-new` всё ещё требует закрыть вопросы:
  - шаг 5.3 = `NOT VERIFIED (plan_qna_unresolved)` + `prompt-flow gap`;
  - не запускать `5.4/5.5`;
  - шаги `6/7/8` пометить `NOT VERIFIED (upstream_plan_qna_unresolved)` и перейти к шагу 99.

#### 5.4 review-spec

Зачем: проверить план+PRD gate.

Сделать:
- запускать только при `readiness_gate=PASS` (см. 5.2.1);
- first run ticket-only;
- при вопросах: retry;
- после каждого run сохранять `05_review_spec_report_check_run<N>.txt`:
  - `report_path`, `recommended_status`, `findings_count`, `open_questions_count`, `spec_exists`, `prd_findings_sync_needed`, `plan_findings_sync_needed`, `narrative_vs_report_mismatch`;
- если итог review-spec = `WARN/BLOCKED` и в отчёте есть unresolved `Q*` или ссылка на отсутствующий spec:
  - выполнить `/feature-dev-aidd:spec-interview $TICKET` (ticket-only, при вопросах один retry);
  - повторить `/feature-dev-aidd:review-spec $TICKET` один раз;
- если `05_review_spec_report_check_run<N>.txt` фиксирует `prd_findings_sync_needed=1` и `open_questions_count=0`:
  - сохранить `05_prd_findings_sync_request.txt` (compact payload на основе findings report);
  - выполнить ровно один sync-retry `/feature-dev-aidd:idea-new $TICKET $IDEA_NOTE AIDD:SYNC_FROM_REVIEW ...`;
  - повторить `/feature-dev-aidd:review-spec $TICKET` один раз.
- если `05_review_spec_report_check_run<N>.txt` фиксирует `plan_findings_sync_needed=1` и `open_questions_count=0`:
  - сохранить `05_plan_findings_sync_request.txt` (compact payload на основе findings report);
  - выполнить ровно один sync-retry `/feature-dev-aidd:plan-new $TICKET AIDD:SYNC_FROM_REVIEW ...`;
  - повторить `/feature-dev-aidd:review-spec $TICKET` один раз.
- если hang/kill: runtime probe
  - `python3 $PLUGIN_DIR/skills/aidd-core/runtime/prd_review.py --ticket $TICKET`

#### 5.5 tasks-new

Зачем: получить tasklist execution source.

Сделать:
- запускать только при `readiness_gate=PASS` (см. 5.2.1);
- перед первым запуском проверить PRD header (`Status:`): если не `READY` или есть unresolved `Q*`, сначала:
  - если последний `05_review_spec_report_check_run<N>.txt` показывает `prd_findings_sync_needed=1` и `open_questions_count=0`, сначала выполнить findings-sync через `idea-new` (см. 5.4), затем повторить `review-spec`;
  - если последний `05_review_spec_report_check_run<N>.txt` показывает `plan_findings_sync_needed=1` и `open_questions_count=0`, сначала выполнить findings-sync через `plan-new` (см. 5.4), затем повторить `review-spec`;
  - выполнить `/feature-dev-aidd:spec-interview $TICKET` (ticket-only, при вопросах один retry),
  - выполнить `/feature-dev-aidd:review-spec $TICKET` (ticket-only, при вопросах один retry),
  - затем повторно проверить PRD header (`Status:` + unresolved `Q*`); если PRD всё ещё не `READY`, классифицировать как `NOT VERIFIED (findings_sync_not_converged)` + `prompt-flow gap`, пометить шаг 5.5 `NOT VERIFIED` и не запускать `tasks-new`.
- first run ticket-only;
- при вопросах: retry;
- если tasks-new сообщает `Missing Spec File` / `aidd/docs/spec/$TICKET.spec.yaml` / unresolved `Q*`:
  - классифицировать как prompt-flow gap (не code bug на первом проходе);
  - выполнить `/feature-dev-aidd:spec-interview $TICKET` (ticket-only, при вопросах один retry);
  - перед retry снова проверить PRD header (`Status:` + unresolved `Q*`); если `Status != READY`, сначала выполнить findings-sync cycle (idea-new/plan-new по `05_review_spec_report_check_run<N>.txt`), затем повторно проверить `Status`;
  - если после findings-sync `Status != READY`, классифицировать как `NOT VERIFIED (findings_sync_not_converged)` + `prompt-flow gap` и не выполнять retry `tasks-new`;
  - иначе повторить `/feature-dev-aidd:tasks-new $TICKET` один раз;
- если `tasks-new` завершился `success|WARN`, но `summary/log` содержит рекомендации manual/non-canonical recovery как primary path:
  - классифицировать как `WARN(prompt_flow_drift_non_canonical_stage_orchestration)`;
  - не переходить на manual path, продолжать сценарий.
- если hang/kill: fallback
  - `python3 $PLUGIN_DIR/skills/tasks-new/runtime/tasks_new.py --ticket $TICKET`
- сохранить `05_tasklist_status_check.txt`.
- если после retry tasks-new остаётся `BLOCKED`:
  - пометить как `prompt-flow blocker`,
  - шаги 6/7 пометить `NOT VERIFIED` и перейти к 8/99.

### Шаг 6. Loop seed (только full)

Зачем: зафиксировать ручную стартовую итерацию.

Сделать:
- один запуск `implement`, один запуск `review`.
- question retry для шага 6 запрещён (R1): если один из запусков уходит в BLOCK/questions, зафиксировать `NOT VERIFIED` и не делать второй attempt того же stage.
- если kill/hang — отмечать `NOT VERIFIED`.
- если `*_summary.txt` содержит `result_count=0` при валидном `init`, классифицировать как `NOT VERIFIED (no_top_level_result)` + `prompt-exec issue`.
- если в логах шага есть `python3 skills/.../runtime/*.py` + `can't open file`, классифицировать как `NOT VERIFIED (prompt_flow_drift_non_canonical_runtime_path)`.
- Anti-cascade gate: если шаг 6 завершился terminal `NOT VERIFIED` из-за `watchdog_terminated` или `no_top_level_result`, шаги 7 и 8 пометить `NOT VERIFIED (upstream_seed_stage_failed)` и перейти к шагу 99.

Loop seed integrity checks:
- `06_active_after_review.json`
- `06_work_item_check.txt`:
  - допустимо: `iteration_id=I<N>`/`M<N>` или `null`
  - недопустимо: `id=review:*` / `id_review_*`
- inventory:
  - `06_actions_tree.txt`
  - `06_context_tree.txt`
  - `06_stage_chain_logs_tree.txt`
  - `06_loops_tree.txt`
- marker semantics check:
  - `06_marker_semantics_check.txt`
  - при проверке исключать шаблонные/backup-файлы (`aidd/docs/tasklist/templates/**`, `*.bak`, `*.tmp`) из детекции ложных marker hits.
  - дополнительно исключать примеры/инструктивные блоки в `AIDD:HOW_TO_UPDATE` и `AIDD:PROGRESS_LOG` (строки с префиксом `>`, inline/fenced code-примеры и placeholder-строки).
  - маркеры handoff вида `id=review:*` в `AIDD:ITERATIONS_FULL`/`AIDD:PROGRESS_LOG` считать валидными; инцидент фиксировать только для identity-полей (`active.work_item`, `work_item_key`, `scope_key`) или служебных stage-chain payload полей.

Fail-fast gate (до шага 7):
- проверить, что артефакты loop-seed существуют и не пустые: `06_active_after_review.json`, `06_work_item_check.txt`, `06_stage_chain_logs_tree.txt`, `06_loops_tree.txt`;
- если любой из артефактов отсутствует/пустой, классифицировать как `NOT VERIFIED (preloop_artifacts_missing)` + `prompt-flow drift`;
- при `preloop_artifacts_missing` шаги 7 и 8 пометить `NOT VERIFIED` и перейти к шагу 99 (без запуска auto-loop/qa).

### Шаг 7. Auto-loop (только full)

Зачем: проверить loop orchestration без ручного вмешательства.

Сделать:
- перед запуском установить `AIDD_LOOP_RUNNER="claude --dangerously-skip-permissions"`;
- `loop-run` или `loop-step` (по `LOOP_MODE`) через Python runtime:
  - `CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 $PLUGIN_DIR/skills/aidd-loop/runtime/loop_run.py --ticket $TICKET --max-iterations 6 --stream --blocked-policy $BLOCKED_POLICY --recoverable-block-retries $RECOVERABLE_BLOCK_RETRIES`
  - или `CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 $PLUGIN_DIR/skills/aidd-loop/runtime/loop_step.py --ticket $TICKET --stream`.
- сохранить stream liveness и runner-mode диагностику:
  - `07_loop_stream_liveness_check.txt` (main log vs stream jsonl/log growth),
  - `07_loop_runner_mode_check.txt` (`permissionMode`, approval-denied signals),
  - `07_stage_result_contract_check.txt` (если blocked по `stage_result_missing_or_invalid`),
  - `07_recoverable_block_policy_check.txt` (`recoverable_blocked`, `recovery_path`, `retry_attempt`),
  - `07_blocking_findings_policy_check.txt` (`reason_code=blocking_findings` -> expected REVISE semantics; для `BLOCKED_POLICY=ralph` expected recoverable path).
  - `07_result_count_check.txt` (`result_count=0` vs top-level blocked/done payload consistency).

Если в stream `init` видно `permissionMode=default` и есть `requires approval`:
- классифицировать как `ENV_MISCONFIG(loop_runner_permissions)`;
- выполнить ровно один retry после явной установки runner/env (без смены сценария).

Если loop-step/loop-run вернул `blocked` с `reason_code=blocking_findings`:
- для `BLOCKED_POLICY=strict`: фиксировать как `WARN(expected_revise_signal)` с продолжением по стандартной диагностике;
- для `BLOCKED_POLICY=ralph`: ожидать `recoverable_blocked=1` и recovery/retry path; отклонения фиксировать как `policy_mismatch(blocked_policy_vs_reason_code)`.
- для `BLOCKED_POLICY=ralph` использовать policy matrix v2 (`ralph_recoverable_reason_scope=policy_matrix_v2`): `hard_block|recoverable_retry|warn_continue`.
- если `BLOCKED_POLICY=ralph` и `reason_class != recoverable_retry`, ожидай `ralph_recoverable_not_exercised=1` + `ralph_recoverable_not_exercised_reason=reason_not_recoverable_by_policy:<reason_code>`; не классифицировать это как `policy_mismatch` по умолчанию.
- если `BLOCKED_POLICY=ralph` и `reason_class = recoverable_retry`, но retry не выполнен из-за лимита, ожидай `ralph_recoverable_not_exercised_reason=recoverable_budget_exhausted:<reason_code>`.

Если pre-iteration research gate вернул `blocked` с `reason_code=rlm_links_empty_warn|rlm_status_pending`:
- для `BLOCKED_POLICY=ralph` ожидать bounded recoverable probe по `next_action` с `recovery_path=research_gate_links_build_probe` до terminal blocked;
- отсутствие recoverable probe/атрибуции фиксировать как `policy_mismatch(research_gate_recovery_path)`.

Если blocked содержит diagnostics с `scope_fallback_stale_ignored`/`scope_shape_invalid`:
- ожидать промоцию в recoverable `reason_code=scope_drift_recoverable`;
- ожидать recovery path `scope_drift_reconcile_probe` (как минимум один probe до итогового BLOCK);
- отсутствие этих признаков фиксировать как `policy_mismatch(scope_drift_recovery_path)`.

Loop runtime integrity checks:
- `07_scope_mismatch_check.txt`
- `07_id_review_tests_hits.txt` (должно быть пусто)
- `07_python_only_surface_check.txt` (не должно быть shell stage-chain вызовов)
- `07_loop_stream_liveness_check.txt` (пруф, что probe смотрит main + stream)
- `07_loop_runner_mode_check.txt` (non-interactive runner mode подтверждён)
- `07_stage_result_contract_check.txt` (contract mismatch vs prompt-exec разведены)
- `07_blocking_findings_policy_check.txt` (blocking_findings semantics: REVISE + ralph recoverable)

Anti-cascade gate (до шага 8):
- если шаг 7 завершился terminal blocked с `reason_code=stage_result_missing_or_invalid` или `watchdog_terminated`, шаг 8 пометить `NOT VERIFIED (upstream_loop_stage_failed)` и перейти к шагу 99.

### Шаг 8. QA

Зачем: итоговая валидация тестовой готовности.

Сделать:
- first run ticket-only;
- precheck `AIDD:TEST_EXECUTION`:
  - сохранить `08_test_execution_precheck.txt`;
  - искать shell-chain токены (`&&`, `||`, `;`) только в command-полях секции `AIDD:TEST_EXECUTION`; в prose/notes не считать инцидентом;
  - если найдено в command-поле как единая task entry, по умолчанию пометить `INFO(tasklist_hygiene)` и продолжить QA с фиксацией риска;
  - повышать до `WARN(tasklist_hygiene)` только если тот же shell-chain реально исполнялся в текущем QA run и дал fail-сигнал;
- если в логе виден direct вызов non-canonical stage preflight runtime вне canonical stage-chain:
  - классифицировать как `prompt-flow drift (non-canonical stage orchestration)`;
  - не продолжать manual recovery path для текущего шага.
- при вопросах: retry;
- если QA-run упал по `python3 skills/qa/runtime/qa.py` + `can't open file`:
  - классифицировать как `prompt-flow drift (non-canonical runtime path)`;
  - выполнить ровно один canonical fallback: `python3 $PLUGIN_DIR/skills/qa/runtime/qa.py --ticket $TICKET`;
- если hang/kill: fallback
  - `python3 $PLUGIN_DIR/skills/qa/runtime/qa.py --ticket $TICKET`

QA integrity checks:
- `08_qa_gradle_check.txt` (проверка через `find` + `rg`, без raw-glob вроде `aidd/reports/qa/*tests*.log`, чтобы избежать `no matches found` в zsh).

### Шаг 99. Post-run write-safety

Зачем: проверить, что runtime не писал в plugin source.

Сделать:
- `99_plugin_git_status_after.txt`
- `99_project_git_status_after.txt`
- `99_plugin_git_status_diff.txt` (delta относительно `00_plugin_git_status_before.txt`)
- `99_plugin_new_paths_stat.txt` (size/mtime для новых путей в plugin repo)
- `99_cleanup_policy.txt` (зафиксировать, что запуск был в режиме force-clean: `reset --hard` + `clean -fd`).
- удалить временный pre-status файл: `rm -f "/tmp/00_git_status_before.${TICKET}.${RUN_TS}.txt"`.
- Классификация write-safety:
  - `PASS`: delta отсутствует.
  - `FAIL(plugin_write_safety_violation)`: есть новые/изменённые пути в plugin repo и есть прямые runtime-evidence записи/редактирования plugin path в stage-логах.
  - `WARN(plugin_write_safety_inconclusive)`: delta есть, но прямого runtime-evidence нет (например, нулевые файлы в корне plugin repo с неочевидным источником); обязательна пометка как release-risk.

## 10) Финальный отчёт в чат

Для `full` обязательно:
- Таблица шагов `PASS/WARN/FAIL` (Happy path, каждый из шагов отдельно).
- Выбранная задача: `task_id`, `title`, `generated_slug_hint`, rationale.
- Что `NOT VERIFIED` и почему.
- Bug reports с severity.
- Ralph loop summary.
- Блок Flow Integrity Checks:
  - slug hygiene
  - plugin init evidence (`plugins`, `slash_commands`, `skills`)
  - canonical stage_result contract
  - stream-aware liveness probe (main log + stream jsonl/log)
  - review-spec report alignment (`05_review_spec_report_check_run<N>.txt`)
  - blocking_findings semantics (`REVISE` signal + `ralph` recoverable path)
  - `NOT VERIFIED` causes
  - plugin write-safety
- Дополнительный блок Env diagnostics:
  - plugin list snapshot
  - `init` evidence (`plugins`, `slash_commands`, `skills`)
  - `cwd` доказательство для stage-runner
- Список команд + пути к логам в `AUDIT_DIR`.

Для `smoke` допускается компактная версия отчёта.

Последняя строка:
`AUDIT_COMPLETE TST-001`
