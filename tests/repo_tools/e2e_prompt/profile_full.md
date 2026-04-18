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

- `PROJECT_DIR=<absolute-path-to-target-workspace>`
- `PLUGIN_DIR=<absolute-path-to-plugin-repo>`
- `CLAUDE_PLUGIN_ROOT=$PLUGIN_DIR`
- `PRE-RUN invariant`: `realpath("$PROJECT_DIR") != realpath("$PLUGIN_DIR")`; иначе `ENV_MISCONFIG(cwd_wrong)` и stop.
- `TICKET=TST-001`
- `PROFILE=full|smoke` (default: `full`)
- `IDEA_NOTE=<формируется на шаге 3>`
- `LOOP_MODE=loop-run|loop-step` (default: `loop-run`)
- `BLOCKED_POLICY=strict|ralph` (default: `ralph`)
- `RECOVERABLE_BLOCK_RETRIES=<int>` (default: `2`)
- `LOOP_STEP_TIMEOUT_SECONDS=<int>` (default: `3600`)
- `LOOP_STAGE_BUDGET_SECONDS=<int>` (default: `3600`)
- `STEP6_IMPLEMENT_BUDGET_SECONDS=<int>` (default: `3600`)
- `STEP6_REVIEW_BUDGET_SECONDS=<int>` (default: `3600`)
- `AIDD_HOOKS_MODE=fast|strict` (default: `fast`)
- `CLAUDE_ARGS=--dangerously-skip-permissions`
- `STAGE_OUTPUT_MODE=stream-json|text` (default: `stream-json`)
- `LOG_POLL_SECONDS=15` (default: `15`)
- `CLAUDE_STREAM_FLAGS=--verbose --output-format stream-json --include-partial-messages`
- `CLAUDE_PLUGIN_FLAGS=--plugin-dir "$PLUGIN_DIR"`
- `PLUGIN_HEALTHCHECK_CMD=/feature-dev-aidd:status $TICKET`
- `SEVERITY_PROFILE=conservative` (default: `conservative`)
- `CLASSIFICATION_PROFILE=soft_default|strict` (default: `soft_default`)

## 3) Режимы

- `PROFILE=smoke`
  - Цель: быстрый health-check.
  - Выполняются шаги: `0,1,2,3,4,5,8,99`.
  - Шаги `6,7` помечаются `SKIPPED (profile=smoke)`.
- `PROFILE=full`
  - Цель: полный регрессионный аудит.
  - Выполняются шаги: `0,1,2,3,4,5,6,7,8,99`.

{{INCLUDE:includes/shared_rules_core.md}}
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
- R14.4: Если в stage-логе есть `ModuleNotFoundError: No module named 'aidd_runtime'` при запуске canonical runtime path, классифицировать как `flow bug (runtime_bootstrap_missing)` и фиксировать отдельным bug-item.
- R15: Если `*_run<N>.summary.txt` содержит `result_count=0` при валидном `init` (plugin/slash_commands/skills присутствуют), классифицировать как `prompt-exec issue (no_top_level_result)` и фиксировать отдельно.
- R15.1: Если `result_count` в summary отсутствует или пустой (`result_count=`), не трактовать это как `0` автоматически; сначала проверять top-level result/event в run-log, и только при подтверждённом отсутствии результата классифицировать `no_top_level_result`.
- R15.2: Для `loop-run` в `text`-режиме валидным top-level result считать JSON event `{"type":"result","schema":"aidd.loop_result.v1",...}` (в дополнение к строке summary `[loop-run] status=...`).
- R15.3: Для `review-spec` источником истины по finding/recommended status считать `aidd/reports/prd/<ticket>.json` (или `*.pack.json`); narrative top-level текста использовать только как supplementary telemetry.
- R15.4: Source-of-truth для test execution policy в runtime = `aidd/config/gates.json`; использование `.claude/settings.json`/`CLAUDE_SETTINGS_PATH` в runtime decision path классифицировать как `prompt-flow drift (non-canonical test policy source)`.
- R15.5: Если зафиксированы `reason_code=project_contract_missing|tests_cwd_mismatch` и одновременно `no_top_level_result`, reason-code считать primary причиной, а `no_top_level_result` — secondary symptom.
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
- R18.1: Readiness gate = `PASS` только при одновременном выполнении условий: `prd_status=READY`, `open_questions_count=0`, `answers_format=compact_q_values`, и `research_status=reviewed|ok|warn|pending` при наличии minimal RLM baseline.
- R18.1a: `compact_q_values` обязателен для retry payload в CLI (`AIDD:ANSWERS Q1=...; Q2="короткий текст"`), но не как обязательный persisted-формат секции `AIDD:ANSWERS` в PRD/plan/tasklist.
- R18.1b: Minimal RLM baseline для soft-readiness: существуют `aidd/reports/research/<ticket>-rlm-targets.json`, `...-rlm-manifest.json`, `...-rlm.worklist.pack.json`, `...-rlm.pack.json`; `aidd/reports/research/<ticket>-rlm.nodes.jsonl` непустой. `links` могут быть `warn|empty` и не являются terminal при baseline.
- R18.2: При `FAIL` readiness gate обязателен `reason_code` из набора `prd_not_ready|open_questions_present|answers_format_invalid|research_not_ready`; шаг 5 классифицируется как `NOT VERIFIED (readiness_gate_failed)` + `prompt-flow gap`.
- R18.2a: Если первичный readiness gate = `FAIL` с `reason_code=prd_not_ready|open_questions_present|answers_format_invalid`, перед terminal-классификацией обязателен ровно один readiness-recovery цикл: закрытие PRD-вопросов (question template + compact `AIDD:ANSWERS` retry для `idea-new`, если trigger валиден) -> `/feature-dev-aidd:review-spec <ticket>` -> пересчёт `05_precondition_block.txt`.
- R18.2b: Если `reason_code=research_not_ready`, допускается ровно один canonical researcher recovery/probe с последующим пересчётом `05_precondition_block.txt`.
- R18.2c: Если `readiness_gate=PASS` достигнут через `research_status=warn|pending` при minimal RLM baseline, фиксировать `INFO(readiness_gate_research_softened)` и продолжать downstream stages.
- R18.3: При readiness gate `FAIL` после исчерпания recovery-цикла шаги `6/7/8` помечаются как `NOT VERIFIED (upstream_readiness_gate_failed)` без запуска stage-команд.
- R18.4: Если `review-spec` top-level narrative и `aidd/reports/prd/<ticket>.json|*.pack.json` расходятся по числу/типу findings, фиксировать `prompt-exec issue (review_spec_report_mismatch)` и принимать recovery-решение по report payload; исключение: при `recommended_status=ready`, `findings_count=0`, `open_questions_count=0` классифицировать как `INFO(review_spec_report_mismatch_non_blocking)`.
- R18.5: Если `review-spec` вернул `WARN|NEEDS_REVISION`, unresolved `Q*` отсутствуют, запускать findings-sync cycle:
  - PRD findings (`aidd/reports/prd/<ticket>.json|*.pack.json`) -> один sync-retry `idea-new` с compact payload `AIDD:SYNC_FROM_REVIEW ...`;
  - Plan findings (`plan_status=NEEDS_REVISION|WARN` в review payload или plan-review report) -> один sync-retry `plan-new` с compact payload `AIDD:SYNC_FROM_REVIEW ...`;
  - после sync-retry обязательно повторить `/feature-dev-aidd:review-spec <ticket>` и пересчитать `05_precondition_block.txt`.
- R18.6: Если после findings-sync cycle `readiness_gate` остаётся `FAIL`, классифицировать как `NOT VERIFIED (findings_sync_not_converged)` + `prompt-flow gap` (без попытки manual stage edits).

{{INCLUDE:includes/shared_stage_run_policy.md}}

### 5.0 Additional full-profile launcher requirements

- Для каждого stage-run сохраняй `head` и `tail` в отдельные файлы (`*.head*.txt`, `*.tail.log`) и heartbeat (`*.heartbeat.log`).
- Для `stream-json` run дополнительно извлекай/сохраняй stream-пути (`*.stream.jsonl`, `*.stream.log`) в `AUDIT_DIR/<step>_stream_paths_run<N>.txt`.
- В `AUDIT_DIR/<step>_stream_paths_run<N>.txt` обязательно сохранять source-attribution для каждого пути (`init/header/metadata|fallback_scan`) и нормализованный абсолютный путь.
- Для stream-path extraction запрещён глобальный regex-scan по всему run-log; extract only from init JSON/control header sources and ignore `tool_result`/artifact text fragments.
- Если primary extraction stream-путей не дал результата, выполнить fallback discovery и явно зафиксировать это в `AUDIT_DIR/<step>_stream_paths_run<N>.txt`.
- Если primary extraction содержит невалидные абсолютные пути вне `PROJECT_DIR`, сохранить их с source-attribution как `stream_path_invalid`, но не использовать для liveness/stall.
- Если primary extraction содержит путь внутри `PROJECT_DIR`, но путь отсутствует на диске, сохранить его как `stream_path_missing` и исключить из liveness/stall.
- В `AUDIT_DIR/<step>_stream_paths_run<N>.txt` каждая запись должна быть в формате `source=<...> path=<abs_path_inside_project>|stream_path_invalid=<abs_path_outside_project>|stream_path_missing=<abs_path_inside_project_missing>`; при отсутствии валидных путей после fallback фиксировать `fallback_scan=1` и `stream_path_not_emitted_by_cli=1`.
- Если stage завершился валидным top-level result, но stream-пути не извлеклись и fallback discovery не нашёл свежих `*.stream.jsonl|*.stream.log`, фиксировать `INFO(stream_path_not_emitted_by_cli)` без инцидента.

### 5.2 Additional full-profile liveness rules

- Для **каждого** stage-run обязательно проверять рост логов каждые `LOG_POLL_SECONDS`:
  - `main log` (`size + tail`),
  - в `stream-json` также `stream_jsonl` (`size + tail`) и при наличии `stream_log`.
- Множество stream-файлов для liveness формируется из `*_stream_paths_run<N>.txt`; при неполном наборе из primary extraction обязателен fallback discovery перед классификацией stall.

### 5.3 Additional full-profile stall rules

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

### 5.4 Additional full-profile incident precedence

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
  - `reason_code=seed_scope_cascade_detected|tests_env_dependency_missing` -> terminal `prompt-exec issue` в `strict_shadow`; при `CLASSIFICATION_PROFILE=soft_default` для `06_implement` публикуется `WARN` + продолжаем `7/8`.
  - `reason_code=repeated_command_failure_no_new_evidence` -> bounded fail-fast без дальнейших guessed retries
  - `reason_code=project_contract_missing|tests_cwd_mismatch` -> terminal policy blocker; при одновременном `no_top_level_result` последний остаётся secondary telemetry
  - `stage_result_missing_or_invalid` + diagnostics `scope_fallback_stale_ignored|scope_shape_invalid` -> `scope_drift_recoverable`
- Отдельно `contract mismatch`:
  - `stage_result_missing_or_invalid` с diagnostics вида `invalid-schema` для fallback candidate (включая legacy stage-result schema payload)
- Только потом `flow bug`:
  - stage logic issue после подтверждения валидного env + retry/probe/fallback

### 5.5 Additional full-profile telemetry filters

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
- Для шага 6 (`implement` и `review`) budget считается по каждому запуску отдельно: `STEP6_IMPLEMENT_BUDGET_SECONDS` и `STEP6_REVIEW_BUDGET_SECONDS` (оба по умолчанию `3600`), без общего shared-window.

Если бюджет превышен:
- собрать диагностику (`ps`, `tail`, артефакты),
- остановить команду,
- пометить результаты шага как `NOT VERIFIED (killed)`.
- до превышения budget `kill` запрещён при наличии liveness (см. `R17`), кроме исключений `ENV_BLOCKER`/`silent stall`/process crash/user interrupt.

{{INCLUDE:includes/shared_question_retry.md}}

### 6.1 Additional full-profile retry rules

- retry-триггер разрешён только по текущему stage-return (финальный ответ stage-команды);
- для `idea-new` и `plan-new` retry-триггер также считается валидным, если top-level `success|WARN` явно требует ответить на `Q*`/закрыть незаполненные `AIDD:ANSWERS Q<N>=...` и перевести артефакт стадии в `READY`;
- не считать trigger-ом `Q*`/`AIDD:ANSWERS`/`Question` внутри вложенных артефактов (PRD/tasklist/reports/log excerpts), если stage-return сам не запрашивает ответ;
- количество `Q<N>` в retry определяется только актуальным top-level stage-return последнего run; illustrative примеры payload не являются фиксированным числом вопросов;
- сформируй `AIDD:ANSWERS` в `AUDIT_DIR/<step>_answers.txt` на основе уже собранных артефактов;
- дополнительно сохрани `AUDIT_DIR/<step>_questions_raw.txt` и `AUDIT_DIR/<step>_questions_normalized.txt` (нормализация `Q<N>` и choice-кодов перед retry);
- если source содержит `TBD`/пустые значения в `AIDD:ANSWERS`, нормализуй в `Q<N>=<token>` или `Q<N>="короткий текст"`; при невозможности нормализации фиксируй `reason_code=answers_format_invalid` и не выполняй retry;
- формат ответов для retry должен быть **компактным**: choice-коды/короткие фразы в одной строке, без длинного многострочного prose;
- если для части актуальных `Q<N>` нет сопоставленных ответов, фиксируй `question_retry_incomplete` и не публикуй partial compact payload как completed retry;
- рекомендуемый шаблон: `AIDD:ANSWERS Q1=C; Q2=B; Q3=C; Q4=A; Q5=C`.
- не вставляй в CLI многострочные ответы с большим количеством Unicode/пунктуации; если нужно сохранить детали, держи их в `<step>_answers.txt`, а в команду передавай сжатый вариант.
- в CLI передавай только нормализованный one-line payload вида `AIDD:ANSWERS Q1=...; Q2="короткий текст"`.
- для runtime retry используй canonical CLI-аргументы runtime (например, `--plan-path` для `plan-review-gate`) без legacy alias-аргументов.
- Если причина BLOCKED связана с unresolved PRD-вопросами (`Q*`) или `PRD Status != READY` (например `draft`):
  - сначала пройди `/feature-dev-aidd:review-spec <ticket>`,
  - затем перед повтором stage обязательно перепроверь `aidd/docs/prd/<ticket>.prd.md` (`Status:` и unresolved `Q*`);
  - если после `review-spec` PRD остаётся `Status != READY` и unresolved `Q*` отсутствуют, выполни findings-sync cycle:
    - PRD findings -> `/feature-dev-aidd:idea-new <ticket> <IDEA_NOTE> AIDD:SYNC_FROM_REVIEW ...`;
    - Plan findings -> `/feature-dev-aidd:plan-new <ticket> AIDD:SYNC_FROM_REVIEW ...`;
    - затем повтори `/feature-dev-aidd:review-spec <ticket>` и перепроверь `Status`;
  - если после findings-sync `Status != READY`, классифицируй как `NOT VERIFIED (findings_sync_not_converged)` + `prompt-flow gap` и не запускай stage, который требует `PRD READY`.
- Если stage-return содержит `Unknown skill` или отсутствуют feature-dev-aidd slash commands в `init`:
  - **не** применять question retry-шаблон;
  - классифицировать как `ENV_BLOCKER(plugin_not_loaded)` и остановить аудит.
- Если stage-return уводит в ручной preflight/ручную запись `stage.*.result.json`, предлагает direct вызов внутреннего stage-chain preflight entrypoint или рекомендует legacy stage aliases (`/feature-dev-aidd:planner`, `/feature-dev-aidd:tasklist-refiner`, `/feature-dev-aidd:implementer`, `/feature-dev-aidd:reviewer`) как основной recovery path/next action:
  - классифицировать как `prompt-flow drift (non-canonical stage orchestration)` и `policy_violation(stage_result_manual_write)` при попытке ручного stage-result write;
  - не выполнять этот manual path в e2e аудите;
  - зафиксировать `NOT VERIFIED` для шага и продолжить только по разрешённому сценарию.
- Если nested runtime-команда использует non-canonical путь `python3 skills/...` или runtime CLI-аргументы вне текущего контракта (пример: `--scope_key` вместо `--scope-key`, `--findings_summary`), классифицировать как `prompt-flow drift (runtime_cli_contract_mismatch)`; manual path не выполнять.

Примечание: это и есть ключ к “человекочитаемому” flow. Вопросы — часть happy path, а не исключение.

{{INCLUDE:includes/shared_must_read_task_catalog.md}}

{{INCLUDE:includes/profile_full_flow_setup.md}}

{{INCLUDE:includes/profile_full_loop_and_report.md}}
