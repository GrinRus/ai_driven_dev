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
- зафиксировать `aidd/config/gates.json` (если есть) в `01_gates_snapshot.json`; если файла нет — записать marker `not_available=1` в `01_gates_snapshot.json`.
- выполнить runtime test-policy source scan и сохранить `01_test_policy_source_scan.txt`:
  - `rg -n "CLAUDE_SETTINGS_PATH|\\.claude/settings\\.json" "$PLUGIN_DIR/skills" "$PLUGIN_DIR/hooks/format-and-test.sh"`;
  - если hit относится к runtime decision path, фиксировать `WARN(test_policy_source_non_canonical)` (не блокирует старт аудита);
  - если scan недоступен, записать marker `not_available=1` в `01_test_policy_source_scan.txt`.
- выполнить healthcheck команду (`$PLUGIN_HEALTHCHECK_CMD`) через launcher из секции 5.0;
- проверить `init`-событие healthcheck-лога:
  - есть `plugins: [{"name":"feature-dev-aidd"...}]`;
  - есть `slash_commands` с `feature-dev-aidd:status`;
  - есть `skills` с `feature-dev-aidd:*`.
- извлечь install runtime path плагина из `init.plugins[].path` и сохранить `01_plugin_runtime_path.txt`.
- выполнить runtime bootstrap probe в изолированном режиме (без внешнего `PYTHONPATH`/site-packages) и сохранить `01_runtime_bootstrap_probe.txt`:
  - `python3 -S <plugin_runtime_path>/skills/aidd-flow-state/runtime/set_active_stage.py --help`
  - `python3 -S <plugin_runtime_path>/skills/status/runtime/index_sync.py --help`
  - `python3 -S <plugin_runtime_path>/skills/review/runtime/review_report.py --help`
  - `python3 -S <plugin_runtime_path>/skills/aidd-rlm/runtime/rlm_slice.py --help`
- если bootstrap probe содержит `ModuleNotFoundError: No module named 'aidd_runtime'`:
  - классифицировать как `flow bug (runtime_bootstrap_missing)`;
  - сохранить `01_runtime_bootstrap_blocker.txt`;
  - продолжать аудит разрешено, но любой fallback/probe через direct runtime path маркировать `NOT VERIFIED (runtime_bootstrap_missing)`.
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
- если обнаружены неотвеченные вопросы (`Q*`, пустые/`TBD` значения в `AIDD:ANSWERS`, `Status: draft` при явном требовании stage-return закрыть вопросы), выполнить question retry для `idea-new` по шаблону секции 6;
- сохранить артефакты question-cycle:
  - `05_idea_new_questions_raw.txt`
  - `05_idea_new_questions_normalized.txt`
  - `05_idea_new_answers.txt`
- `AIDD:ANSWERS` для retry передавать compact one-line payload; использовать `Q<N>=<token>` или `Q<N>="короткий текст"` (опираясь на `Default:`/варианты в PRD);
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
  - `answers_format=<compact_q_values|invalid>`
  - `research_status=<reviewed|ok|pending|warn|invalid>`
  - `research_warn_scope=<none|links_empty_non_blocking|minimal_baseline_soft|invalid>`
  - `readiness_gate=<PASS|FAIL>`
  - `reason_code=<prd_not_ready|open_questions_present|answers_format_invalid|research_not_ready|->`
- запуск `5.3/5.4/5.5` допускается только при `readiness_gate=PASS`.
- если `readiness_gate=PASS` через `research_status=warn|pending` при minimal baseline (`research_warn_scope=minimal_baseline_soft|links_empty_non_blocking`), зафиксировать `INFO(readiness_gate_research_softened)` и продолжать downstream stages.
- если `readiness_gate=FAIL`:
  - в `05_precondition_block.txt` обязательно заполнить конкретный `reason_code`;
  - если `reason_code=prd_not_ready|open_questions_present|answers_format_invalid`, выполнить ровно один readiness-recovery цикл:
    1) закрыть PRD/plan-вопросы через question template (включая compact retry для `idea-new` и `plan-new`, если trigger валиден);
    2) выполнить `/feature-dev-aidd:review-spec $TICKET` (ticket-only, при вопросах один retry);
    3) перепроверить PRD header (`Status:` + unresolved `Q*`) и пересчитать `05_precondition_block.txt`.
  - если `reason_code=research_not_ready`, выполнить ровно один canonical recovery/probe для researcher и пересчитать `05_precondition_block.txt`.
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
- для downstream probes:
  - `plan/review/qa`: если после bounded finalize остаётся `reason_code=rlm_status_pending` или `reason_code=rlm_links_empty_warn`, допускается soft-pass (`exit_code=0`) с `WARN(research_gate_softened)` и telemetry `policy=warn_continue`; это не `research_not_ready` само по себе при minimal baseline.
- `baseline_missing` в downstream probes считать drift/contract mismatch.
- классифицировать как prompt-exec issue до probe.

#### 5.3.1 Plan question-closure (после первого `plan-new`)

Зачем: закрыть вопросы плана до запуска downstream стадий, даже если первый `plan-new` завершился `success|WARN`.

Сделать:
- если top-level stage-return `plan-new` явно требует закрыть `Q*`/незаполненный `AIDD:ANSWERS`, выполнить ровно один question retry по шаблону секции 6;
- сохранить артефакты:
  - `05_plan_new_questions_raw.txt`
  - `05_plan_new_questions_normalized.txt`
  - `05_plan_new_answers.txt`
- передавать в CLI только compact one-line payload: `AIDD:ANSWERS Q1=...; Q2="короткий текст"`;
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
  - `report_path`, `recommended_status`, `findings_count`, `open_questions_count`, `prd_findings_sync_needed`, `plan_findings_sync_needed`, `narrative_vs_report_mismatch`;
- если итог review-spec = `WARN/BLOCKED` и в отчёте есть unresolved `Q*`:
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
  - выполнить `/feature-dev-aidd:review-spec $TICKET` (ticket-only, при вопросах один retry),
  - затем повторно проверить PRD header (`Status:` + unresolved `Q*`); если PRD всё ещё не `READY`, классифицировать как `NOT VERIFIED (findings_sync_not_converged)` + `prompt-flow gap`, пометить шаг 5.5 `NOT VERIFIED` и не запускать `tasks-new`.
- first run ticket-only;
- при вопросах: retry;
- если tasks-new сообщает `upstream_blocker` / unresolved `Q*`:
  - классифицировать как prompt-flow gap (не code bug на первом проходе);
  - перед retry снова проверить PRD header (`Status:` + unresolved `Q*`); если `Status != READY`, сначала выполнить findings-sync cycle (idea-new/plan-new по `05_review_spec_report_check_run<N>.txt`), затем повторно проверить `Status`;
  - если после findings-sync `Status != READY`, классифицировать как `NOT VERIFIED (findings_sync_not_converged)` + `prompt-flow gap` и не выполнять retry `tasks-new`;
  - иначе повторить `/feature-dev-aidd:tasks-new $TICKET` один раз только при `repairable_structure`;
- если `tasks-new` сообщает `AIDD:TEST_EXECUTION missing tasks`:
  - сохранить `05_tasklist_test_execution_probe.txt` с полями `tasks_key_present`, `tasks_list_count`, `commands_key_present`, `classification`;
  - если probe подтверждает `tasks_list_count>0` (canonical executable contract) или наличие `command|commands` entries, классифицировать как `INFO(tasklist_schema_parser_mismatch_recoverable)` и продолжать downstream stages (не terminal blocker);
  - если probe не подтверждает исполняемые test entries, оставлять классификацию как `prompt-flow blocker`.
- если `tasks-new` завершился `success|WARN`, но `summary/log` содержит рекомендации manual/non-canonical recovery как primary path:
  - классифицировать как `WARN(prompt_flow_drift_non_canonical_stage_orchestration)`;
  - не переходить на manual path, продолжать сценарий.
- если hang/kill: fallback
  - `python3 $PLUGIN_DIR/skills/tasks-new/runtime/tasks_new.py --ticket $TICKET`
- сохранить `05_tasklist_status_check.txt`.
- если после retry tasks-new остаётся `BLOCKED`:
  - пометить как `prompt-flow blocker`,
  - шаги 6/7 пометить `NOT VERIFIED` и перейти к 8/99.
