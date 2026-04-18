### Шаг 6. Loop seed (только full)

Сделать:
- `STEP6_IMPLEMENT_BUDGET_SECONDS=3600`
- `STEP6_REVIEW_BUDGET_SECONDS=3600`
- один запуск `implement`, один запуск `review`;
- single-scope invariant: seed `implement` run обрабатывает ровно один work_item/scope; запуск второго iteration (`I<N+1>`) в том же `06_implement_run1.log` классифицируется как `seed_scope_cascade_detected`.
- policy под `soft_default`: terminal implement-blockers шага 6 публикуются как `WARN`; одновременно обязателен strict-shadow telemetry block: `primary_root_cause`, `strict_shadow_classification`, `softened=1`, `softened_from`, `softened_to`.
- policy под `strict`: те же причины остаются terminal `NOT VERIFIED`.
- question retry для шага 6 запрещён;
- если `result_count=0`, классифицировать как `NOT VERIFIED (no_top_level_result)` + `prompt-exec issue`;
- если в seed `implement` обнаружен deterministic test-env blocker (`Playwright executable missing`, browser install dependency, аналогичные runtime dependency gaps), выставлять `reason_code=tests_env_dependency_missing`; в `soft_default` публиковать `WARN` + strict-shadow, в `strict` — `NOT VERIFIED`;
- если в логах есть `python3 skills/.../runtime/*.py` + `can't open file`, классифицировать как `NOT VERIFIED (prompt_flow_drift_non_canonical_runtime_path)`.

Loop seed integrity checks:
- `06_active_after_review.json`
- `06_work_item_check.txt`
- `06_actions_tree.txt`
- `06_context_tree.txt`
- `06_stage_chain_logs_tree.txt`
- `06_loops_tree.txt`
- `06_marker_semantics_check.txt`

Fail-fast gate:
- если любой из preloop artifacts отсутствует/пустой, классифицировать как `NOT VERIFIED (preloop_artifacts_missing)` + `prompt-flow drift`;
- при `preloop_artifacts_missing` шаги 7 и 8 пометить `NOT VERIFIED` и перейти к шагу 99.

### Шаг 7. Auto-loop (только full)

Сделать:
- установить `AIDD_LOOP_RUNNER="claude --dangerously-skip-permissions"`;
- `loop-run` или `loop-step` через Python runtime:
  - `CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 $PLUGIN_DIR/skills/aidd-loop/runtime/loop_run.py --ticket $TICKET --max-iterations 6 --stream --step-timeout-seconds $LOOP_STEP_TIMEOUT_SECONDS --stage-budget-seconds $LOOP_STAGE_BUDGET_SECONDS --blocked-policy $BLOCKED_POLICY --recoverable-block-retries $RECOVERABLE_BLOCK_RETRIES`
  - или `CLAUDE_PLUGIN_ROOT="$PLUGIN_DIR" PYTHONPATH="$PLUGIN_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 $PLUGIN_DIR/skills/aidd-loop/runtime/loop_step.py --ticket $TICKET --stream`
- сохранить:
  - `07_loop_stream_liveness_check.txt`
  - `07_loop_runner_mode_check.txt`
  - `07_stage_result_contract_check.txt`
  - `07_recoverable_block_policy_check.txt`
  - `07_blocking_findings_policy_check.txt`
  - `07_result_count_check.txt`
- если в stream `init` видно `permissionMode=default` и `requires approval`, классифицировать как `ENV_MISCONFIG(loop_runner_permissions)` и выполнить ровно один retry.
- если `reason_code=blocking_findings`, использовать policy matrix v2 и проверять `recoverable_blocked`, `recovery_path`, `retry_attempt`.
- для parity с inherited prompt сохраняй telemetry marker `policy_matrix_v2`.
- если pre-iteration research gate вернул `reason_code=rlm_links_empty_warn|rlm_status_pending`, ожидать telemetry `research_gate_softened=true`, `research_gate_soft_reason`, `research_gate_soft_policy=always`.
- если blocked содержит `scope_fallback_stale_ignored`/`scope_shape_invalid`, ожидать recoverable `reason_code=scope_drift_recoverable` и recovery path `scope_drift_reconcile_probe`.

Loop runtime integrity checks:
- `07_scope_mismatch_check.txt`
- `07_id_review_tests_hits.txt`
- `07_python_only_surface_check.txt`
- `07_loop_stream_liveness_check.txt`
- `07_loop_runner_mode_check.txt`
- `07_stage_result_contract_check.txt`
- `07_blocking_findings_policy_check.txt`

Anti-cascade gate:
- если шаг 7 завершился terminal blocked с `reason_code=stage_result_missing_or_invalid` или `watchdog_terminated`, шаг 8 пометить `NOT VERIFIED (upstream_loop_stage_failed)` и перейти к шагу 99.

### Шаг 8. QA

Сделать:
- first run ticket-only;
- сохранить `08_test_execution_precheck.txt`;
- искать `&&`, `||`, `;` только в command-полях секции `AIDD:TEST_EXECUTION`;
- если в логе виден direct вызов non-canonical stage preflight runtime, классифицировать как `prompt-flow drift (non-canonical stage orchestration)` и manual recovery path не использовать;
- при вопросах: retry;
- если QA-run упал по `python3 skills/qa/runtime/qa.py` + `can't open file`, выполнить ровно один canonical fallback:
  - `python3 $PLUGIN_DIR/skills/qa/runtime/qa.py --ticket $TICKET`
- если hang/kill: fallback
  - `python3 $PLUGIN_DIR/skills/qa/runtime/qa.py --ticket $TICKET`
- сохранить `08_qa_execution_log_check.txt`.

### Шаг 9. Quality Gate + Improvement Plan + Backlog Wave Planning

#### 9.0 Общая цель

После шага `8`:
- определить, дошёл ли run до terminal feature state;
- оценить качество итогового кода и generated artifacts;
- отделить systemic AIDD gaps от product-specific gaps;
- подготовить user-facing improvement plan;
- при `QUALITY_PROFILE=full` и наличии systemic findings записать AIDD follow-up plan в `BACKLOG_PATH` как новую wave.

#### 9.1 Evidence inventory

Сохранить `AUDIT_DIR/09_quality_sources.txt` с источниками, которые реально использовались:
- base flow step artifacts (`03_*`, `05_*`, `06_*`, `07_*`, `08_*`, `99_*` если partial);
- canonical PRD/plan/tasklist/review/QA artifacts по тикету;
- git diff/status target project после run;
- test logs/evidence из review/qa;
- final loop artifacts и stage results;
- `BACKLOG_PATH` + parsed `max_wave_id`, если backlog читался.

Без `09_quality_sources.txt` quality verdict недействителен.

#### 9.2 Final-state convergence check

Сформируй `AUDIT_DIR/09_final_state_check.txt` с полями:
- `step5_status=<PASS|WARN|FAIL|NOT_VERIFIED>`
- `step6_status=<PASS|WARN|FAIL|SKIPPED|NOT_VERIFIED>`
- `step7_status=<PASS|WARN|FAIL|SKIPPED|NOT_VERIFIED>`
- `step8_status=<PASS|WARN|FAIL|NOT_VERIFIED>`
- `qa_report_status=<PASS|WARN|BLOCKED|missing>`
- `loop_terminal_status=<done|blocked|killed|missing|skipped>`
- `feature_final_state=<REACHED|NOT_REACHED>`
- `reason_code=<->`

`feature_final_state=REACHED` только если:
- inherited flow дошёл до terminal точки без unresolved `ENV_BLOCKER`, `ENV_MISCONFIG` или `contract_mismatch`;
- шаг 8 дал валидный QA result или canonical QA-equivalent terminal evidence;
- существует QA evidence/report из canonical path;
- нет unresolved terminal причин вида `watchdog_terminated`, `no_top_level_result`, `readiness_gate_failed`, `findings_sync_not_converged`, `plugin_not_loaded`, если они не были superseded downstream recovery.

Если `feature_final_state=NOT_REACHED`:
- quality audit всё равно выполнить;
- `overall_quality_gate=FAIL`;
- findings, мешающие convergence, поставить первыми.

#### 9.3 Code quality evaluation

Сформируй:
- `AUDIT_DIR/09_code_scorecard.json`
- `AUDIT_DIR/09_code_findings.md`
- `AUDIT_DIR/09_acceptance_trace.md`

Оценивай только feature-related diff/scope и ближайшие contract/tests paths.

Code dimensions:
- `acceptance_coverage`
- `correctness_and_regression`
- `contract_consistency`
- `maintainability`
- `robustness`
- `observability`

Формат scorecard entry:

```json
{
  "dimension": "acceptance_coverage",
  "score": 0,
  "verdict": "FAIL",
  "summary": "...",
  "evidence_paths": ["..."],
  "finding_ids": ["QF-01"]
}
```

Artifact scorecard использует тот же формат, например:

```json
{
  "dimension": "prd_quality",
  "score": 2,
  "verdict": "WARN",
  "summary": "...",
  "evidence_paths": ["..."],
  "finding_ids": ["QF-02"]
}
```

Шкала:
- `3` = strong/pass
- `2` = acceptable/warn-low
- `1` = weak/warn-high
- `0` = fail/blocker

`09_acceptance_trace.md` обязан трассировать:
- acceptance criterion -> code paths/tests/evidence -> verdict.

#### 9.4 Artifact quality evaluation

Сформируй:
- `AUDIT_DIR/09_artifact_scorecard.json`
- `AUDIT_DIR/09_artifact_findings.md`

Artifact dimensions:
- `prd_quality`
- `research_quality`
- `plan_quality`
- `tasklist_quality`
- `review_quality`
- `qa_quality`
- `cross_artifact_alignment`
- `operator_readability`

Обязательно проверить:
- `PRD ready / questions closed / acceptance explicit`;
- `plan actionable / no unresolved planning ambiguity`;
- `tasklist executable / bounded / readable by runner`;
- `review findings align with actual code and next action`;
- `qa report aligns with top-level QA outcome`;
- `cross-artifact consistency`;
- `operator readability`.

#### 9.5 Root-cause map

Собери findings в:
- `AUDIT_DIR/09_quality_findings.md`
- `AUDIT_DIR/09_quality_findings.json`

Для каждого finding обязательны поля:
- `finding_id` (`QF-01`, `QF-02`, ...)
- `title`
- `severity` (`P0|P1|P2|P3`)
- `class` (`systemic_aidd_gap|product_output_gap|env_or_runner_gap`)
- `quality_domain` (`code|artifact|flow|runner|docs`)
- `summary`
- `evidence_paths`
- `candidate_plugin_paths`
- `backlog_candidate` (`0|1`)

#### 9.6 User improvement plan

Составь `AUDIT_DIR/09_user_improvement_plan.md` со структурой:
- `Top systemic AIDD improvements`
- `Top product output improvements`
- `What to fix first`
- `What can wait`

Требования:
- кратко;
- action-oriented;
- не дублировать backlog wave дословно;
- максимум `QUALITY_TOP_FINDINGS_LIMIT` пунктов суммарно.

#### 9.7 Backlog wave drafting

Выполняется только если:
- `QUALITY_PROFILE=full`,
- `BACKLOG_SCOPE` допускает запись,
- `systemic backlog candidates > 0` или `WAVE_WRITE_MODE=always`.

Сначала сохрани:
- `AUDIT_DIR/09_backlog_before_head.txt`
- `AUDIT_DIR/09_backlog_parse.txt`

`09_backlog_parse.txt` должен содержать:
- `backlog_exists=0|1`
- `max_wave_id=<int|->`
- `new_wave_id=<int|->`
- `write_allowed=0|1`
- `systemic_candidates=<int>`
- `wave_created=0|1`
- `reason_code=<->`

Если `systemic_candidates=0` и `WAVE_WRITE_MODE=on-findings`:
- `wave_created=0`
- backlog не менять
- сохранить `AUDIT_DIR/09_backlog_wave_write.txt` с `reason_code=no_systemic_findings`

Если wave создаётся:
1. Вычисли `BACKLOG_NEW_WAVE = max(Wave NNN)+1`.
2. Сгенерируй `AUDIT_DIR/09_backlog_wave_draft.md`.
3. Вставь draft в `BACKLOG_PATH` сразу после title/revision-note блока.
4. Сохрани `AUDIT_DIR/09_backlog_after_head.txt`.
5. Сохрани `AUDIT_DIR/09_backlog_wave_write.txt` с полями:
   - `wave_created=1`
   - `wave_id=W<NNN>`
   - `items_written=<int>`
   - `insert_mode=after_revision_note`
   - `allowed_plugin_write=BACKLOG_PATH`

Формат новой wave:

```md
## Wave <NNN> — E2E quality follow-ups for <TICKET> (<YYYY-MM-DD>)

Статус: plan. Основание — результаты quality e2e run <RUN_TS> по тикету <TICKET>; цель — повысить качество кода и артефактов, генерируемых AIDD.

### Source run
- Audit dir: `<AUDIT_DIR>`
- Base prompt: `<BASE_PROMPT>`
- Feature final state: `<REACHED|NOT_REACHED>`
- Overall quality gate: `<PASS|WARN|FAIL>`

- [ ] **W<NNN>-1 (P1) <short title>** `<plugin/path1>`, `<plugin/path2>`:
  - <concrete fix 1>
  - <concrete fix 2>
  - <concrete fix 3>
  **AC:** <acceptance criteria>
  **Deps:** <wave/task ids or ->>
  **Regression/tests:** `<commands>`
  **Evidence:** `<AUDIT_DIR/...>`
  **Effort:** S|M|L
  **Risk:** Low|Medium|High
```

Wave item rules:
- не более `QUALITY_BACKLOG_ITEM_LIMIT` items;
- только `P0|P1|P2`;
- сортировка `P0 -> P1 -> P2`;
- каждый item обязан ссылаться на конкретные plugin repo files;
- каждый item обязан иметь `AC`, `Deps`, `Regression/tests`, `Evidence`, `Effort`, `Risk`;
- `Evidence` ссылается только на реальные artifacts текущего run.

#### 9.8 Quality gate calculation

Сохрани `AUDIT_DIR/09_quality_gate.txt` с полями:
- `feature_final_state=<REACHED|NOT_REACHED>`
- `code_quality_gate=<PASS|WARN|FAIL>`
- `artifact_quality_gate=<PASS|WARN|FAIL>`
- `systemic_aidd_findings=<int>`
- `product_output_findings=<int>`
- `env_or_runner_findings=<int>`
- `backlog_candidates=<int>`
- `wave_created=<0|1>`
- `wave_id=<WNNN|->`
- `overall_quality_gate=<PASS|WARN|FAIL>`
- `reason_code=<->`

Gate rules:
- `code_quality_gate=FAIL`, если есть любой `P0|P1` code finding или required regression/test signal красный.
- `artifact_quality_gate=FAIL`, если есть любой `P0|P1` artifact/flow finding или unresolved readiness ambiguity.
- `overall_quality_gate=PASS`, только если:
  - `feature_final_state=REACHED`,
  - `code_quality_gate=PASS`,
  - `artifact_quality_gate=PASS`,
  - `systemic_aidd_findings=0`,
  - нет `P0|P1` `product_output_gap`.
- `overall_quality_gate=WARN`, если `feature_final_state=REACHED`, нет `P0|P1`, но есть `P2` findings и/или создана backlog wave по non-terminal systemic improvements.
- `overall_quality_gate=FAIL`, если:
  - `feature_final_state=NOT_REACHED`, или
  - есть любой `P0|P1`, или
  - backlog должен был быть создан, но write failed.

#### 9.9 Runner contract и финальный отчёт

В чат-отчёте после шага 9 обязательно выведи:
- inherited step matrix (`0..8` + `99`);
- отдельный quality matrix:
  - final feature state,
  - code quality gate,
  - artifact quality gate,
  - overall quality gate;
- inherited flow integrity highlights (без отдельного нового блока):
  - test contract SoT (`aidd/config/gates.json`) + policy-source scan (`01_gates_snapshot.json`, `01_test_policy_source_scan.txt`);
  - reason-code precedence (`project_contract_missing|tests_cwd_mismatch` как primary; `no_top_level_result` как secondary symptom);
  - runtime path hygiene (python-only runtime surfaces + отсутствие runtime decision dependency на `.claude/settings.json`);
  - topology/cwd evidence (`PRE-RUN invariant` + launcher precheck);
- список top `systemic_aidd_gap`;
- список top `product_output_gap`;
- новый `wave_id` и item ids, если wave создана;
- что именно предложено пользователю как дальнейшие доработки;
- пути к key artifacts (`09_*` + base audit dir).
