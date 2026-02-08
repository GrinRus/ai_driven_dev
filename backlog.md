# Product Backlog

## Wave 96 — SKILL-first migration program (consolidated)

_Статус: новый, приоритет 0. Цель — перевести runtime на SKILL-first модель: stage/shared entrypoints живут рядом со SKILL, а `tools/` остаётся shared library/orchestrator + compatibility shims._

### Success Metrics (tracked per checkpoint)

- **M1:** stage-specific entrypoints left in `tools/` (excluding explicit shims) -> target `0` после Phase 1.
  **Check:** `python3 tools/tools_inventory.py --repo-root . --output-json /tmp/aidd_tools_inventory.json --output-md /tmp/aidd_tools_inventory.md` + фильтр по classification.
- **M2:** python-shebang in `.sh` -> не увеличивается в Phase 0, затем сокращается по migration window.
  **Check:** `find tools -maxdepth 1 -type f -name '*.sh' -print0 | xargs -0 rg -n '^#!.*python'`.
- **M3:** direct `tools/` refs in agents -> остаются только deferred-core/orchestrator/gates.
  **Check:** `rg '\$\{CLAUDE_PLUGIN_ROOT\}/tools/' agents/`.
- **M4:** direct `tools/` refs in stage skills -> остаются только deferred-core/shims на migration window.
  **Check:** `rg '\$\{CLAUDE_PLUGIN_ROOT\}/tools/' skills/*/SKILL.md`.

### Phase Plan

- **Phase 0 (обязательное):** policy/guards/inventory + deferred-core freeze/guardrails + test-runner standardization.
- **Phase 1 (обязательное):** stage-local shell relocation (`W96-5..W96-10`) + compatibility shims + hook/docs dual-path hints.
- **Phase 2 (можно начать):** stage-local python relocation (`W96-11..W96-14`).
- **Phase 3 (после Phase 1):** shared shell relocation to `skills/aidd-core/scripts/*` (`W96-15`) + docs/templates/gates alignment (`W96-1c`, `W96-22`, `W96-23`).
- **Phase 4 (optional, P2):** hardening (`W96-28..W96-30`) after migration baseline is stable.

### Phase 0 — Policy, Guards, Inventory, Freeze

- [ ] **W96-0 (P0) Baseline audit snapshot + migration board refresh** `backlog.md`, `tools/entrypoints-bundle.txt`, `tools/tools_inventory.py`, `tests/repo_tools/lint-prompts.py`:
  - зафиксировать baseline факты и blast radius перед миграцией (consumers matrix по skill/agent/hook/test/docs);
  - синхронизировать sequence коммитов и phase dependencies;
  - зафиксировать M1–M4 baseline values.
  **AC:** backlog и migration board совпадают с фактическим runtime/refs state.
  **Regression/tests:** inventory + lint-prompts.
  **Effort:** S
  **Risk:** Low

- [ ] **W96-1a (P0) Stage Lexicon DOC + templates/docs alignment (no runtime validator changes)** `AGENTS.md`, `templates/aidd/AGENTS.md`, `templates/aidd/docs/tasklist/template.md`, `templates/aidd/docs/prompting/conventions.md`, `README.md`, `README.en.md`:
  - зафиксировать lexicon: public stage `review-spec`; internal substages `review-plan`/`review-prd`;
  - убрать терминологические конфликты в user-facing docs/templates;
  - явно указать alias/deprecation notes в документации.
  **AC:** docs/templates согласованы по stage lexicon без изменения runtime validators.
  **Regression/tests:** docs checks + prompt-lint.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-1b (P0) Runtime accepts public `review-spec` (alias/umbrella) without drift** `tools/set_active_stage.py`, `tools/context_map_validate.py`, `tools/gate_workflow.py`, `tests/test_set_active_stage.py`, `tests/test_gate_workflow.py`:
  - добавить/выровнять alias handling: `review-spec` как public umbrella stage;
  - сохранить корректную internal маршрутизацию для `review-plan`/`review-prd`;
  - исключить drift между active-stage, scope keys и gate behavior.
  **AC:** runtime корректно принимает `review-spec` и не ломает internal review flow.
  **Regression/tests:** stage alias/unit + gate integration tests.
  **Effort:** M
  **Risk:** High

- [ ] **W96-2 (P0) SKILL-first architecture policy contract (docs)** `AGENTS.md`, `templates/aidd/docs/prompting/conventions.md`, `README.md`, `README.en.md`:
  - stage entrypoints -> `skills/<stage>/scripts/*`;
  - shared entrypoints target -> `skills/aidd-core/scripts/*` (Phase 3);
  - `tools/` -> shared libs/orchestrator + compatibility shims with deprecation window.
  **AC:** policy формализована как SoT и совпадает с migration plan.
  **Regression/tests:** lint-prompts + docs consistency checks.
  **Effort:** S
  **Risk:** Medium

- [ ] **W96-3a (P0) Guard: canonical `.sh` must be bash (allowlist for legacy shims only)** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/skill-scripts-guard.py`, `tests/repo_tools/shim-regression.sh`:
  - запретить python-shebang для canonical scripts в `skills/**/scripts/*.sh`;
  - добавить allowlist/классификацию legacy shims в `tools/*.sh`;
  - проверять `bash -n` для canonical scripts.
  **AC:** новые canonical scripts всегда bash; нарушения ловятся CI guard.
  **Regression/tests:** ci-lint + skill-scripts-guard + shim-regression.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-3b (P0) Test-runner standardization (no "Ran 0 tests")** `tests/repo_tools/ci-lint.sh`, `.github/workflows/ci.yml`, `pyproject.toml` (если нужно), `AGENTS.md`:
  - выбрать и зафиксировать единый путь исполнения тестов (pytest или unittest);
  - обеспечить реальный запуск ключевых test suites в CI path;
  - добавить guard на пустые test runs.
  **AC:** ключевые тестовые наборы исполняются; нет "Ran 0 tests" в целевом CI path.
  **Regression/tests:** `tests/repo_tools/ci-lint.sh` + selected test runner step.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-4 (P1) Canonical wrapper template + python bootstrap policy** `skills/aidd-reference/wrapper_lib.sh`, `AGENTS.md`, `templates/aidd/docs/prompting/conventions.md`, `skills/*/scripts/*.sh`:
  - зафиксировать единый шаблон stage wrappers (`#!/usr/bin/env bash`, `set -euo pipefail`, guarded output);
  - стандартизировать bootstrap (`CLAUDE_PLUGIN_ROOT`, `PYTHONPATH`);
  - описать минимальный output/log contract для wrappers.
  **AC:** wrapper template единый и используемый для новых canonical scripts.
  **Regression/tests:** skill-scripts-guard + smoke wrapper flow.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-19 (P1) Tools inventory v2: canonical/shim/shared + consumers matrix** `tools/tools_inventory.py`, `tests/test_tools_inventory.py`, `tests/repo_tools/ci-lint.sh`, `README.md`, `README.en.md`, `AGENTS.md`:
  - добавить классификацию: `canonical_stage`, `shared_skill`, `shim`, `core_api_deferred`;
  - добавить consumer types: `agent`, `skill`, `hook`, `test`, `docs`, `shim`;
  - показывать `canonical_replacement_path` для shim entries.
  **AC:** inventory отражает migration status без false "unused".
  **Regression/tests:** test_tools_inventory + ci-lint guard.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-24 (P0) Deferred-core API freeze (stable external API, internal shim allowed)** `tools/init.sh`, `tools/research.sh`, `tools/tasks-derive.sh`, `tools/actions-apply.sh`, `tools/context-expand.sh`, `tests/test_init_aidd.py`, `tests/test_research_rlm_e2e.py`, `tests/test_tasks_derive.py`, `tests/test_context_expand.py`:
  - зафиксировать публичный контракт `tools/<entrypoint>`: путь/флаги/help/exit-code/hints стабильны в wave-1;
  - разрешить internal refactor: `tools/<entrypoint>` может стать shim на canonical `skills/.../scripts/...`, но без изменения внешнего контракта;
  - добавить contract tests на flags/help/exit codes/hints.
  **AC:** deferred-core APIs стабильны externally, internal shim strategy поддерживается тестами.
  **Regression/tests:** contract tests per deferred-core entrypoint + smoke.
  **Effort:** M
  **Risk:** High

- [ ] **W96-25 (P1) Do-not-migrate guardrails for deferred-core APIs** `tests/repo_tools/lint-prompts.py`, `tools/tools_inventory.py`, `tests/test_tools_inventory.py`, `tests/repo_tools/ci-lint.sh`, `AGENTS.md`, `README.md`, `README.en.md`:
  - пометить deferred-core APIs в inventory (`core_api=true`, `migration_deferred=true`);
  - блокировать silent relocation без shim + migration note;
  - синхронизировать policy/CI/docs.
  **AC:** accidental relocation deferred-core APIs без compat слоя блокируется.
  **Regression/tests:** inventory/lint unit tests + CI scenario.
  **Effort:** S
  **Risk:** Medium

### Phase 1 — Stage-local shell relocation (required)

- [ ] **W96-5 (P1) IDEA: relocate `analyst-check` to stage scripts + shim** `skills/idea-new/scripts/analyst-check.sh`, `skills/idea-new/SKILL.md`, `tools/analyst-check.sh`, `README.md`, `README.en.md`, `tests/repo_tools/shim-regression.sh`.
- [ ] **W96-6 (P1) PLAN: relocate `research-check` to stage scripts + shim** `skills/plan-new/scripts/research-check.sh`, `skills/plan-new/SKILL.md`, `tools/research-check.sh`, `README.md`, `README.en.md`, `tests/repo_tools/shim-regression.sh`.
- [ ] **W96-7 (P1) REVIEW-SPEC: relocate `prd-review` to stage scripts + shim** `skills/review-spec/scripts/prd-review.sh`, `skills/review-spec/SKILL.md`, `tools/prd-review.sh`, `tests/test_prd_review_agent.py`, `tests/repo_tools/shim-regression.sh`.
- [ ] **W96-8 (P1) RESEARCHER: relocate `research/reports-pack/rlm-*` wrappers to stage scripts + shims** `skills/researcher/scripts/*.sh`, `tools/research.sh`, `tools/reports-pack.sh`, `tools/rlm-*.sh`, `skills/researcher/SKILL.md`, `agents/researcher.md`, `tests/repo_tools/shim-regression.sh`.
- [ ] **W96-9 (P1) QA: canonical `skills/qa/scripts/qa.sh` + shim** `skills/qa/scripts/qa.sh`, `skills/qa/SKILL.md`, `tools/qa.sh`, `templates/aidd/config/gates.json`, `hooks/gate-qa.sh`, `tests/helpers.py`, `tests/test_qa_runner.py`.
- [ ] **W96-10 (P1) STATUS: canonical `skills/status/scripts/status.sh` + `index-sync.sh` + shims** `skills/status/scripts/status.sh`, `skills/status/scripts/index-sync.sh`, `skills/status/SKILL.md`, `tools/status.sh`, `tools/index-sync.sh`, `README.md`, `README.en.md`, `tests/test_status.py`.
  **AC (for W96-5..W96-10):** canonical stage-local entrypoints используются stage skills; старые `tools/*.sh` остаются deprecation shims (stderr DEPRECATED + exec canonical).
  **Regression/tests:** `bash tests/repo_tools/shim-regression.sh`, stage-specific unit/integration tests, smoke-workflow.

- [ ] **W96-21 (P1) Hook/docs hints: canonical + deprecated shim dual-path** `hooks/context_gc/pretooluse_guard.py`, `hooks/gate-tests.sh`, `hooks/gate-qa.sh`, `tools/gate_workflow.py`, `README.md`, `README.en.md`, `docs/legacy/commands/*.md`, `templates/aidd/docs/prompting/conventions.md`:
  - заменить hints на canonical `skills/<stage>/scripts/*`;
  - оставить legacy `tools/*` только как deprecated compatibility note.
  **AC:** hooks/docs не рекомендуют устаревший путь как primary.
  **Regression/tests:** hook tests + docs/lint checks.
  **Effort:** S
  **Risk:** Low

- [ ] **W96-31 (P2, W96-X) gate-api-contract: decide (remove or wire) + docs note** `hooks/gate-api-contract.sh`, `hooks/hooks.json`, `tests/test_wave95_policy_guards.py`, `AGENTS.md`, `README.md`:
  - проверить текущее состояние gate-api-contract (stub/unwired/removed);
  - выбрать один вариант: окончательно удалить и вычистить refs, либо полноценно wire + покрыть тестом;
  - зафиксировать решение в docs/backlog notes.
  **AC:** нет мёртвой placeholder-логики gate-api-contract без явного решения.
  **Regression/tests:** `tests/test_wave95_policy_guards.py` + hook wiring checks.
  **Effort:** S
  **Risk:** Low

### Phase 2 — Stage-local python relocation (can be partial in this PR)

- [ ] **W96-11 (P1) Relocate stage-specific python modules (idea/plan/review-spec) + compat stubs** `skills/idea-new/runtime/analyst_check.py`, `skills/plan-new/runtime/research_check.py`, `skills/review-spec/runtime/prd_review.py`, `tools/analyst_check.py`, `tools/research_check.py`, `tools/prd_review.py`.
- [ ] **W96-12 (P1) Relocate researcher python modules + compat stubs** `skills/researcher/runtime/*.py`, `tools/reports_pack.py`, `tools/rlm_*.py`, `tools/research.py`.
- [ ] **W96-13 (P1) Relocate review python modules + compat stubs** `skills/review/runtime/*.py`, `tools/context_pack.py`, `tools/review_pack.py`, `tools/review_report.py`, `tools/reviewer_tests.py`.
- [ ] **W96-14 (P1) Lint/guards for `skills/<stage>/runtime/*`** `tests/repo_tools/lint-prompts.py`, `tests/repo_tools/skill-scripts-guard.py`, `tests/test_prompt_lint.py`, `AGENTS.md`.
  **AC (for W96-11..W96-14):** stage-specific python logic может жить рядом со skill без потери compatibility через tools stubs.

### Phase 3 — Shared shell relocation + full alignment

- [ ] **W96-15 (P1) Relocate shared multi-stage shell entrypoints to `skills/aidd-core/scripts/*` + shims in tools** `skills/aidd-core/scripts/*.sh`, `tools/set-active-stage.sh`, `tools/set-active-feature.sh`, `tools/progress.sh`, `tools/stage-result.sh`, `tools/status-summary.sh`, `tools/tasklist-*.sh`, `tools/prd-check.sh`, `tools/diff-boundary-check.sh`.

- [ ] **W96-16 (P1) Shared RLM skill for SUBAGENT preload only (`agents/*.md`)** `skills/aidd-rlm/SKILL.md`, `agents/*.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `tools/entrypoints-bundle.txt`:
  - добавить compact shared skill `aidd-rlm` для subagent preload;
  - обновлять `agents/*.md` frontmatter `skills:` на `aidd-rlm` where needed;
  - **не** добавлять `skills:` inheritance в `skills/*/SKILL.md`.
  **AC:** subagents preload RLM guidance через `skills:`; stage skills без skills-in-skills inheritance.
  **Regression/tests:** prompt-lint + entrypoints bundle checks.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-17 (P1) Shared implement/review/qa toolset contract without skills-in-skills inheritance** `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `skills/aidd-core/scripts/*`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - убрать reliance on inheritance in `SKILL.md`;
  - консолидировать общий toolset через shared canonical entrypoints и (опционально) генерацию allowed-tools baselines;
  - если preload нужен — только для subagents, не для stage skills.
  **AC:** implement/review/qa согласованы по shared toolset без skills-in-skills механики.
  **Regression/tests:** prompt-lint/baseline parity.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-18 (P1) Agent skill preload validation contract** `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `agents/*.md`:
  - lint проверяет `agents/*.md` frontmatter `skills:` -> существующий `skills/<name>/SKILL.md`;
  - lint запрещает в агентах прямые refs на stage-local `tools/<stage-specific>.sh` (кроме deferred-core/orchestrator/gates);
  - lint требует canonical refs `skills/<stage>/scripts/*` или shared skill scripts where applicable.
  **AC:** agent frontmatter preload refs валидны; direct stage-local tool refs в agents блокируются.
  **Regression/tests:** prompt-lint unit/integration coverage for agent rules.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-1c (P1) Full stage lexicon alignment after entrypoint relocation** `tools/set_active_stage.py`, `tools/context_map_validate.py`, `templates/aidd/docs/tasklist/template.md`, `templates/aidd/config/gates.json`, `tools/gate_workflow.py`, `README.md`, `README.en.md`:
  - завершить согласование runtime + templates + gates после фактической миграции entrypoints;
  - удалить transitional drift и устаревшие aliases where safe;
  - закрепить финальный contract в docs/tests.
  **AC:** runtime/templates/gates работают в едином lexicon без конфликтов и скрытых alias regressions.
  **Regression/tests:** gate/integration + smoke.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-22 (P1) Templates/docs per-stage structure** `templates/aidd/docs/stages/**`, `templates/aidd/docs/shared/stage-lexicon.md`, `templates/aidd/docs/tasklist/template.md`, `templates/aidd/docs/prd/template.md`, `templates/aidd/docs/plan/template.md`, `templates/aidd/docs/research/template.md`.
- [ ] **W96-23 (P1) Gates/config alignment to new canonical paths** `templates/aidd/config/gates.json`, `tools/gate_workflow.py`, `tools/research_guard.py`, `tools/status.py`, `tools/index_sync.py`, `tests/test_gate_workflow.py`, `tests/test_gate_qa.py`.

### Phase 4 — Optional hardening (P2)

- [ ] **W96-26 (P2) Phase-2 blueprint: deferred-core and review-shim removal windows** `AGENTS.md`, `CHANGELOG.md`, `docs/legacy/commands/*.md`, `tests/repo_tools/shim-regression.sh`:
  - зафиксировать removal windows для compatibility shims;
  - включить план удаления review shims (`tools/review-pack.sh`, `tools/review-report.sh`, `tools/reviewer-tests.sh`).
  **AC:** есть согласованный Phase-2 removal plan with rollback criteria.
  **Carry-over:** W95-E4

- [ ] **W96-27 (P1) Cleanup tracked ad-hoc prompt artifact** `aidd_test_flow_prompt_ralph_script.txt`, `.gitignore`, `docs/examples/**`, `CHANGELOG.md`, `README.md`, `README.en.md`.
  **AC:** ad-hoc artifact либо удалён из tracking, либо формализован в examples.
  **Carry-over:** W95-F2

- [ ] **W96-28 (P2) Output-contract: from diagnostic to enforceable gate policy input** `tools/output_contract.py`, `tools/loop_step.py`, `tools/gate_workflow.py`, `tools/stage_result.py`, `tests/test_output_contract.py`, `tests/test_loop_step.py`, `tests/test_gate_workflow.py`.
  **AC:** output-contract warnings могут детерминированно влиять на gate/loop decisions per profile.
  **Carry-over:** W89.5-8

- [ ] **W96-29 (P2) Non-blocking recovery for `review_pack_stale` where regeneration succeeds** `tools/loop_step.py`, `tools/loop_run.py`, `tools/review_pack.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`, `tests/test_loop_semantics.py`.
  **AC:** stale-pack recoverable path не блокирует loop-run.
  **Carry-over:** W89.5-9

- [ ] **W96-30 (P2) SKILL-first wrapper contract hardening in loop/gates** `tools/loop_step.py`, `tools/loop_run.py`, `tools/gate_workflow.py`, `skills/implement/scripts/preflight.sh`, `skills/review/scripts/preflight.sh`, `skills/qa/scripts/preflight.sh`, `tests/test_gate_workflow_preflight_contract.py`, `tests/test_loop_step.py`, `tests/repo_tools/smoke-workflow.sh`.
  **AC:** no false-success without mandatory wrapper artifacts + actions log.

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
