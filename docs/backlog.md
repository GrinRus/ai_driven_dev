# Product Backlog

> INTERNAL/DEV-ONLY: engineering wave planning and execution tracker.

_Revision note (2026-03-10): backlog ревизован по критерию удаления реализованных волн: удаляем волну только если acceptance подтверждён в текущем коде, релевантные regression/check команды зелёные, и нет открытых блокирующих зависимостей._

## Wave 117 — E2E quality follow-ups for TST-002 (2026-03-29)

Статус: plan. Основание — результаты quality e2e run 20260329T172731Z по тикету TST-002; цель — повысить качество кода и артефактов, генерируемых AIDD.

### Source run
- Audit dir: `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T172731Z`
- Base prompt: `/Users/griogrii_riabov/grigorii_projects/ai_driven_dev/docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`
- Feature final state: `NOT_REACHED`
- Overall quality gate: `FAIL`

- [ ] **W117-1 (P0) Enforce terminal stage result emission for idea-new** `skills/idea-new/SKILL.md`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/aidd_stage_launcher.py`:
  - добавить fail-fast ветку для `result_count=0` с deterministic terminal payload вместо зависания/tool-only sequence;
  - зафиксировать non-interactive contract для stage command completion (`done|blocked` с top-level result);
  - добавить regression fixture на сценарий `idea-new` с отсутствующим terminal result.
  **AC:** `idea-new` всегда эмитит terminal top-level result в stream-json run; `no_top_level_result` для этого сценария не воспроизводится.
  **Deps:** ->
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_e2e_prompt_contract.py`
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T172731Z/05_idea_new_run1.summary.txt`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T172731Z/05_idea_new_run2.summary.txt`
  **Effort:** M
  **Risk:** High

- [ ] **W117-2 (P1) Fix idea-new tool-use execution error path in non-interactive mode** `skills/idea-new/SKILL.md`, `agents/analyst.md`, `skills/aidd-flow-state/runtime/set_active_feature.py`:
  - исключить path, где stage остаётся в tool-use loop с `Sibling tool call errored` без terminal stage response;
  - добавить bounded retry policy для preflight tool actions внутри stage orchestration;
  - расширить diagnostics (`reason_code`, `tool_error_fingerprint`) для classifiable runner outcomes.
  **AC:** при tool execution error stage завершается deterministic BLOCKED payload, а не бесконечным stream/thinking.
  **Deps:** W117-1
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/test_prompt_lint.py`
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T172731Z/05_idea_new_run2.log`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T172731Z/05_stage_terminal_status.txt`
  **Effort:** M
  **Risk:** Medium

- [ ] **W117-3 (P1) Keep aidd-init slash orchestration self-contained (no external shell handoff)** `skills/aidd-init/SKILL.md`, `skills/aidd-init/runtime/init.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - убрать operator guidance, требующий выход из Claude и запуск внешнего shell script;
  - гарантировать completion `aidd-init` в canonical stage command path;
  - покрыть regression-проверкой на отсутствие external-shell handoff текста в stage terminal response.
  **AC:** `/feature-dev-aidd:aidd-init` выполняется end-to-end в non-interactive runner без external-terminal инструкции.
  **Deps:** ->
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/test_prompt_lint.py`
  **Evidence:** `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T172731Z/04_aidd_init_run1.log`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T172731Z/04_aidd_init_fallback_marker.txt`
  **Effort:** S
  **Risk:** Medium

## Wave 116 — E2E quality follow-ups for TST-002 (2026-03-29)

Статус: plan. Основание — результаты quality e2e run 20260329T135533Z по тикету TST-002; цель — повысить качество кода и артефактов, генерируемых AIDD.

### Source run
- Audit dir: /Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T135533Z
- Base prompt: /Users/griogrii_riabov/grigorii_projects/ai_driven_dev/docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt
- Feature final state: NOT_REACHED
- Overall quality gate: FAIL

- [ ] **W116-1 (P0) Stop non-converging seed stage command loops** skills/implement/SKILL.md, skills/implement/runtime/implement_run.py, tests/repo_tools/aidd_audit_runner.py:
  - детектировать повтор одного и того же command+stderr fingerprint в seed stage и завершать run fail-fast до исчерпания budget;
  - добавить module-aware cwd correction для gradle wrappers (backend-mcp/gradlew, backend/gradlew) либо deterministic terminal fail с reason_code;
  - гарантировать top-level stage result при terminal fail (result_count>=1 или canonical blocked payload).
  **AC:** шаг 6 не уходит в watchdog-only termination при повторяемой deterministic ошибке; no_top_level_result не воспроизводится для данного класса сбоев.
  **Deps:** -
  **Regression/tests:** python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_aidd_audit_runner.py.
  **Evidence:** /Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T135533Z/06_implement_run1.diagnostics.txt, /Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T135533Z/06_implement_termination_attribution.txt
  **Effort:** M
  **Risk:** High

- [ ] **W116-2 (P1) Enforce anti-stall runner policy for repeated deterministic errors** skills/aidd-loop/runtime/loop_step.py, skills/implement/runtime/implement_run.py, tests/repo_tools/test_e2e_prompt_contract.py:
  - ввести anti-stall threshold для repeated deterministic stderr/signature;
  - фиксировать explicit reason_code (например, seed_stage_non_converging_command) и recovery hint без бесконечных попыток;
  - отделить recoverable retry path от terminal no-progress path.
  **AC:** repeated deterministic errors классифицируются в bounded retries; run останавливается с явным reason_code без watchdog timeout.
  **Deps:** W116-1
  **Regression/tests:** python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py.
  **Evidence:** /Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T135533Z/06_implement_run1.log, /Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T135533Z/06_implement_run1.diagnostics.txt
  **Effort:** S
  **Risk:** Medium

- [ ] **W116-3 (P1) Tighten research readiness quality gate (no-TBD policy)** skills/researcher/templates/research.template.md, skills/researcher/runtime/research.py, templates/aidd/config/gates.json, tests/test_research_command.py:
  - добавить mandatory-section completeness checks (запрет placeholder TBD для ключевых блоков);
  - при placeholder-only output выставлять deterministic research_not_ready вместо downstream PASS;
  - обновить diagnostics для soft-warn, чтобы ready не выставлялся при пустом содержимом.
  **AC:** readiness gate не допускает downstream READY при research с placeholder-only секциями.
  **Deps:** -
  **Regression/tests:** python3 -m pytest -q tests/test_research_command.py tests/repo_tools/test_e2e_prompt_contract.py.
  **Evidence:** /Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/docs/research/TST-002.md, /Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T135533Z/05_precondition_block.txt
  **Effort:** S
  **Risk:** Medium

- [ ] **W116-4 (P2) Enforce tasklist report-pointer consistency and module-aware command hints** skills/tasks-new/templates/tasklist.template.md, skills/tasks-new/runtime/tasks_new.py, skills/implement/SKILL.md, skills/review/SKILL.md:
  - валидировать report pointers (reviewer, qa) перед выставлением READY;
  - для multi-module repos генерировать module-aware command hints вместо repo-root ./gradlew;
  - добавить explicit diagnostics в tasklist status check при несоответствии ссылок/команд.
  **AC:** tasklist READY не содержит ссылок на отсутствующие mandatory reports; build commands корректны для module-local wrappers.
  **Deps:** -
  **Regression/tests:** python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/test_prompt_lint.py.
  **Evidence:** /Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/docs/tasklist/TST-002.md, /Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/.aidd_audit/TST-002/20260329T135533Z/08_qa_status.txt
  **Effort:** S
  **Risk:** Medium


## Closed waves archive

- **Wave 112 (closed, archived 2026-03-29)**:
  - acceptance подтверждён по коду + test-contract evidence (`docs/wave-112-summary.md`);
  - повторная валидация на `main` (2026-03-29): `tests/repo_tools/ci-lint.sh` PASS, `tests/repo_tools/smoke-workflow.sh` PASS, `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py` PASS.
  - source-of-truth report: `docs/wave-112-summary.md`.

## P0-now — Risk-first queue (2026-03-29)

- `W113-1`
- `W113-8`
- `W113-24`
- `W113-26`
- `W113-27`
- `W114-1`
- `W114-2`
- `W113-9`
- `W113-3`
- `W113-4`
- `W114-3`
- `W114-4`

## Wave 114 — Consolidated P0-now backlog (2026-03-16)

_Статус: plan. Основание — risk-first reprioritization: задачи этой волны подняты в верхний приоритет `P0-now`._

- [ ] **W114-1 (P0-now) Harden stream-path telemetry when CLI does not emit stream path** `tests/repo_tools/aidd_stream_paths.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_stage_launcher.py`, `tests/repo_tools/test_aidd_audit_runner.py`:
  - стабилизировать extraction/fallback (`fallback_scan=1`) без потери liveness-классификации;
  - в отчётах фиксировать детерминированный marker, чтобы INFO/WARN не маскировал реальный terminal status;
  - добавить replay-guard на сигнатуру `stream_path_not_emitted_by_cli`.
  **AC:** stream-path anomaly классифицируется стабильно и не приводит к неоднозначной интерпретации run-статуса.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_stage_launcher.py tests/repo_tools/test_aidd_audit_runner.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W114-2 (P0-now) Resolve plugin write-safety inconclusive classification** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - убрать ложный WARN при появлении plugin repo untracked artifacts без прямого runtime write proof;
  - разделить `INFO(preexisting|manual artifact)` и `WARN(runtime write safety breach)` в post-run классификации;
  - зафиксировать инцидентный кейс `05_tasklist_test_execution_probe.txt` как regression fixture.
  **AC:** шаг 99 не выдаёт `plugin_write_safety_inconclusive` без доказанной runtime-записи в plugin root.
  **Deps:** W113-9
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W114-3 (P0-now) QA contract hardening: pin derive flow to `--source qa`** `skills/qa/SKILL.md`, `tests/test_prompt_lint.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - заменить неявное `derive tasks if needed` на deterministic conditional flow с canonical командой `tasks_derive.py --source qa --append --ticket <ticket>`;
  - запретить generic/unspecified `tasks_derive` вызовы в qa-stage guidance;
  - добавить regression tripwire на QA drift-сигнатуры derive без источника.
  **AC:** QA prompt/skill не оставляет неоднозначного derive пути; в QA flow не появляется source-less `tasks_derive` запуск.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W114-4 (P0-now) Research surface minimization: remove wildcard derive entrypoint from stage skill** `skills/researcher/SKILL.md`, `tests/test_prompt_lint.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - сузить `allowed-tools` для researcher, убрав generic `Bash(...tasks_derive.py *)` как внешнюю ручную поверхность и оставив derive orchestration только внутри canonical `research.py`;
  - закрепить в stage-skill, что handoff derive вызывается исключительно через runtime-controlled path (`rlm_status!=ready`);
  - добавить lint-tripwire на повторное появление wildcard derive инструмента в researcher skill.
  **AC:** researcher stage contract не экспонирует generic `tasks_derive` вызовы; handoff derive остаётся только deterministic runtime-шагом.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py tests/repo_tools/test_e2e_prompt_contract.py tests/test_research_command.py`.
  **Effort:** S
  **Risk:** Medium

## Wave 113 — Consolidated active backlog (2026-03-16)

_Статус: plan. Основание — mixed priority backlog: `P0-now` для risk-first задач и `P1` для remaining integration/doc/readiness work._

- [ ] **W113-1 (P0-now) Reopen `review_spec_report_mismatch` (narrative vs structured payload)** `skills/aidd-core/runtime/prd_review.py`, `skills/aidd-core/runtime/prd_review_section.py`, `tests/test_prd_review_agent.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - устранить рассинхрон `step 5.4` (narrative допускает proceed/warn, structured report рекомендует pending/open_questions);
  - зафиксировать structured payload как source-of-truth для gate/outcome классификации;
  - добавить regression guard на сигнатуру `review_spec_report_mismatch_narrative_vs_structured`.
  **AC:** в step-matrix отсутствует `step=5.4 status=WARN note=review_spec_report_mismatch_*` при валидном review-spec run.
  **Deps:** W113-8
  **Regression/tests:** `python3 -m pytest -q tests/test_prd_review_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W113-2 (P1) Canonicalize preflight artifact shape (`aidd.stage_result.v1`)** `skills/aidd-core/runtime/stage_actions_run.py`, `skills/aidd-flow-state/runtime/stage_result.py`, `tests/test_stage_actions_run.py`, `tests/test_qa_exit_code.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - убрать legacy preflight schema (`aidd.preflight.v1`) из seed stage-chain artifacts;
  - гарантировать единый contract shape для `stage.preflight.result.json` и terminal `stage.result.json`;
  - добавить contract-test на недопустимость legacy schema_version в preflight.
  **AC:** `stage.preflight.result.json` в loop artifacts всегда соответствует canonical `aidd.stage_result.v1` shape.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_stage_actions_run.py tests/test_qa_exit_code.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W113-3 (P0-now) Prevent cross-stage derive drift in implement/debug (`tasks_derive --source research`)** `skills/implement/SKILL.md`, `agents/implementer.md`, `skills/implement/runtime/implement_run.py`, `tests/test_prompt_lint.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - запретить implement-stage orchestration вызывать derive для чужого source (`research`) вне explicit handoff;
  - закрепить stage-local contract: implement/review/qa используют только свой canonical `--source`, если derive реально нужен;
  - добавить prompt/runtime tripwire на сигнатуру `tasks_derive.py --source research` внутри implement/debug flow.
  **AC:** implement/debug логи не содержат cross-stage derive вызовов; stage contract остаётся изолированным по source.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W113-4 (P0-now) Review contract hardening: explicit `tasks_derive --source review` only** `skills/review/SKILL.md`, `tests/test_prompt_lint.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - убрать source-less orchestration строку для `tasks_derive.py` в `review` и зафиксировать canonical вызов `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasks_derive.py --source review --append --ticket <ticket>`;
  - запретить fallback на вызовы без `--source` в review-stage guidance;
  - добавить lint/prompt tripwire на review-contract drift (`tasks_derive` без `--source review`).
  **AC:** review prompt/skill больше не допускает source-less `tasks_derive`; argparse-сигнатура `tasks_derive.py: error: the following arguments are required: --source` не воспроизводится в review-stage оркестрации.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W113-5 (P1) QA blocked reason-code completeness** `skills/qa/runtime/qa_parts/core.py`, `skills/qa/runtime/qa.py`, `skills/aidd-flow-state/runtime/stage_result.py`, `tests/test_qa_agent.py`, `tests/test_qa_exit_code.py`:
  - для blocked findings выставлять canonical `reason_code=blocking_findings`;
  - сохранить совместимость `schema=aidd.stage_result.v1` и evidence links contract.
  **AC:** blocked QA stage-result содержит непустой canonical reason code.

- [ ] **W113-6 (P1) Readiness recovery telemetry supersede markers** `tests/repo_tools/e2e_prompt/*`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - после успешного recovery (`readiness_gate=PASS`) помечать ранние `*_skipped_*`/`05_gate_outcome` как superseded;
  - убрать противоречивые terminal narrative при фактическом downstream execution.
  **AC:** итоговый step-5 audit status не содержит конфликтующих `NOT VERIFIED` при реально выполненных downstream шагах.

- [ ] **W113-7 (P1) Regression guard for TST-001 runs `20260308`/`20260309`** `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh`:
  - добавить контрактные проверки на сигнатуры: `set_stage.py` drift, `progress_cli --message`, repeated `exit 127`, invalid stage-result enum, empty QA reason code, stale readiness telemetry conflict;
  - отделить допускаемые WARN от terminal blockers в expected matrix.
  **AC:** перечисленные сигнатуры ловятся repo-tools до merge.

- [ ] **W113-8 (P0-now) `review-spec` narrative/report parity + pack-budget trimming** `skills/aidd-core/runtime/prd_review.py`, `skills/aidd-core/runtime/prd_review_section.py`, `tests/test_prd_review_agent.py`, `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - убрать расхождение narrative vs structured report при `recommended_status` вычислении;
  - стабилизировать top-N trimming для `action_items`, чтобы pack-budget exceed не приводил к contradictory verdicts;
  - зафиксировать report payload как единственный source-of-truth для recovery decisions.
  **AC:** `05_review_spec_report_check_run2.txt`-подобный `narrative_vs_report_mismatch=1` не воспроизводится при повторяемом run.
  **Deps:** -
  **Origin:** follow-up of former W112-10 (archived in closed Wave 112).
  **Regression/tests:** `python3 -m pytest -q tests/test_prd_review_agent.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W113-9 (P0-now) Workspace-layout classifier baseline awareness (pre-existing root paths)** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - отличать pre-existing root `docs|reports|config|.cache` от путей, созданных/изменённых в рамках текущего run;
  - по неизменённым pre-existing путям выдавать `INFO(preexisting_noncanonical_root)` вместо WARN;
  - сохранять WARN только для фактической мутации root non-canonical paths during run.
  **AC:** кейс из `99_workspace_layout_check.txt` не поднимает WARN при отсутствии delta во время аудита.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_aidd_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W113-10 (P1) Targeted memory retrieval (`memory_slice.py`) aligned with pack-first read discipline** `skills/aidd-memory/runtime/memory_slice.py`, `tests/test_memory_slice.py`:
  - добавить query-based slice для semantic/decisions memory;
  - сохранять slice artifacts в `aidd/reports/context/`.
  **AC:** memory slice работает как targeted evidence path без full-read.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_memory_slice.py`.
  **Effort:** S
  **Risk:** Low

### EPIC M2 — Integration into existing flow (research -> loop -> docops)

- [ ] **W113-11 (P1) Loop preflight/read policy integration for memory packs** `skills/aidd-loop/runtime/preflight_prepare.py`, `skills/aidd-loop/runtime/output_contract.py`, `hooks/context_gc/pretooluse_guard.py`, `tests/test_preflight_prepare.py`, `tests/test_output_contract.py`:
  - добавить memory artifacts в optional read chain/readmap для implement/review/qa;
  - разрешить policy-driven reads из `aidd/reports/memory/**`.
  **AC:** loop stages читают memory packs без policy-deny и с корректным read-order diagnostics.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_preflight_prepare.py tests/test_output_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W113-12 (P1) Context-GC working set enrichment with bounded memory excerpts** `hooks/context_gc/working_set_builder.py`, `templates/aidd/config/context_gc.json`, `tests/test_wave95_policy_guards.py`:
  - добавить short excerpts из semantic/decisions packs в auto working set;
  - сохранить global char limits и deterministic truncation.
  **AC:** session start получает memory summary без превышения context budget.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_wave95_policy_guards.py`.
  **Effort:** S
  **Risk:** Low

- [ ] **W113-13 (P1) Read-policy/templates/index alignment for memory-first retrieval** `skills/aidd-policy/references/read-policy.md`, `skills/aidd-core/templates/context-pack.template.md`, `skills/status/runtime/index_sync.py`, `skills/aidd-core/templates/index.schema.json`, `tests/test_status.py`:
  - добавить memory packs в canonical read order;
  - отразить memory artifacts в index/report discovery.
  **AC:** policy/templates/status-index не расходятся с Memory v2 contract.
  **Deps:** W113-11
  **Origin:** follow-up of former W112-19 (archived in closed Wave 112).
  **Regression/tests:** `python3 -m pytest -q tests/test_status.py tests/test_prompt_lint.py`.
  **Effort:** S
  **Risk:** Low

### EPIC M3 — Gates, regression suite, rollout

- [ ] **W113-14 (P1) Docs/changelog/operator guidance for Memory v2 rollout (breaking-only)** `AGENTS.md`, `README.md`, `README.en.md`, `templates/aidd/AGENTS.md`, `CHANGELOG.md`, `docs/memory-v2-rfc.md`:
  - обновить canonical docs под semantic/decision memory paths и rollout policy;
  - зафиксировать breaking rollout: без backward compatibility/backfill для legacy memory state.
  **AC:** docs/prompts/notes согласованы с runtime и тестовым контрактом Memory v2 и явно фиксируют breaking-only policy.
  **Deps:** -
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** S
  **Risk:** Low

- [ ] **W113-15 (P1) Update full flow prompt script for Memory v2 (`docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`)** `docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`, `tests/repo_tools/smoke-workflow.sh`:
  - обновить full-flow prompt script под Memory v2 read chain (`rlm.pack -> semantic.pack -> decisions.pack -> loop/context packs`);
  - убрать legacy compatibility/backfill шаги из сценария и acceptance flow.
  **AC:** full-flow prompt script соответствует Wave 101 контракту (breaking-only, no backfill) и используется как актуальный operator сценарий.
  **Deps:** W113-14
  **Regression/tests:** `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** S
  **Risk:** Low

### Wave 101 Critical Path

1. Baseline Memory v2 runtime/gates завершён и архивирован в closed Wave 112 (`docs/wave-112-summary.md`).
2. `W113-11` -> `W113-13` -> `W113-14` -> `W113-15`
3. `W113-16` -> `W113-17` -> `W113-18`

- [ ] **W113-16 (P1) Replace temporary soft gate with deterministic readiness promotion path** `skills/researcher/runtime/research.py`, `skills/aidd-rlm/runtime/rlm_finalize.py`, `skills/aidd-core/runtime/research_guard.py`, `tests/test_research_command.py`, `tests/test_research_check.py`:
  - убрать необходимость soft-continue за счёт детерминированного перехода `pending -> ready|warn(scoped)` в bounded auto-recovery;
  - нормализовать reason codes и next-action hints между researcher/research_guard/research_check;
  - обеспечить стабильный `rlm_status` в pack/worklist при повторных прогонах.
  **AC:** pipeline сходится без временного plan-softening в репрезентативных сценариях; `rlm_status_pending` остаётся только при реальных hard blockers.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_research_check.py`.
  **Effort:** M
  **Risk:** High

- [ ] **W113-17 (P1) Readiness gate/report alignment for `research_not_ready` diagnostics** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - фиксировать отдельные подпpичины `research_not_ready` (`pending`, `nodes_missing`, `links_empty_unscoped`, `pack_missing`) в precondition artifacts;
  - синхронизовать readiness diagnostics между stage-return и `05_precondition_block.txt`;
  - добавить проверку, что временный plan-soft mode не маскирует contract/env incidents.
  **AC:** оператор видит точную подпpичину `research_not_ready`; prompt-contract tests покрывают расхождения report vs stage-return.
  **Deps:** W113-16
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W113-18 (P1) Restore strict research gates после стабилизации** `templates/aidd/config/gates.json`, `skills/aidd-core/runtime/research_guard.py`, `skills/aidd-loop/runtime/loop_block_policy.py`, `tests/repo_tools/e2e_prompt/profile_{full,smoke}.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - вернуть strict-default policy (`downstream_gate_mode=strict` и strict readiness contract);
  - оставить runtime override через CLI/env для controlled rollout;
  - добавить strict-profile regression в prompt/runtime tests.
  **AC:** strict режим воспроизводимо блокирует warn/pending при отсутствии explicit soft override; soft rollout остаётся управляемым feature-flag.
  **Deps:** -
  **Regression/tests:** `python3 tests/repo_tools/build_e2e_prompts.py --check`, `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/test_research_check.py tests/test_loop_run.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W113-19 (P1) Review-pack recovery path hardening** `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_run.py`:
  - добавить детерминированный recovery path `retry_review_pack` для stage=`review` при review-pack recoverable reason;
  - исключить деградацию в `handoff_to_implement` для этой причины.
  **AC:** telemetry содержит `recovery_path=retry_review_pack`; bounded retry не переключает stage в implement.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W113-20 (P1) Regression coverage for targeted relax + timeout contract** `tests/test_loop_run.py`, `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/ci-lint.sh`:
  - покрыть кейсы: `ralph + review_pack_missing` recoverable, `strict + review_pack_missing` terminal, default step-timeout `3600`, наличие timeout flags в full prompt;
  - закрепить через CI-repro entrypoint.
  **AC:** unit + prompt-contract тесты стабильно ловят регрессии по policy/timeouts.
  **Deps:** W113-19
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** S
  **Risk:** Low

- [ ] **W113-21 (P1) Scope fallback confinement for stage-result lookup** `skills/aidd-loop/runtime/loop_step_stage_result.py`, `skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`:
  - ужесточить fallback selection: preferred scope authoritative; cross-scope fallback только с `scope_drift_recoverable` marker;
  - убрать повторяющийся `scope_key_mismatch_warn` noise при стабильном scope.
  **AC:** повторяемый fallback `iteration_id_I2 -> iteration_id_I1` без recoverable diagnostics не воспроизводится.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_run.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W113-22 (P1) Output contract signal precision (`read_log_missing`, `read_order_missing_loop_pack`)** `skills/aidd-loop/runtime/output_contract.py`, `skills/aidd-loop/runtime/loop_step_parts/core.py`, `tests/test_output_contract.py`, `tests/test_loop_step.py`, `tests/test_gate_workflow_preflight_contract.py`:
  - разделить реальные нарушения контракта и telemetry lag;
  - не поднимать `output_contract_warn` при валидном stream-evidence и корректном loop-pack read order.
  **AC:** WARN остаётся только при реальном contract gap, а не из-за неполного telemetry flush.
  **Deps:** W113-21
  **Regression/tests:** `python3 -m pytest -q tests/test_output_contract.py tests/test_loop_step.py tests/test_gate_workflow_preflight_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W113-23 (P1) PRD section parsing + cache-version hardening** `skills/aidd-flow-state/runtime/prd_check.py`, `skills/aidd-core/runtime/prd_review.py`, `tests/test_prd_ready_check.py`, `tests/test_prd_review_agent.py`:
  - завершать секции `AIDD:*` на любом markdown heading (`#{1,6}`), не только `##`;
  - versioned cache для `prd-check` (`cache_version`) и ignore legacy cache payload без актуальной версии.
  **AC:** nested headings не ломают readiness parsing; stale cache без `cache_version` не bypass-ит актуальную проверку.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prd_ready_check.py tests/test_prd_review_agent.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W113-24 (P0-now) Canonical `aidd/*` workspace layout enforcement (no root migration)** `skills/aidd-core/runtime/runtime.py`, `hooks/hooklib.py`, `hooks/context_gc/pretooluse_guard.py`, `tests/test_resources.py`, `tests/test_context_gc.py`, `tests/test_hook_rw_policy.py`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/e2e_prompt/profile_smoke.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - enforce canonical runtime artifacts only under `aidd/docs/**`, `aidd/reports/**`, `aidd/config/**`, `aidd/.cache/**`;
  - remove auto-migration of root paths (`docs/**|reports/**|config/**|.cache/**`) into `aidd/*`;
  - when `aidd/docs` is missing, return deterministic bootstrap error (`/feature-dev-aidd:aidd-init`) without mutating workspace root;
  - keep root-level non-canonical paths untouched by runtime; block root-level writes when `aidd/` exists.
  **AC:** full/smoke flows do not mutate root-level non-canonical artifacts; runtime and hooks resolve only canonical `aidd/*` paths.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_resources.py tests/test_context_gc.py tests/test_hook_rw_policy.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

- [ ] **W113-25 (P1) Canonical orchestration guard against internal manual recovery paths** `skills/qa/SKILL.md`, `skills/aidd-loop/SKILL.md`, `tests/test_prompt_lint.py`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - запретить рекомендации и primary recovery path с direct internal preflight/stage-result writes;
  - добавить prompt-lint tripwire на non-canonical ручной handoff внутри QA/loop orchestrations;
  - оставить только canonical stage-chain next actions в top-level stage-return.
  **AC:** prompt-lint ловит non-canonical recovery hints; e2e contract tests падают на manual stage-result path в primary action.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W113-26 (P0-now) Write-safety classifier baseline awareness for root non-canonical paths** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/test_audit_runner.py`:
  - отличать pre-existing root `docs|reports|config|.cache` от newly-created/modified during run;
  - при отсутствии delta классифицировать как `INFO(preexisting_noncanonical_root)`, не как WARN;
  - поднимать WARN только при фактической мутации root non-canonical paths во время прогона.
  **AC:** pre-existing неизменённый root path больше не приводит к WARN; delta/mutation остаётся WARN.
  **Deps:** W113-24
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_audit_runner.py tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W113-27 (P0-now) Stream-path telemetry completeness for stall classification** `tests/repo_tools/aidd_audit_runner.py`, `tests/repo_tools/e2e_prompt/profile_full.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - сделать fallback discovery обязательным при `stream_paths_missing` и пустом валидном наборе primary extraction;
  - фиксировать `stream_path_not_emitted_by_cli` как non-terminal noise при валидном top-level result;
  - синхронизовать liveness классификацию между prompt contract и audit runner.
  **AC:** ложный stall из-за пустого primary stream-path extraction не воспроизводится при живом stream/fallback evidence.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** S
  **Risk:** Medium

## Wave 115 — Parking backlog (merged from Wave 108 + Wave 100)

_Статус: plan. Основание — parking backlog с точечным повышением `P2` для rollout-critical задач (`W108-3`, `W108-5`) и prompt/test-run contract gap (`W100-12`)._

### Source: Wave 108
- [ ] **W108-1** Stabilize Researcher/RLM links for `no_symbols` cases (`skills/aidd-rlm/runtime/rlm_links_build.py`, `skills/researcher/runtime/research.py`, `tests/test_rlm_links_build.py`, `tests/test_research_command.py`):
  - снизить ложные `links_empty_reason=no_symbols` на реальных backend/frontend кодовых базах;
  - добавить диагностику (какие target files/symbol sources отброшены и почему).
  **AC:** на репрезентативных тикетах `research --auto` перестаёт массово застревать в `Status: warn` из-за `no_symbols`.

- [ ] **W108-2** Add observability for loop research soft-gate usage (`skills/aidd-loop/runtime/loop_run_parts/core.py`, `tests/test_loop_run.py`):
  - фиксировать отдельный telemetry marker для soft-continue на `research_status_invalid`;
  - добавить сводный отчёт частоты soft-gate с reason codes в loop artifacts.
  - Findings (2026-03-03): в policy probe `qa_tests_failed` `ralph` корректно маркирует `recoverable_blocked=1`, `retry_attempt=1`, `recovery_path=handoff_to_implement`; `strict` остаётся terminal blocked (`recoverable_blocked=0`).
    Evidence: `.aidd_audit/loop_policy/20260303T080709Z/findings_summary_20260303.md`.
  **AC:** по логам/pack можно детерминированно увидеть, где loop стартовал через soft-gate.

- [ ] **W108-3 (P2)** Return strict research gate after stabilization (`skills/aidd-loop/runtime/loop_run_parts/core.py`, `templates/aidd/config/gates.json`, `tests/test_loop_run.py`, `tests/repo_tools/e2e_prompt/profile_full.md`):
  - вернуть fail-fast блокировку `research_status_invalid` (через policy/config flag + rollout plan);
  - обновить e2e prompt contract и smoke/regression проверки.
  - Findings (2026-03-03): для non-recoverable причины (`review_pack_missing`) `strict` и `ralph` дают одинаковый terminal blocked (retry не запускается); rollback-план должен явно разделять recoverable/non-recoverable reason classes.
    Evidence: `.aidd_audit/loop_policy/20260303T080709Z/findings_summary_20260303.md`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/reports/loops/TST-001/cli.loop-run.20260303-080259.log`, `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/reports/loops/TST-001/cli.loop-run.20260303-080315.log`.
  **AC:** strict mode снова блокирует loop при неконсистентном research; есть подтверждённый rollout toggle и тесты.

- [ ] **W108-4** Keep loop scope-mismatch as non-terminal telemetry for post-review iteration rework (`skills/aidd-loop/runtime/loop_step_parts/core.py`, `tests/test_loop_step.py`):
  - сохранить soft-continue поведение при fallback `scope_key` mismatch в implement переходе;
  - фиксировать `scope_key_mismatch_warn`, `expected_scope_key`, `selected_scope_key` как обязательную telemetry поверхность.
  - Findings (2026-03-03): на `TST-001` mismatch больше не является terminal blocker; flow продолжает выполнение и упирается в downstream причину (`review_pack_missing`), что подтверждает корректность soft-mode только для mismatch gate.
    Evidence: `/Users/griogrii_riabov/grigorii_projects/ai_advent_challenge_new/aidd/reports/loops/TST-001/cli.loop-step.20260303-080315.log`.
  **AC:** loop не падает terminal на mismatch и продолжает итерацию, а mismatch детерминированно виден в payload/логах.

- [ ] **W108-5 (P2)** Re-introduce strict scope mismatch transition gate after canonical scope emit hardening (`skills/aidd-loop/runtime/loop_step_parts/core.py`, `skills/aidd-loop/runtime/loop_step_stage_chain.py`, `tests/test_loop_step.py`, `tests/repo_tools/e2e_prompt/profile_full.md`):
  - после стабилизации stage_result emission вернуть fail-fast блокировку `scope_mismatch_transition_blocked` за feature-flag/policy toggle;
  - покрыть rollout тестами и e2e профилями (strict vs temporary soft mode).
  - Findings (2026-03-03): synthetic probe с `blocking_findings` на review показывает нормализацию blocked→continue и downstream terminal по `review_pack_missing`; перед возвратом strict mismatch gate нужно зафиксировать границы нормализации warn-reasons.
    Evidence: `.aidd_audit/loop_policy/20260303T080709Z/findings_summary_20260303.md`.
  **AC:** strict profile снова блокирует non-authoritative fallback scope, rollout контролируется конфигом и подтверждён тестами.

### Source: Wave 100
### EPIC P — Task Graph (DAG) как источник для планирования
- [ ] **W100-1** `skills/aidd-flow-state/runtime/task_graph.py`, `aidd/reports/taskgraph/<ticket>.json` (или `aidd/docs/taskgraph/<ticket>.yaml`):
  - парсер tasklist → DAG:
    - узлы: iterations (`iteration_id`) + handoff (`id: review:* / qa:* / research:* / manual:*`);
    - поля: deps/locks/expected_paths/priority/blocking/state;
    - node id: `iteration_id` или `handoff id`; state выводится из чекбокса + (опционально) stage_result.
  - вычисление `ready/runnable` и топологическая проверка (cycles/missing deps).
  **AC:** из tasklist строится корректный DAG; есть список runnable узлов.

- [ ] **W100-2** `skills/aidd-flow-state/runtime/taskgraph_check.py` (или расширение `skills/aidd-flow-state/runtime/tasklist_check.py`):
  - валидировать: циклы, неизвестные deps, self-deps, пустые expected_paths (если требуется), конфликтующие locks (опционально).
  **AC:** CI/локальный чек ловит некорректные зависимости до запуска параллели.

### EPIC Q — Claim/Lock протокол для work items
- [ ] **W100-3** `skills/aidd-loop/runtime/work_item_claim.py`, `aidd/reports/locks/<ticket>/<id>.lock.json`:
  - claim/release/renew lock;
  - stale lock policy (ttl, force unlock);
  - в lock хранить `worker_id`, `created_at`, `last_seen`, `scope_key`, `branch/worktree`;
  - shared locks dir (например, `AIDD_LOCKS_DIR`) или orchestrator-only locks; атомарное создание (O_EXCL).
  **AC:** один узел не может быть взят двумя воркерами; stale locks диагностируются и снимаются по правилам; locks общие для всех воркеров.

### EPIC R — Scheduler: выбор runnable узлов под N воркеров
- [ ] **W100-4** `skills/aidd-loop/runtime/scheduler.py`:
  - выбрать набор runnable узлов на N воркеров:
    - учитывать deps,
    - учитывать `locks`,
    - учитывать пересечения `expected_paths` (конфликт → не запускать параллельно; конфликт = общий top-level group или префикс),
    - сортировка: blocking → priority → plan order.
  **AC:** scheduler отдаёт набор независимых work items; не выдаёт конфликтующие по locks/paths.

- [ ] **W100-5** `skills/aidd-loop/runtime/loop_pack.py`:
  - уметь генерировать loop pack по конкретному work_item_id, а не только “следующий из NEXT_3”;
  - сохранять pack в per‑work‑item пути (Wave 87 уже подготовил).
  **AC:** можно собрать loop pack для любого узла DAG по id; pack содержит deps/locks/expected_paths/size_budget/tests для выбранного узла.

### EPIC S — Parallel loop-run (оркестрация воркеров)
- [ ] **W100-6** `skills/aidd-loop/runtime/loop_run.py`:
  - добавить режим `--parallel N`:
    - получить runnable узлы от scheduler,
    - claim locks,
    - запустить N воркеров (каждый с явным `--work-item <id>` / `scope_key`),
    - собирать stage results и принимать решения (blocked/done/continue) по каждому узлу.
  **AC:** parallel loop-run запускает N независимых узлов и корректно реагирует на BLOCKED/DONE по каждому; определён контракт artifact root (shared vs per-worktree) и сбор результатов.

- [ ] **W100-7** `skills/aidd-loop/runtime/worktree_manager.py` (или `tests/repo_tools/worktree.sh`):
  - подготовка isolated рабочих директорий на воркера:
    - `git worktree add` / отдельные ветки,
    - единый шаблон именования веток,
    - cleanup.
  **AC:** каждый воркер работает в изолированном worktree; определён способ записи артефактов (shared root или сбор из worktrees).

### EPIC T — Консолидация результатов обратно в основной tasklist
- [ ] **W100-8** `skills/aidd-flow-state/runtime/tasklist_consolidate.py`, `skills/aidd-flow-state/runtime/tasklist_normalize.py`:
  - на основе stage_result + review_pack + tests_log:
    - отметить `[x]` для завершённых узлов,
    - обновить `AIDD:NEXT_3` из DAG runnable,
    - добавить `AIDD:PROGRESS_LOG` записи,
    - перенос/дедуп handoff задач.
  **AC:** после параллельного прогона tasklist обновляется детерминированно; без дублей; NEXT_3 корректен; дедуп handoff по стабильному id.

- [ ] **W100-9** `skills/aidd-observability/runtime/aggregate_report.py`:
  - агрегировать evidence в “ticket summary”:
    - ссылки на per‑work‑item tests logs,
    - список stage results,
    - сводка статусов узлов.
  **AC:** есть единый сводный отчёт по тикету и по узлам.

### EPIC U — Документация + регрессии
- [ ] **W100-10** `templates/aidd/docs/loops/README.md`, `templates/aidd/AGENTS.md`:
  - задокументировать parallel workflow:
    - deps/locks/expected_paths правила,
    - claim/release,
    - конфликт‑стратегию (paths overlap → serial),
    - policy: воркеры не редактируют tasklist в parallel‑mode (consolidate делает main).
  **AC:** понятная инструкция “как запускать parallel loop-run” + troubleshooting + policy для tasklist/артефактов.

- [ ] **W100-11** `tests/test_scheduler.py`, `tests/test_parallel_loop_run.py`, `tests/repo_tools/parallel-loop-regression.sh`:
  - тесты на DAG, scheduler, claim, параллельный раннер, консолидацию.
  **AC:** регрессии ловят гонки/перетирание артефактов/неверный выбор runnable; включены кейсы conflict paths/lock stale/worker crash.

- [ ] **W100-12 (P2) Parallel loop prompt/test-run contract** `tests/repo_tools/e2e_prompt/profile_full.md`, `docs/e2e/aidd_test_flow_prompt_ralph_script_full.txt`, `tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/smoke-workflow.sh`:
  - добавить operator-правила для `parallel loop-run` в e2e prompt profile/script (read order, handoff, fail-fast, rollback hints);
  - зафиксировать regression-tripwires в prompt-contract тестах для `--parallel`, worker coordination и artifact consistency;
  - добавить smoke-проверки для prompt path, чтобы parallel-mode guidance оставалась синхронной с runtime rollout.
  **AC:** parallel-mode имеет явный prompt/test-run contract; drift ловится prompt-contract/smoke тестами до merge.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** S
  **Risk:** Medium
