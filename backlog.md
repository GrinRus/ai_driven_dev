# Product Backlog

## Wave 96 — SKILL-first migration program (consolidated)

_Статус: новый, приоритет 0. Цель — перевести runtime на SKILL-first модель, объединить бывшие W96+W97 и закрыть carry-over риски без breaking change в wave-1._

### Baseline (code snapshot 2026-02-08)

- [ ] **W96-0 (P0) Baseline audit snapshot + migration board refresh** `backlog.md`, `tools/entrypoints-bundle.txt`, `tools/tools_inventory.py`, `tests/repo_tools/lint-prompts.py`:
  - зафиксировать baseline факты в wave (для контроля прогресса миграции): `review-spec` как public stage, `review-plan/review-prd` как internal substage; 46 `tools/*.sh` с python shebang; массовые ссылки `skills/*/SKILL.md` и `agents/*.md` на `tools/*`;
  - синхронизировать checklist миграции с фактическими consumers из inventory/rg (skill/agent/hook/test/docs);
  - определить порядок миграции по stage (idea -> plan -> review-spec -> researcher -> qa -> status -> shared).
  **AC:** backlog отражает единый SKILL-first план с актуальными зависимостями и без отдельного Wave 97.
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `AIDD_ALLOW_PLUGIN_WORKSPACE=1 CLAUDE_PLUGIN_ROOT=$PWD python3 tools/tools_inventory.py --repo-root . --output-json /tmp/aidd_tools_inventory.json --output-md /tmp/aidd_tools_inventory.md`.
  **Effort:** S
  **Risk:** Low

### EPIC A — Contracts & stage lexicon

- [ ] **W96-1 (P0) Stage lexicon contract (`review-spec` public, `review-plan/review-prd` internal)** `AGENTS.md`, `templates/aidd/AGENTS.md`, `templates/aidd/docs/tasklist/template.md`, `tools/set_active_stage.py`, `tools/context_map_validate.py`, `README.md`, `README.en.md`:
  - зафиксировать единый словарь стадий: `review-spec` как публичная команда/стадия; `review-plan` и `review-prd` как internal substage;
  - описать alias/переходы и правила записи `active_stage`, чтобы не было drift между docs/templates/runtime;
  - обновить tasklist/template/gates подсказки под новую терминологию.
  **AC:** во всех SoT-документах и runtime-валидации единая stage-терминология без противоречий.
  **Regression/tests:** `tests/test_set_active_stage.py` (или эквивалент), `tests/repo_tools/lint-prompts.py`, smoke `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** M
  **Risk:** High

- [ ] **W96-2 (P0) SKILL-first architecture policy as repository contract** `AGENTS.md`, `templates/aidd/docs/prompting/conventions.md`, `README.md`, `README.en.md`:
  - закрепить policy: stage entrypoints живут в `skills/<stage>/scripts/*`; shared entrypoints — в `skills/aidd-core/scripts/*`; `tools/` = shared libs + orchestrator + compatibility shims;
  - явно описать migration phases (canonical path + shim path + removal window);
  - добавить требования к output diagnostics и ссылкам в docs/hook hints.
  **AC:** policy документирована как SoT и совпадает с фактическими migration задачами.
  **Regression/tests:** docs lint + `tests/repo_tools/lint-prompts.py`.
  **Effort:** S
  **Risk:** Medium

- [ ] **W96-3 (P1) Script type normalization (`.sh`=bash, python entrypoints=`.py`)** `tools/*.sh`, `tools/*.py`, `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/skill-scripts-guard.py`:
  - устранить практику python-shebang в `.sh` для новых canonical entrypoints;
  - ввести guard, чтобы новые `.sh` в runtime были bash wrappers, а python logic жила в `.py`;
  - добавить transitional exceptions list для legacy shims до конца миграции.
  **AC:** новый runtime не добавляет python-shebang `.sh`; violations ловятся CI guard.
  **Regression/tests:** shellcheck/static checks + guard test.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-4 (P1) Canonical stage wrapper template + python bootstrap policy** `skills/*/scripts/*.sh`, `skills/aidd-reference/wrapper_lib.sh`, `AGENTS.md`:
  - унифицировать шаблон wrapper scripts (bash strict mode, guarded output, deterministic logs, CLI flags);
  - зафиксировать вызов python-логики через стабильный bootstrap (`CLAUDE_PLUGIN_ROOT`, `PYTHONPATH`), без неявных относительных импортов;
  - документировать обязательные поля stdout contract для preflight/run/postflight wrappers.
  **AC:** новые wrappers создаются по одному шаблону и проходят script guards без ручных исключений.
  **Regression/tests:** `python3 tests/repo_tools/skill-scripts-guard.py`, schema guards.
  **Effort:** M
  **Risk:** Medium

### EPIC B — Stage-local shell entrypoint relocation

- [ ] **W96-5 (P1) IDEA: move `analyst-check` to stage scripts + shim** `skills/idea-new/scripts/analyst-check.sh`, `skills/idea-new/SKILL.md`, `tools/analyst-check.sh`, `README.md`, `README.en.md`, `tests/repo_tools/shim-regression.sh`:
  - добавить canonical `skills/idea-new/scripts/analyst-check.sh` и переключить stage refs;
  - оставить `tools/analyst-check.sh` как warn-only compatibility shim;
  - синхронизировать docs/tests на canonical path.
  **AC:** `idea-new` использует stage-local script; legacy path остаётся совместимым через shim.
  **Regression/tests:** shim-regression + stage smoke.
  **Effort:** S
  **Risk:** Low

- [ ] **W96-6 (P1) PLAN: move `research-check` to stage scripts + shim** `skills/plan-new/scripts/research-check.sh`, `skills/plan-new/SKILL.md`, `tools/research-check.sh`, `README.md`, `README.en.md`, `tests/repo_tools/shim-regression.sh`:
  - добавить canonical `skills/plan-new/scripts/research-check.sh`;
  - перевести stage/docs refs и сохранить `tools/research-check.sh` как deprecated shim;
  - зафиксировать deprecation notice policy.
  **AC:** `plan-new` использует stage-local `research-check.sh`; legacy tool path работает как shim.
  **Regression/tests:** shim-regression + lint-prompts.
  **Effort:** S
  **Risk:** Low

- [ ] **W96-7 (P1) REVIEW-SPEC: move `prd-review` to stage scripts + shim** `skills/review-spec/scripts/prd-review.sh`, `skills/review-spec/SKILL.md`, `tools/prd-review.sh`, `tests/test_prd_review_agent.py`, `tests/repo_tools/shim-regression.sh`:
  - добавить canonical `skills/review-spec/scripts/prd-review.sh`;
  - оставить `tools/prd-review.sh` как compatibility shim;
  - обновить skill/docs/tests references.
  **AC:** review-spec stage вызывает только stage-local entrypoint; legacy path совместим.
  **Regression/tests:** prd review unit/integration + shim regression.
  **Effort:** S
  **Risk:** Low

- [ ] **W96-8 (P1) RESEARCHER: move stage entrypoints to `skills/researcher/scripts/*` + shims** `skills/researcher/scripts/research.sh`, `skills/researcher/scripts/reports-pack.sh`, `skills/researcher/scripts/rlm-*.sh`, `tools/research.sh`, `tools/reports-pack.sh`, `tools/rlm-*.sh`, `skills/researcher/SKILL.md`, `agents/researcher.md`:
  - ввести canonical stage-local wrappers для research pipeline (`research`, `reports-pack`, `rlm-*`);
  - сохранить `tools/*` как shim API для hooks/legacy CLI на deprecation window;
  - обновить stage/agent/docs references на canonical path (dual path в migration phase).
  **AC:** researcher stage работает через `skills/researcher/scripts/*`; legacy tool entrypoints не ломают hooks.
  **Regression/tests:** `tests/test_research_rlm_e2e.py`, `tests/test_rlm_wrappers.py`, smoke + shim-regression.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-9 (P1) QA: canonical `skills/qa/scripts/qa.sh` + compatibility shim** `skills/qa/scripts/qa.sh`, `skills/qa/SKILL.md`, `tools/qa.sh`, `templates/aidd/config/gates.json`, `hooks/gate-qa.sh`, `tests/helpers.py`, `tests/test_qa_runner.py`:
  - добавить stage-local `qa.sh` и переключить QA stage path;
  - оставить `tools/qa.sh` совместимым shim для hooks/tests/legacy docs;
  - выровнять path hints в gates/config/helpers.
  **AC:** QA stage запускается через stage script; hook path остаётся совместимым.
  **Regression/tests:** QA unit/integration + gate-qa + shim-regression.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-10 (P1) STATUS: move `status.sh` + `index-sync.sh` to stage scripts + shims** `skills/status/scripts/status.sh`, `skills/status/scripts/index-sync.sh`, `skills/status/SKILL.md`, `tools/status.sh`, `tools/index-sync.sh`, `README.md`, `README.en.md`, `tests/test_status.py`:
  - добавить canonical stage-local status scripts;
  - сохранить `tools/status.sh`/`tools/index-sync.sh` как deprecated shims;
  - синхронизировать docs/examples/tests.
  **AC:** status stage использует `skills/status/scripts/*`; legacy tool paths совместимы.
  **Regression/tests:** status/index tests + smoke + shim-regression.
  **Effort:** M
  **Risk:** Low

### EPIC C — Stage-local Python runtime relocation

- [ ] **W96-11 (P1) Move stage-specific Python (idea/plan/review-spec) near skills** `skills/idea-new/runtime/analyst_check.py`, `skills/plan-new/runtime/research_check.py`, `skills/review-spec/runtime/prd_review.py`, `tools/analyst_check.py`, `tools/research_check.py`, `tools/prd_review.py`:
  - перенести stage-only python modules рядом со stage skill;
  - в `tools/*.py` оставить compatibility stubs на переходный период;
  - обновить wrappers/import paths без breaking change.
  **AC:** stage-specific python logic живёт в `skills/<stage>/runtime`; legacy imports через stubs остаются рабочими.
  **Regression/tests:** unit tests для analyst/research/prd review + smoke.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-12 (P1) Move researcher Python runtime modules near stage** `skills/researcher/runtime/reports_pack.py`, `skills/researcher/runtime/rlm_*.py`, `tools/reports_pack.py`, `tools/rlm_*.py`, `tools/research.py`:
  - перенести researcher-specific python runtime к stage skill;
  - `tools/research.py` оставить shared/hook-facing, пока не завершён deferred-core phase;
  - сохранить совместимые stubs в `tools/` до окончания migration window.
  **AC:** researcher-specific runtime рядом со stage; shared APIs не ломаются.
  **Regression/tests:** `tests/test_research_rlm_e2e.py`, `tests/test_rlm_*`, shim-regression.
  **Effort:** L
  **Risk:** High

- [ ] **W96-13 (P1) Move review Python runtime modules near stage** `skills/review/runtime/context_pack.py`, `skills/review/runtime/review_pack.py`, `skills/review/runtime/review_report.py`, `skills/review/runtime/reviewer_tests.py`, `tools/context_pack.py`, `tools/review_pack.py`, `tools/review_report.py`, `tools/reviewer_tests.py`:
  - перенести review runtime к `skills/review/runtime`;
  - оставить `tools/*.py` как compat stubs до phase-2;
  - обновить wrappers/tests/import matrix для обоих путей (canonical + shim).
  **AC:** review runtime локализован рядом со stage; external compatibility сохранена.
  **Regression/tests:** `tests/test_review_pack.py`, `tests/test_review_report.py`, `tests/test_reviewer_tests_cli.py`, loop/review smoke.
  **Effort:** L
  **Risk:** High

- [ ] **W96-14 (P1) Expand lint/guards for `skills/<stage>/runtime/*` contract** `tests/repo_tools/lint-prompts.py`, `tests/repo_tools/skill-scripts-guard.py`, `tests/test_prompt_lint.py`, `AGENTS.md`:
  - разрешить `runtime/` как валидный support dir для skills (с лимитами глубины/размера);
  - добавить проверки на корректные bootstrap imports и отсутствие прямых writes вне workspace;
  - сохранить strict валидацию `scripts/*.sh` (bash-only, guarded output).
  **AC:** lint/guards валидно поддерживают stage runtime relocation и не дают ложных FAIL.
  **Regression/tests:** prompt-lint + skill-scripts-guard unit coverage.
  **Effort:** M
  **Risk:** Medium

### EPIC D — Shared skill runtime, inheritance, and inventory

- [ ] **W96-15 (P1) Shared shell entrypoints: canonical move to `skills/aidd-core/scripts/*` + shims** `skills/aidd-core/scripts/*.sh`, `tools/set-active-stage.sh`, `tools/set-active-feature.sh`, `tools/progress.sh`, `tools/stage-result.sh`, `tools/status-summary.sh`, `tools/tasklist-*.sh`, `tools/prd-check.sh`, `tools/diff-boundary-check.sh`:
  - перенести multi-stage shell entrypoints в shared skill (`aidd-core`);
  - оставить `tools/*.sh` compatibility shims на deprecation window;
  - обновить references в stage skills/docs/hooks/tests.
  **AC:** canonical shared entrypoints живут в `skills/aidd-core/scripts/*`; `tools/*` совместимы как shims.
  **Regression/tests:** smoke + shim-regression + hook tests.
  **Effort:** L
  **Risk:** High

- [ ] **W96-16 (P1) Shared RLM preload skill for agents/stages** `skills/aidd-rlm/SKILL.md`, `agents/*.md`, `skills/*/SKILL.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `tools/entrypoints-bundle.txt`, `dev/reports/migrations/commands_to_skills_frontmatter.json`:
  - добавить preloaded shared skill `aidd-rlm` (user-invocable=false) как SoT для `rlm-slice/rlm-*`;
  - подключить через frontmatter `skills:` в агентах и stage skills вместо копипасты tool lists;
  - зафиксировать inheritance policy в lint/baseline.
  **AC:** RLM toolset задаётся в одном shared skill; frontmatter drift отсутствует.
  **Regression/tests:** prompt-lint + baseline parity + entrypoints bundle.
  **Effort:** L
  **Risk:** High

- [ ] **W96-17 (P1) Shared loop-runtime skill contract (`implement/review/qa`)** `skills/aidd-loop-runtime/SKILL.md`, `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - вынести общий loop runtime toolset в shared preload skill;
  - подключить через `skills:` в stage frontmatter, сократить дубли `allowed-tools`;
  - поддержать переходный режим (legacy full list + inherited contract) до завершения миграции.
  **AC:** implement/review/qa используют единый shared loop-runtime contract.
  **Regression/tests:** lint-prompts/baseline parity + loop smoke.
  **Effort:** L
  **Risk:** High

- [ ] **W96-18 (P1) Stage skill inheritance lint contract (no false baseline mismatch)** `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `tools/entrypoints_bundle.py`, `dev/reports/migrations/commands_to_skills_frontmatter.json`:
  - обновить lint под inheritance shared skill toolsets;
  - валидировать preload references (`skills:`) и запрещать broken/empty links;
  - сохранить обратную совместимость на migration window.
  **AC:** lint принимает shared inheritance и блокирует некорректные preload ссылки.
  **Regression/tests:** prompt-lint unit tests + baseline migration tests.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-19 (P1) Tools inventory v2: canonical/shared/shim + consumers matrix** `tools/tools_inventory.py`, `tests/test_tools_inventory.py`, `tests/repo_tools/ci-lint.sh`, `README.md`, `README.en.md`, `AGENTS.md`:
  - расширить inventory классификацией: `canonical_stage`, `shared_skill`, `shim`, `core_api_deferred`;
  - добавить consumer types (`agent`, `skill`, `hook`, `test`, `shim`) и флаг canonical replacement;
  - использовать отчёт как guard against false "unused" during migration.
  **AC:** inventory корректно показывает canonical/shared/shim состояние и прогресс миграции.
  **Regression/tests:** tools inventory unit tests + CI consistency guard.
  **Effort:** M
  **Risk:** Medium

### EPIC E — Agents, hooks, and docs convergence

- [ ] **W96-20 (P1) Agent playbook migration to shared skills + stage scripts** `agents/*.md`, `skills/aidd-core/SKILL.md`, `skills/aidd-loop/SKILL.md`, `tests/repo_tools/lint-prompts.py`:
  - перевести агентные prompts на shared skills как SoT, убрать дубли long-form runtime procedures;
  - запретить прямые ссылки в агентах на stage-local `tools/<stage>.sh` (кроме deferred core APIs);
  - обновить prompt-lint guardrails для этого правила.
  **AC:** агенты используют shared skills/stage scripts и не ходят напрямую в stage-local tools paths.
  **Regression/tests:** prompt-lint + agent prompt regression checks.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-21 (P1) Hook/docs path normalization (canonical + shim guidance)** `hooks/context_gc/pretooluse_guard.py`, `hooks/gate-tests.sh`, `hooks/gate-qa.sh`, `tools/gate_workflow.py`, `README.md`, `README.en.md`, `docs/legacy/commands/*.md`, `templates/aidd/docs/prompting/conventions.md`:
  - нормализовать подсказки: canonical path = `skills/<stage>/scripts/*`, legacy path = compatibility shim;
  - добавить dual-path hints на deprecation window;
  - убрать stale references на устаревшие entrypoints без контекста.
  **AC:** hooks/docs последовательно показывают canonical путь и явно помечают shim.
  **Regression/tests:** docs lint + hook tests + shim regression.
  **Effort:** S
  **Risk:** Low

- [ ] **W96-22 (P1) Templates/docs per-stage layout + stage lexicon document** `templates/aidd/docs/stages/**`, `templates/aidd/docs/shared/stage-lexicon.md`, `templates/aidd/docs/tasklist/template.md`, `templates/aidd/docs/prd/template.md`, `templates/aidd/docs/plan/template.md`, `templates/aidd/docs/research/template.md`:
  - ввести per-stage структуру шаблонов (`intent/inputs/outputs/checklist`) + shared docs (`artifacts`, `naming`, `lexicon`);
  - устранить конфликт `review-spec` vs `review-plan/review-prd` в templates;
  - разделить reference docs и generated outputs policy.
  **AC:** template structure stage-oriented, naming deterministic, lexicon documented.
  **Regression/tests:** template guards + smoke bootstrap validation.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-23 (P1) Gates/config alignment to SKILL-first docs/runtime paths** `templates/aidd/config/gates.json`, `tools/gate_workflow.py`, `tools/research_guard.py`, `tools/status.py`, `tools/index_sync.py`, `tests/test_gate_workflow.py`, `tests/test_gate_qa.py`:
  - синхронизировать gates и runtime path expectations под canonical stage/shared script paths;
  - выровнять expected artifacts по стадиям согласно обновлённым templates/docs;
  - добавить regression checks на path drift.
  **AC:** gates и runtime policy совпадают с новой SKILL-first структурой.
  **Regression/tests:** gate unit/integration matrix + smoke workflow.
  **Effort:** M
  **Risk:** High

### EPIC F — Deferred core APIs + carry-over hardening (former W97 included)

- [ ] **W96-24 (P0) Deferred-core API freeze (wave-1 no-relocate)** `tools/init.sh`, `tools/research.sh`, `tools/tasks-derive.sh`, `tools/actions-apply.sh`, `tools/context-expand.sh`, `tests/test_init_aidd.py`, `tests/test_research_rlm_e2e.py`, `tests/test_tasks_derive.py`, `tests/test_context_expand.py`:
  - закрепить перечисленные entrypoints как stable public API для wave-1;
  - добавить contract snapshot tests (flags, exit codes, hints, compatibility);
  - запретить silent relocation без shim/migration notes.
  **AC:** deferred-core APIs стабильны и защищены contract tests/CI guards.
  **Regression/tests:** API-specific unit/integration + smoke.
  **Effort:** M
  **Risk:** High

- [ ] **W96-25 (P1) Do-not-migrate guardrails in lint/inventory/CI** `tests/repo_tools/lint-prompts.py`, `tools/tools_inventory.py`, `tests/test_tools_inventory.py`, `tests/repo_tools/ci-lint.sh`, `AGENTS.md`, `README.md`, `README.en.md`:
  - пометить deferred APIs как `core_api=true`, `migration_deferred=true` в inventory;
  - добавить CI/lint блокировки на перенос без shim/compat note;
  - синхронизировать policy docs.
  **AC:** accidental relocation deferred-core APIs блокируется автоматически.
  **Regression/tests:** inventory/lint tests + CI scenario checks.
  **Effort:** S
  **Risk:** Medium

- [ ] **W96-26 (P2) Phase-2 blueprint: deferred-core and review-shim removal windows** `AGENTS.md`, `CHANGELOG.md`, `docs/legacy/commands/*.md`, `tests/repo_tools/shim-regression.sh`:
  - описать phase-2 roadmap: target canonical path, rollout order, rollback plan, explicit removal windows;
  - включить отдельный план удаления review compatibility shims (`tools/review-pack.sh`, `tools/review-report.sh`, `tools/reviewer-tests.sh`);
  - определить release criteria для финального удаления shim paths.
  **AC:** есть согласованный phase-2 план с датируемыми критериями и rollback steps.
  **Regression/tests:** n/a (design artifact), smoke/ci остаются зелёными.
  **Effort:** S
  **Risk:** Medium
  **Carry-over:** W95-E4

- [ ] **W96-27 (P1) Cleanup tracked ad-hoc prompt artifact** `aidd_test_flow_prompt_ralph_script.txt`, `.gitignore`, `docs/examples/**`, `CHANGELOG.md`, `README.md`, `README.en.md`:
  - удалить ad-hoc файл из tracking или формализовать в `docs/examples/**` с metadata header;
  - синхронизировать `.gitignore`, docs и release notes;
  - убрать dangling references.
  **AC:** ad-hoc artifact больше не нарушает repo hygiene и docs consistency.
  **Regression/tests:** repo hygiene checks + grep guard on stale references.
  **Effort:** S
  **Risk:** Low
  **Carry-over:** W95-F2

- [ ] **W96-28 (P1) Output-contract from diagnostic to gate policy input** `tools/output_contract.py`, `tools/loop_step.py`, `tools/gate_workflow.py`, `tools/stage_result.py`, `tests/test_output_contract.py`, `tests/test_loop_step.py`, `tests/test_gate_workflow.py`:
  - перевести `output.contract.json` из warn-only диагностики в policy input (WARN/BLOCK по профилю);
  - пробрасывать reason-code в stage_result/loop payload для budget/read-order/status mismatch;
  - добавить matrix tests для `read_log_too_long`, `full_doc_without_missing_fields`, `read_order_*`, `status_mismatch_stage_result`.
  **AC:** output-contract детерминированно влияет на gate/loop решения.
  **Regression/tests:** output contract + gate workflow matrix tests.
  **Effort:** M
  **Risk:** High
  **Carry-over:** W89.5-8

- [ ] **W96-29 (P1) Non-blocking recovery for `review_pack_stale` when regeneration succeeds** `tools/loop_step.py`, `tools/loop_run.py`, `tools/review_pack.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`, `tests/test_loop_semantics.py`:
  - убрать hard-block на `review_pack_stale` для recoverable сценариев после успешной регенерации pack;
  - оставить BLOCK только для невосстановимых состояний (`review_pack_missing` после retry, invalid schema);
  - добавить telemetry в loop logs (`stale_recovered` vs `stale_blocked`).
  **AC:** stale-pack recoverable path не останавливает loop-run, reason-codes остаются различимыми.
  **Regression/tests:** loop-step/loop-run semantics tests for stale recovery.
  **Effort:** M
  **Risk:** Medium
  **Carry-over:** W89.5-9

- [ ] **W96-30 (P1) SKILL-first wrapper contract hardening in loop/gates** `tools/loop_step.py`, `tools/loop_run.py`, `tools/gate_workflow.py`, `skills/implement/scripts/preflight.sh`, `skills/review/scripts/preflight.sh`, `skills/qa/scripts/preflight.sh`, `tests/test_gate_workflow_preflight_contract.py`, `tests/test_loop_step.py`, `tests/repo_tools/smoke-workflow.sh`:
  - зафиксировать always-on wrapper contract для `implement|review|qa` в seed и loop-path (preflight/readmap/writemap/actions/logs);
  - убрать false-success paths без обязательных артефактов и `AIDD:ACTIONS_LOG`;
  - улучшить BLOCKED diagnostics (`reason`, `reason_code`, `stage_result_path`, wrapper logs).
  **AC:** stage success невозможен без wrapper contract; diagnostics полные и детерминированные.
  **Regression/tests:** gate/loop integration + smoke workflow.
  **Effort:** M
  **Risk:** High

## Wave 90 — Research RLM-only (без context/targets, только AIDD:RESEARCH_HINTS)

_Статус: новый, приоритет 1. Обратная совместимость не требуется — удалить старую логику и тесты._

- [ ] **W90-1** `tools/research_hints.py` (или `tools/prd_sections.py`), `templates/aidd/docs/prd/template.md`, `commands/idea-new.md`, `commands/researcher.md`:
  - добавить парсер `AIDD:RESEARCH_HINTS` (Paths/Keywords/Notes) с нормализацией (split `:`/`,`/whitespace, trim, dedupe);
  - сделать hints обязательными для research (минимум `paths` или `keywords`);
  - обновить PRD template/commands: явно требовать заполнения `AIDD:RESEARCH_HINTS` на этапе analyst.
  **AC:** есть единый парсер hints; research не стартует при пустых hints; PRD template содержит строгий формат.
  **Deps:** -

- [ ] **W90-2** `tools/rlm_targets.py`, `tools/rlm_manifest.py`, `tools/rlm_links_build.py`, `tools/rlm_nodes_build.py`:
  - RLM targets строятся напрямую из `AIDD:RESEARCH_HINTS` (paths/keywords/notes), без `*-targets.json`;
  - удалить `_load_research_targets` и любые зависимости от `reports/research/*-targets.json`;
  - `targets_mode=explicit` при наличии paths.
  **AC:** `aidd/reports/research/<ticket>-rlm-targets.json` генерируется только из PRD hints; `*-targets.json` нигде не читается.
  **Deps:** W90-1

- [ ] **W90-3** `tools/research.py`, `tools/research.sh`, `tools/researcher-context.sh`, `tools/researcher_context.py`, `tools/reports_pack.py`:
  - убрать сбор `*-context.json`/`*-context.pack.json` и `*-targets.json`;
  - удалить/заменить `ResearcherContextBuilder` и связанные CLI (`researcher-context`);
  - `research.sh` запускает только RLM pipeline (targets → manifest → worklist) + materialize `docs/research/<ticket>.md`;
  - удалить `reports.research_pack_budget` логику в `tools/reports_pack.py`.
  **AC:** research не создаёт `*-context*` и `*-targets.json`; остаются только RLM артефакты и `docs/research/<ticket>.md`.
  **Deps:** W90-1, W90-2

- [ ] **W90-4** `tools/research_guard.py`, `tools/gate_workflow.py`, `tools/tasks_derive.py`, `tools/index_sync.py`, `tools/status.py`:
  - валидировать research только по RLM артефактам (targets/manifest/worklist/nodes/links/pack);
  - handoff‑derive для research берёт данные только из `*-rlm.pack.json`;
  - удалить ссылки на `*-context.json`/`*-targets.json` из gate/index/status.
  **AC:** гейты и handoff работают без `*-context*`; warnings/blocked основаны на RLM readiness.
  **Deps:** W90-2, W90-3

- [ ] **W90-5** `tools/rlm_finalize.py`, `tools/rlm_nodes_build.py`, `tools/reports_pack.py`:
  - убрать `--update-context` и любые обновления `context.json`;
  - `rlm_finalize` оперирует только `nodes/links` и пишет `*-rlm.pack.json`.
  **AC:** `rlm_finalize` работает без `context.json`; pack строится из nodes/links.
  **Deps:** W90-3

- [ ] **W90-6** `agents/researcher.md`, `commands/researcher.md`, `templates/aidd/docs/anchors/research.md`, `templates/aidd/docs/anchors/rlm.md`, `AGENTS.md`, `templates/aidd/AGENTS.md`, `templates/aidd/config/conventions.json`:
  - удалить упоминания `*-context.json`/`*-context.pack.json`/`*-targets.json`;
  - зафиксировать RLM‑only policy и зависимость от `AIDD:RESEARCH_HINTS`;
  - удалить `reports.research_pack_budget` из `config/conventions.json`.
  **AC:** документация и канон описывают только RLM артефакты; нет ссылок на context/targets.
  **Deps:** W90-1, W90-3

- [ ] **W90-7** `tests/*`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh` (если нужно), `tests/helpers.py`:
  - удалить/переписать тесты, опирающиеся на `*-context.json`/`*-targets.json`;
  - добавить тесты для парсера `AIDD:RESEARCH_HINTS` и RLM targets из PRD;
  - обновить smoke‑workflow под RLM‑only.
  **AC:** тесты проходят в режиме RLM‑only; отсутствуют упоминания `*-context*` в тестах.
  **Deps:** W90-1, W90-2, W90-3, W90-4, W90-5

## Wave 100 — Реальная параллелизация (scheduler + claim + parallel loop-run)

_Статус: план. Цель — запуск нескольких implementer/reviewer в параллель по независимым work items, безопасное распределение задач, отсутствие гонок артефактов, консолидация результатов._

### EPIC P — Task Graph (DAG) как источник для планирования
- [ ] **W100-1** `tools/task_graph.py`, `aidd/reports/taskgraph/<ticket>.json` (или `aidd/docs/taskgraph/<ticket>.yaml`):
  - парсер tasklist → DAG:
    - узлы: iterations (`iteration_id`) + handoff (`id: review:* / qa:* / research:* / manual:*`);
    - поля: deps/locks/expected_paths/priority/blocking/state;
    - node id: `iteration_id` или `handoff id`; state выводится из чекбокса + (опционально) stage_result.
  - вычисление `ready/runnable` и топологическая проверка (cycles/missing deps).
  **AC:** из tasklist строится корректный DAG; есть список runnable узлов.

- [ ] **W100-2** `tools/taskgraph-check.sh` (или расширение `tasklist-check.sh`):
  - валидировать: циклы, неизвестные deps, self-deps, пустые expected_paths (если требуется), конфликтующие locks (опционально).
  **AC:** CI/локальный чек ловит некорректные зависимости до запуска параллели.

### EPIC Q — Claim/Lock протокол для work items
- [ ] **W100-3** `tools/work_item_claim.py`, `tools/work-item-claim.sh`, `aidd/reports/locks/<ticket>/<id>.lock.json`:
  - claim/release/renew lock;
  - stale lock policy (ttl, force unlock);
  - в lock хранить `worker_id`, `created_at`, `last_seen`, `scope_key`, `branch/worktree`;
  - shared locks dir (например, `AIDD_LOCKS_DIR`) или orchestrator-only locks; атомарное создание (O_EXCL).
  **AC:** один узел не может быть взят двумя воркерами; stale locks диагностируются и снимаются по правилам; locks общие для всех воркеров.

### EPIC R — Scheduler: выбор runnable узлов под N воркеров
- [ ] **W100-4** `tools/scheduler.py`:
  - выбрать набор runnable узлов на N воркеров:
    - учитывать deps,
    - учитывать `locks`,
    - учитывать пересечения `expected_paths` (конфликт → не запускать параллельно; конфликт = общий top-level group или префикс),
    - сортировка: blocking → priority → plan order.
  **AC:** scheduler отдаёт набор независимых work items; не выдаёт конфликтующие по locks/paths.

- [ ] **W100-5** `tools/loop_pack.py` / `loop-pack.sh`:
  - уметь генерировать loop pack по конкретному work_item_id, а не только “следующий из NEXT_3”;
  - сохранять pack в per‑work‑item пути (Wave 87 уже подготовил).
  **AC:** можно собрать loop pack для любого узла DAG по id; pack содержит deps/locks/expected_paths/size_budget/tests для выбранного узла.

### EPIC S — Parallel loop-run (оркестрация воркеров)
- [ ] **W100-6** `tools/loop_run.py`:
  - добавить режим `--parallel N`:
    - получить runnable узлы от scheduler,
    - claim locks,
    - запустить N воркеров (каждый с явным `--work-item <id>` / `scope_key`),
    - собирать stage results и принимать решения (blocked/done/continue) по каждому узлу.
  **AC:** parallel loop-run запускает N независимых узлов и корректно реагирует на BLOCKED/DONE по каждому; определён контракт artifact root (shared vs per-worktree) и сбор результатов.

- [ ] **W100-7** `tools/worktree_manager.py` (или `tests/repo_tools/worktree.sh`):
  - подготовка isolated рабочих директорий на воркера:
    - `git worktree add` / отдельные ветки,
    - единый шаблон именования веток,
    - cleanup.
  **AC:** каждый воркер работает в изолированном worktree; определён способ записи артефактов (shared root или сбор из worktrees).

### EPIC T — Консолидация результатов обратно в основной tasklist
- [ ] **W100-8** `tools/tasklist_consolidate.py`, `tools/tasklist-normalize.sh`:
  - на основе stage_result + review_pack + tests_log:
    - отметить `[x]` для завершённых узлов,
    - обновить `AIDD:NEXT_3` из DAG runnable,
    - добавить `AIDD:PROGRESS_LOG` записи,
    - перенос/дедуп handoff задач.
  **AC:** после параллельного прогона tasklist обновляется детерминированно; без дублей; NEXT_3 корректен; дедуп handoff по стабильному id.

- [ ] **W100-9** `tools/reports/aggregate.py`:
  - агрегировать evidence в “ticket summary”:
    - ссылки на per‑work‑item tests logs,
    - список stage results,
    - сводка статусов узлов.
  **AC:** есть единый сводный отчёт по тикету и по узлам.

### EPIC U — Документация + регрессии
- [ ] **W100-10** `templates/aidd/docs/loops/README.md`, `templates/aidd/docs/prompting/conventions.md`:
  - задокументировать parallel workflow:
    - deps/locks/expected_paths правила,
    - claim/release,
    - конфликт‑стратегию (paths overlap → serial),
    - policy: воркеры не редактируют tasklist в parallel‑mode (consolidate делает main).
  **AC:** понятная инструкция “как запускать parallel loop-run” + troubleshooting + policy для tasklist/артефактов.

- [ ] **W100-11** `tests/test_scheduler.py`, `tests/test_parallel_loop_run.py`, `tests/repo_tools/parallel-loop-regression.sh`:
  - тесты на DAG, scheduler, claim, параллельный раннер, консолидацию.
  **AC:** регрессии ловят гонки/перетирание артефактов/неверный выбор runnable; включены кейсы conflict paths/lock stale/worker crash.
