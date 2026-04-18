Сделать:
- `cd "$PROJECT_DIR"`;
- сохранить pre-status во временный файл: `/tmp/00_git_status_before.${TICKET}.${RUN_TS}.txt`;
- принудительно очистить workspace до `HEAD`:
  - `git reset --hard HEAD`
  - `git clean -fd`
- создать `AUDIT_DIR` после cleanup;
- скопировать pre-status в `AUDIT_DIR/00_git_status_before.txt`;
- сохранить post-status в `AUDIT_DIR/00_git_status_after.txt`;
- если cleanup не удался — `BLOCKER(clean_state_unavailable)` и stop;
- сохранить plugin status baseline в `00_plugin_git_status_before.txt`.

### Шаг 1. Preflight (fail-fast env)

Сделать:
- checkout audit branch;
- сохранить head/branch;
- определить `AUDIT_MODE`:
  - SKILL_FIRST если есть `skills/aidd-core/SKILL.md` и `skills/implement/SKILL.md`;
  - иначе `LEGACY_UNSUPPORTED` и stop как N/A;
- выполнить plugin-prompt path scan и сохранить `01_non_canonical_runtime_path_scan.txt`:
  - `rg -n "python3 skills/.*/runtime/" "$PLUGIN_DIR/skills/{implement,review,qa}/SKILL.md"`;
- зафиксировать `claude plugin list` в `01_plugin_list.txt`;
- зафиксировать `aidd/config/gates.json` в `01_gates_snapshot.json`; если файла нет — записать marker `not_available=1` в `01_gates_snapshot.json`;
- выполнить runtime test-policy source scan и сохранить `01_test_policy_source_scan.txt`:
  - `rg -n "CLAUDE_SETTINGS_PATH|\\.claude/settings\\.json" "$PLUGIN_DIR/skills" "$PLUGIN_DIR/hooks/format-and-test.sh"`;
  - если hit относится к runtime decision path, фиксировать `WARN(test_policy_source_non_canonical)` (не блокирует старт quality-аудита);
  - если scan недоступен, записать marker `not_available=1` в `01_test_policy_source_scan.txt`;
- выполнить healthcheck команду (`$PLUGIN_HEALTHCHECK_CMD`) через launcher;
- проверить `init`-событие healthcheck-лога на `plugins`, `slash_commands`, `skills`;
- извлечь install runtime path плагина и сохранить `01_plugin_runtime_path.txt`;
- выполнить runtime bootstrap probe в изолированном режиме и сохранить `01_runtime_bootstrap_probe.txt`:
  - `python3 -S <plugin_runtime_path>/skills/aidd-flow-state/runtime/set_active_stage.py --help`
  - `python3 -S <plugin_runtime_path>/skills/status/runtime/index_sync.py --help`
  - `python3 -S <plugin_runtime_path>/skills/review/runtime/review_report.py --help`
  - `python3 -S <plugin_runtime_path>/skills/aidd-rlm/runtime/rlm_slice.py --help`
- если bootstrap probe содержит `ModuleNotFoundError: No module named 'aidd_runtime'`, сохранить `01_runtime_bootstrap_blocker.txt` и продолжать аудит с маркировкой `NOT VERIFIED (runtime_bootstrap_missing)` для direct runtime fallback'ов.
- если любой пункт не выполнен, или получен `Unknown skill`, сохранить `01_env_blocker.txt` и **остановить аудит**.
- если получен `refusing to use plugin repository as workspace root`, исправить `cwd` на `PROJECT_DIR`, повторить healthcheck 1 раз, затем при повторном провале остановить аудит.

### Шаг 2. Baseline

Сделать:
- `cd "$PROJECT_DIR"`;
- `ls -la`;
- snapshot дерева `aidd` (или `aidd: missing`).

### Шаг 3. Task selection + IDEA_NOTE

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
- сформировать `IDEA_NOTE` из этого файла.

### Шаг 4. aidd-init

Готовность:
- `aidd/AGENTS.md`
- `aidd/docs/shared/stage-lexicon.md`

Если не готово:
- выполнить `/feature-dev-aidd:aidd-init` через launcher.

После:
- сохранить `04_aidd_tree_post.txt`.

### Шаг 5. Happy path

Общее правило для 5.1..5.5:
- каждый slash stage-run через launcher;
- при `Unknown skill` -> `ENV_BLOCKER(plugin_not_loaded)` и stop;
- question retry использовать только для реальных stage-вопросов/BLOCK;
- manual internal stage-chain/debug path не использовать как recovery для slash stage-команд 5.x.

#### 5.1 idea-new

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

Сделать:
- после `5.1` проверить top-level stage-return и `aidd/docs/prd/$TICKET.prd.md`;
- если обнаружены неотвеченные вопросы (`Q*`, пустые/`TBD` значения в `AIDD:ANSWERS`, `Status: draft`), выполнить question retry для `idea-new`;
- сохранить:
  - `05_idea_new_questions_raw.txt`
  - `05_idea_new_questions_normalized.txt`
  - `05_idea_new_answers.txt`
- после retry повторно снять `05_prd_head.txt`.

#### 5.2 researcher

Сделать:
- первый запуск ticket-only;
- при вопросах: retry;
- в non-interactive path ожидать bounded auto-recovery внутри researcher runtime;
- fallback допускается только если stage blocked/hang (не для `Unknown skill`):
  - `python3 $PLUGIN_DIR/skills/researcher/runtime/research.py --ticket $TICKET --auto --paths backend/src/main/java,frontend/src/pages --keywords github,analysis,flow`
- пометить fallback marker.

RLM artifacts check:
- must exist:
  - `${TICKET}-rlm-targets.json`
  - `${TICKET}-rlm-manifest.json`
  - `${TICKET}-rlm.worklist.pack.json`
- must NOT exist:
  - `${TICKET}-context.json`
  - `${TICKET}-targets.json`

#### 5.2.1 Step 5 Readiness Gate (hard-stop)

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
- если `readiness_gate=PASS` через `research_status=warn|pending`, зафиксировать `INFO(readiness_gate_research_softened)`.
- если `readiness_gate=FAIL`, выполнить один readiness-recovery цикл; при повторном `FAIL` пометить шаг 5 как `NOT VERIFIED (readiness_gate_failed)` и шаги `6/7/8` как `NOT VERIFIED (upstream_readiness_gate_failed)`.

#### 5.3 plan-new

Сделать:
- запускать только при `readiness_gate=PASS`;
- first run ticket-only;
- при вопросах: retry;
- если hang/kill: выполнить runtime probe
  - `python3 $PLUGIN_DIR/skills/plan-new/runtime/research_check.py --ticket $TICKET --expected-stage plan`
- если после bounded finalize остаётся `reason_code=rlm_status_pending` или `reason_code=rlm_links_empty_warn`, допускается soft-pass с `WARN(research_gate_softened)` и telemetry `policy=warn_continue`.

#### 5.3.1 Plan question-closure (после первого `plan-new`)

Сделать:
- если top-level stage-return `plan-new` явно требует закрыть `Q*`, выполнить ровно один question retry;
- сохранить:
  - `05_plan_new_questions_raw.txt`
  - `05_plan_new_questions_normalized.txt`
  - `05_plan_new_answers.txt`
- после retry снять `05_plan_head.txt`.

Anti-cascade:
- если после retry `plan-new` всё ещё требует закрыть вопросы:
  - шаг 5.3 = `NOT VERIFIED (plan_qna_unresolved)` + `prompt-flow gap`;
  - шаги `6/7/8` пометить `NOT VERIFIED (upstream_plan_qna_unresolved)` и перейти к шагу 99.

#### 5.4 review-spec

Сделать:
- запускать только при `readiness_gate=PASS`;
- first run ticket-only;
- при вопросах: retry;
- после каждого run сохранять `05_review_spec_report_check_run<N>.txt`:
  - `report_path`, `recommended_status`, `findings_count`, `open_questions_count`, `prd_findings_sync_needed`, `plan_findings_sync_needed`, `narrative_vs_report_mismatch`
- если есть unresolved `Q*`, повторить `/feature-dev-aidd:review-spec $TICKET` один раз.
- при `prd_findings_sync_needed=1` выполнить один sync-retry через `idea-new`, затем ещё раз `review-spec`.
- при `plan_findings_sync_needed=1` выполнить один sync-retry через `plan-new`, затем ещё раз `review-spec`.
- если hang/kill: runtime probe
  - `python3 $PLUGIN_DIR/skills/aidd-core/runtime/prd_review.py --ticket $TICKET`

#### 5.5 tasks-new

Сделать:
- запускать только при `readiness_gate=PASS`;
- если PRD не `READY` или есть unresolved `Q*`, выполнить required recovery (`review-spec`, findings-sync`) и только потом retry.
- first run ticket-only;
- при вопросах: retry;
- если tasks-new сообщает `upstream_blocker` или unresolved `Q*`, классифицировать как prompt-flow gap; один retry допускается только для `repairable_structure`.
- если `tasks-new` сообщает `AIDD:TEST_EXECUTION missing tasks`:
  - сохранить `05_tasklist_test_execution_probe.txt`;
  - если `tasks_list_count>0` (canonical executable contract) или есть `command|commands`, классифицировать как `INFO(tasklist_schema_parser_mismatch_recoverable)` и продолжать downstream stages.
- если `tasks-new` завершился `success|WARN`, но summary/log содержит manual/non-canonical recovery как primary path, фиксировать `WARN(prompt_flow_drift_non_canonical_stage_orchestration)` и не использовать manual path.
- если hang/kill: fallback
  - `python3 $PLUGIN_DIR/skills/tasks-new/runtime/tasks_new.py --ticket $TICKET`
- сохранить `05_tasklist_status_check.txt`.
- если после retry tasks-new остаётся `BLOCKED`, шаги 6/7 пометить `NOT VERIFIED` и перейти к 8/99.
