### Шаг 6. Loop seed (только full)

Зачем: зафиксировать ручную стартовую итерацию.

Сделать:
- перед запуском шага установить локальные бюджеты seed-run:
  - `STEP6_IMPLEMENT_BUDGET_SECONDS=3600`
  - `STEP6_REVIEW_BUDGET_SECONDS=3600`
- один запуск `implement`, один запуск `review`.
- single-scope invariant: seed `implement` run обрабатывает ровно один work_item/scope; запуск второго iteration (`I<N+1>`) в том же `06_implement_run1.log` классифицируется как `seed_scope_cascade_detected`.
- classification policy шага 6: при `CLASSIFICATION_PROFILE=soft_default` terminal implement-blockers переводятся в `WARN` и шаги `7/8` продолжаются; одновременно обязательно сохранять strict-shadow telemetry: `primary_root_cause`, `strict_shadow_classification`, `softened=1`, `softened_from`, `softened_to`.
- при `CLASSIFICATION_PROFILE=strict` те же причины остаются terminal `NOT VERIFIED`.
- question retry для шага 6 запрещён (R1): если один из запусков уходит в BLOCK/questions, зафиксировать `NOT VERIFIED` и не делать второй attempt того же stage.
- если kill/hang — отмечать `NOT VERIFIED`.
- если `*_summary.txt` содержит `result_count=0` при валидном `init`, классифицировать как `NOT VERIFIED (no_top_level_result)` + `prompt-exec issue`.
- если в seed `implement` обнаружен deterministic test-env blocker (`Playwright executable missing`, browser install dependency, аналогичные runtime dependency gaps), выставлять `reason_code=tests_env_dependency_missing`; в `soft_default` публиковать `WARN` + strict-shadow, в `strict` — `NOT VERIFIED`.
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
  - `CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 $PLUGIN_DIR/skills/aidd-loop/runtime/loop_run.py --ticket $TICKET --max-iterations 6 --stream --step-timeout-seconds $LOOP_STEP_TIMEOUT_SECONDS --stage-budget-seconds $LOOP_STAGE_BUDGET_SECONDS --blocked-policy $BLOCKED_POLICY --recoverable-block-retries $RECOVERABLE_BLOCK_RETRIES`
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
- ожидать soft-continue без terminal blocked по research-причинам;
- в loop payload должны присутствовать telemetry-поля: `research_gate_softened=true`, `research_gate_soft_reason=<reason_code>`, `research_gate_soft_policy=always`.

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
- `08_qa_execution_log_check.txt` (проверка через `find` + `rg`, без raw-glob вроде `aidd/reports/qa/*tests*.log`, чтобы избежать `no matches found` в zsh).

### Шаг 99. Post-run write-safety

Зачем: проверить, что runtime не писал в plugin source.

Сделать:
- `99_plugin_git_status_after.txt`
- `99_project_git_status_after.txt`
- `99_plugin_git_status_diff.txt` (delta относительно `00_plugin_git_status_before.txt`)
- `99_plugin_new_paths_stat.txt` (size/mtime для новых путей в plugin repo)
- `99_cleanup_policy.txt` (зафиксировать, что запуск был в режиме force-clean: `reset --hard` + `clean -fd`).
- `99_workspace_layout_check.txt` (проверка отсутствия non-canonical root путей в workspace root: `docs/**|reports/**|config/**|.cache/**` вне `aidd/`).
- удалить временный pre-status файл: `rm -f "/tmp/00_git_status_before.${TICKET}.${RUN_TS}.txt"`.
- Классификация write-safety:
  - `PASS`: delta отсутствует.
  - `FAIL(plugin_write_safety_violation)`: есть новые/изменённые пути в plugin repo и есть прямые runtime-evidence записи/редактирования plugin path в stage-логах.
  - `WARN(plugin_write_safety_inconclusive)`: delta есть, но прямого runtime-evidence нет (например, нулевые файлы в корне plugin repo с неочевидным источником); обязательна пометка как release-risk.
  - `WARN(workspace_layout_non_canonical_root_detected)`: в workspace root появились non-canonical root пути вне `aidd/`; downstream результаты считать недетерминированными.

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
  - test contract SoT (`aidd/config/gates.json`) + policy-source scan (`01_gates_snapshot.json`, `01_test_policy_source_scan.txt`)
  - canonical stage_result contract
  - reason-code precedence (`project_contract_missing|tests_cwd_mismatch` как primary; `no_top_level_result` как secondary symptom)
  - runtime path hygiene (python-only runtime surfaces + отсутствие runtime decision dependency на `.claude/settings.json`)
  - stream-aware liveness probe (main log + stream jsonl/log)
  - review-spec report alignment (`05_review_spec_report_check_run<N>.txt`)
  - blocking_findings semantics (`REVISE` signal + `ralph` recoverable path)
  - `NOT VERIFIED` causes
  - topology/cwd evidence (`PRE-RUN invariant` + launcher precheck)
  - plugin write-safety
- Дополнительный блок Env diagnostics:
  - plugin list snapshot
  - `init` evidence (`plugins`, `slash_commands`, `skills`)
  - `cwd` доказательство для stage-runner
- Список команд + пути к логам в `AUDIT_DIR`.

Для `smoke` допускается компактная версия отчёта.

Последняя строка:
`AUDIT_COMPLETE TST-001`
