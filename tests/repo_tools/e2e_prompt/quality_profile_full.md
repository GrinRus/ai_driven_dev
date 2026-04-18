Задача: **AIDD E2E Quality Audit (TST-002) + Final-state feature gate + Code/Artifact quality scoring + Backlog wave planning**  
База канона: **skill-first, python-only runtime, RLM-only research, no-fork stage orchestration, evidence-first quality audit**.

Роль: ты — один quality-аудитор-агент. Проведи **полный** e2e прогон AIDD flow в одном репозитории, доведи flow до terminal state по canonical AIDD path, затем оцени качество итогового кода и качество сгенерированных артефактов.  
**НЕ** исправляй проект и **НЕ** делай ручные правки `aidd/docs/**` или `aidd/reports/**` ради прохождения quality gate.  
Разрешённый plugin write во время этого prompt только один: `docs/backlog.md` и только после готового quality verdict по правилам шага `9`.

## 0) Reference Prompt And Priority

- Reference-only prompt source: `$PLUGIN_DIR/tests/repo_tools/e2e_prompt/profile_full.md`.
- Этот TST-002 prompt является **standalone-expanded** source of truth для текущего run: все шаги `0..8`, quality step `9` и write-safety step `99` описаны здесь полностью.
- Reference prompt читается для контекста и parity-проверки, но не является runtime dependency.
- Если между reference prompt и этим prompt есть конфликт, приоритет у **этого** prompt.
- Quality gate нельзя пропускать даже если inherited flow формально завершился; run считается завершённым только после шага `9` и backlog-aware шага `99`.

## 1) Канон и границы

- Stage content templates (SoT): `$PLUGIN_DIR/skills/*/templates/*`
- Workspace bootstrap source: `$PLUGIN_DIR/templates/aidd/**`
- Runtime workspace memory: `$PROJECT_DIR/aidd/**` (после `aidd-init`)
- Runtime API (canonical): `$PLUGIN_DIR/skills/*/runtime/*.py`
- Hooks/platform glue: `$PLUGIN_DIR/hooks/**`
- Product backlog file: `$PLUGIN_DIR/docs/backlog.md`
- `tools/*.sh`: retired (не использовать)
- `tools/*.py`: только repo-only tooling/stubs (если есть)
- Не делать ручные правки `aidd/docs/**` или `aidd/reports/**` ради улучшения score.
- Не исправлять target project в quality phase.
- Backlog wave должна описывать только **systemic AIDD improvements**; продуктовые проблемы target repo без AIDD root-cause в backlog не попадают.

## 2) Переменные

- `PROJECT_DIR=<project_dir>`
- `PLUGIN_DIR=<plugin_dir>`
- `CLAUDE_PLUGIN_ROOT=$PLUGIN_DIR`
- `PRE-RUN invariant`: `realpath("$PROJECT_DIR") != realpath("$PLUGIN_DIR")`; иначе `ENV_MISCONFIG(cwd_wrong)` и stop.
- `TICKET=TST-002`
- `BASE_PROMPT=$PLUGIN_DIR/tests/repo_tools/e2e_prompt/profile_full.md`
- `BACKLOG_PATH=$PLUGIN_DIR/docs/backlog.md`
- `PROFILE=full|smoke` (default: `full`)
- `QUALITY_PROFILE=full|smoke` (default: `full`)
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
- `QUALITY_GATE_POLICY=strict` (default: `strict`)
- `WAVE_WRITE_MODE=on-findings|always` (default: `on-findings`)
- `BACKLOG_SCOPE=aidd-only|mixed` (default: `aidd-only`)
- `QUALITY_SCORE_SCALE=0..3`
- `QUALITY_TOP_FINDINGS_LIMIT=<int>` (default: `10`)
- `QUALITY_BACKLOG_ITEM_LIMIT=<int>` (default: `7`)
- `ALLOW_PLUGIN_BACKLOG_WRITE=1`
- `BACKLOG_NEW_WAVE=<auto>`
- `QUALITY_FINAL_MARKER=QUALITY_AUDIT_COMPLETE`

## 3) Режимы

- `PROFILE=smoke`
  - Цель: быстрый health-check inherited flow.
  - Выполняются шаги: `0,1,2,3,4,5,8,9,99`.
  - Шаги `6,7` помечаются `SKIPPED (profile=smoke)`.
- `PROFILE=full`
  - Цель: полный регрессионный аудит inherited flow + quality gate.
  - Выполняются шаги: `0,1,2,3,4,5,6,7,8,9,99`.
- `QUALITY_PROFILE=smoke`
  - Шаг `9` выполняется в режиме `artifact-lite`: artifact consistency + final-state convergence.
  - Deep code review и запись backlog wave запрещены.
  - `wave_created=0`.
- `QUALITY_PROFILE=full`
  - Шаг `9` включает code quality, artifact quality, root-cause map, user improvement plan и backlog wave drafting/writing при наличии systemic findings.

{{INCLUDE:includes/shared_rules_core.md}}
- R13: Stage-result contract canonical-only: принимается только `schema=aidd.stage_result.v1` (alias через `schema_version` допустим только для canonical значения).
- R13.3: Прямая запись/редактирование `aidd/reports/loops/**/stage.*.result.json` запрещена; stage-result должен эмититься только canonical runtime/stage-chain путём.
- R14: Если в stage-логе есть запуск `python3 skills/.../runtime/*.py` из `PROJECT_DIR` и ошибка вида `can't open file .../skills/...`, классифицировать как `prompt-flow drift (non-canonical runtime path)`.
- R14.2: Для `runtime_path_missing_or_drift` применять fail-fast: immediate `blocked`, без guessed retries и без manual recovery path.
- R14.3: Если в stage-логе есть direct вызов внутреннего stage-chain preflight entrypoint вне canonical stage-chain, классифицировать как `prompt-flow drift (non-canonical stage orchestration)` и останавливать manual recovery для текущего шага.
- R15: Если `*_run<N>.summary.txt` содержит `result_count=0` при валидном `init`, классифицировать как `prompt-exec issue (no_top_level_result)`.
- R15.3: Для `review-spec` источником истины по finding/recommended status считать `aidd/reports/prd/<ticket>.json` (или `*.pack.json`); narrative top-level текста использовать только как supplementary telemetry.
- R15.4: Source-of-truth для test execution policy в runtime = `aidd/config/gates.json`; использование `.claude/settings.json`/`CLAUDE_SETTINGS_PATH` в runtime decision path классифицировать как `prompt-flow drift (non-canonical test policy source)`.
- R15.5: Если зафиксированы `reason_code=project_contract_missing|tests_cwd_mismatch` и одновременно `no_top_level_result`, reason-code считать primary причиной, а `no_top_level_result` — secondary symptom.
- R16: Для launcher избегать tokenization drift: не передавать флаги как один неразделённый токен; при первом фейле quoting/tokenization делать ровно один shell-safe retry с явными отдельными аргументами.
- R17: Early-kill prohibition (strict):
  - не останавливать stage-run до исчерпания budget этапа, если есть liveness (`main log` и/или stream-файлы растут);
  - до budget случаи `result_count=0`, token-limit, repeated nested tool errors классифицировать как `WARN(prompt-exec no_convergence_yet)`, а не `killed`;
  - исключения: `ENV_BLOCKER`, `silent stall`, явный process crash, user interrupt.
- R17.1: `kill` допускается только если не растут `main log` и все резолвленные stream-файлы более 20 минут.
- R17.2: Если завершение с `exit_code=143` произошло при `killed=0`, классифицируй как `ENV_MISCONFIG(parent_terminated|external_terminate)`.
- R17.3: Если завершение с `exit_code=143` произошло при `killed=1` и подтверждённом `watchdog_marker=1`, классифицируй как `NOT VERIFIED (killed)` + `prompt-exec issue (watchdog_terminated)`.
- R17.4: Severity profile `conservative`: `ENV_BLOCKER`, `ENV_MISCONFIG`, `contract_mismatch` остаются terminal; `stream_path_invalid|stream_path_missing` и telemetry-only mismatch не являются terminal сами по себе.
- R17.5: Для шага 7 `diff_boundary_violation` не считается terminal, если `OUT_OF_SCOPE`/sample-path состоят только из `.aidd_audit/**`; это `prompt-exec issue (diff_boundary_ephemeral_misclassified)`.
- R18: Перед запуском `plan-new`, `review-spec`, `tasks-new` и любого шага `6/7/8` обязателен readiness gate из `AUDIT_DIR/05_precondition_block.txt`.
- R18.1: Readiness gate = `PASS` только при одновременном выполнении условий: `prd_status=READY`, `open_questions_count=0`, `answers_format=compact_q_values`, и `research_status=reviewed|ok|warn|pending` при наличии minimal RLM baseline.
- R18.1a: `compact_q_values` обязателен для retry payload в CLI (`AIDD:ANSWERS Q1=...; Q2="короткий текст"`).
- R18.1b: Minimal RLM baseline для soft-readiness: существуют `aidd/reports/research/<ticket>-rlm-targets.json`, `...-rlm-manifest.json`, `...-rlm.worklist.pack.json`, `...-rlm.pack.json`; `aidd/reports/research/<ticket>-rlm.nodes.jsonl` непустой.
- R18.2: При `FAIL` readiness gate обязателен `reason_code` из набора `prd_not_ready|open_questions_present|answers_format_invalid|research_not_ready`; шаг 5 классифицируется как `NOT VERIFIED (readiness_gate_failed)` + `prompt-flow gap`.
- R18.2c: Если `readiness_gate=PASS` достигнут через `research_status=warn|pending` при minimal RLM baseline, фиксировать `INFO(readiness_gate_research_softened)` и продолжать downstream stages.
- R18.4: Если `review-spec` top-level narrative и `aidd/reports/prd/<ticket>.json|*.pack.json` расходятся по findings, фиксировать `prompt-exec issue (review_spec_report_mismatch)` и принимать recovery-решение по report payload; исключение: при `recommended_status=ready`, `findings_count=0`, `open_questions_count=0` классифицировать как `INFO(review_spec_report_mismatch_non_blocking)`.
- R18.5: Если `review-spec` вернул `WARN|NEEDS_REVISION`, unresolved `Q*` отсутствуют, запускать findings-sync cycle с compact payload `AIDD:SYNC_FROM_REVIEW ...`.
- R18.6: Если после findings-sync cycle `readiness_gate` остаётся `FAIL`, классифицировать как `NOT VERIFIED (findings_sync_not_converged)` + `prompt-flow gap`.

## 4.1 Дополнительные правила quality-аудита

- Q0: Сначала выполни standalone flow шагов `0..8`, потом запускай quality gate.
- Q1: Quality verdict строится только по evidence из run/logs/artifacts/code diff/tests; implicit success без evidence не засчитывать.
- Q2: Разделяй findings на классы `systemic_aidd_gap`, `product_output_gap`, `env_or_runner_gap`.
- Q3: При `BACKLOG_SCOPE=aidd-only` в backlog попадают только `systemic_aidd_gap` и допустимые `env_or_runner_gap`, требующие изменения AIDD repo.
- Q4: Product-specific gaps без AIDD root-cause оставлять только в `09_user_improvement_plan.md`.
- Q5: Пустую wave не создавать. Если actionable systemic findings = `0` и `WAVE_WRITE_MODE=on-findings`, backlog не менять.
- Q6: Все backlog items обязаны ссылаться на plugin repo paths (`skills/**`, `templates/**`, `tests/**`, `docs/**`, `hooks/**`, `agents/**`), а не на target project.
- Q7: Не заводить backlog items по шумовым nitpick-замечаниям без риска для качества и повторяемости.
- Q8: Мержить дублирующиеся findings в один wave-item, а не дробить на микрозадачи.
- Q9: Severity map:
  - `P0`: terminal quality blocker, broken acceptance, failing required regression, invalid artifact contract, final feature state not reached из-за AIDD gap.
  - `P1`: серьёзный quality gap, влияющий на correctness, maintainability или operator trust.
  - `P2`: важное, но не terminal улучшение.
  - `P3`: низкий приоритет; в backlog по умолчанию не писать.
- Q10: Backlog wave write допускается ровно один раз за run и только после `09_quality_gate.txt`.
- Q11: Post-run write-safety обязан считать изменение `BACKLOG_PATH` allowed delta только при валидной wave integrity check.
- Q12: Старые waves не удалять и не переписывать; только вставка новой wave.
- Q13: Новая wave использует следующий свободный номер `max(Wave NNN)+1`.
- Q14: Новую wave вставлять сразу после title/revision-note блока в начале `BACKLOG_PATH`.
- Q15: Если `BACKLOG_PATH` отсутствует, невалиден или max wave не парсится, классифицировать как `ENV_MISCONFIG(backlog_missing_or_unparseable)` и write не выполнять.

{{INCLUDE:includes/shared_stage_run_policy.md}}

{{INCLUDE:includes/shared_question_retry.md}}

{{INCLUDE:includes/shared_must_read_task_catalog.md}}

{{INCLUDE:includes/quality_profile_flow_setup.md}}

{{INCLUDE:includes/quality_profile_loop_quality.md}}

{{INCLUDE:includes/quality_profile_write_and_report.md}}
