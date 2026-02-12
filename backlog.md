# Product Backlog

## Wave 96 — SKILL-first migration program (consolidated)

_Статус: завершен, приоритет 0. Цель — перевести runtime на SKILL-first модель: stage/shared entrypoints и Python runtime живут рядом со SKILL (`skills/*/scripts`, `skills/*/runtime`)._

_Доп. вводные (breaking target): в рамках доработки Wave 96 допускается поломка обратной совместимости ради полного вывода shell runtime из `tools/*.sh`._

### Success Metrics (tracked per checkpoint)

- **M1:** stage-specific entrypoints left in `tools/` (excluding explicit redirect-wrappers) -> target `0` после Phase 1.
  **Check:** `python3 tools/tools_inventory.py --repo-root . --output-json /tmp/aidd_tools_inventory.json --output-md /tmp/aidd_tools_inventory.md` + фильтр по classification.
- **M2:** python-shebang in canonical `.sh` -> target `0`.
  **Check:** `find skills -type f -path '*/scripts/*.sh' -print0 | xargs -0 rg -n '^#!.*python'`.
- **M3:** direct `tools/` refs in agents -> остаются только deferred-core/orchestrator/gates.
  **Check:** `rg '\$\{CLAUDE_PLUGIN_ROOT\}/tools/' agents/`.
- **M4:** direct `tools/` refs in stage skills -> остаются только deferred-core/redirect-wrappers на migration window.
  **Check:** `rg '\$\{CLAUDE_PLUGIN_ROOT\}/tools/' skills/*/SKILL.md`.

Current checkpoint (2026-02-08):
- `M1 = 0` (`tools/` runtime entrypoints outside redirect-wrapper/core_deferred are eliminated).
- `M2 = 0` python-shebang в canonical `skills/*/scripts/*.sh`.
- `M3 = 0` direct `${CLAUDE_PLUGIN_ROOT}/tools/` refs in `agents/*.md`.
- `M4 = 0` direct `${CLAUDE_PLUGIN_ROOT}/tools/` refs in `skills/*/SKILL.md`.

### Phase Plan

- **Phase 0 (обязательное):** policy/guards/inventory + deferred-core freeze/guardrails + test-runner standardization.
- **Phase 1 (обязательное):** stage-local shell relocation (`W96-5..W96-10`) + transition redirect-wrappers + hook/docs dual-path hints.
- **Phase 2 (можно начать):** stage-local python relocation (`W96-11..W96-14`).
- **Phase 3 (после Phase 1):** shared shell relocation to `skills/aidd-core/scripts/*` (`W96-15`) + docs/templates/gates alignment (`W96-1c`, `W96-22`, `W96-23`).
- **Phase 4 (optional, P2):** hardening (`W96-28..W96-30`) after migration baseline is stable.
- **Phase 5 (обязательное, breaking):** tools-free runtime cutover для entrypoints и Python runtime (tools остаётся только для transition stubs/repo tooling) (`W96-32..W96-40`).

### Phase 0 — Policy, Guards, Inventory, Freeze

- [x] **W96-0 (P0) Baseline audit snapshot + migration board refresh** `backlog.md`, `tests/repo_tools/entrypoints-bundle.txt`, `tools/tools_inventory.py`, `tests/repo_tools/lint-prompts.py`:
  - зафиксировать baseline факты и blast radius перед миграцией (consumers matrix по skill/agent/hook/test/docs);
  - синхронизировать sequence коммитов и phase dependencies;
  - зафиксировать M1–M4 baseline values.
  **AC:** backlog и migration board совпадают с фактическим runtime/refs state.
  **Regression/tests:** inventory + lint-prompts.
  **Effort:** S
  **Risk:** Low

- [x] **W96-1a (P0) Stage Lexicon DOC + templates/docs alignment (no runtime validator changes)** `AGENTS.md`, `templates/aidd/AGENTS.md`, `templates/aidd/docs/tasklist/template.md`, `templates/aidd/AGENTS.md`, `README.md`, `README.en.md`:
  - зафиксировать lexicon: public stage `review-spec`; internal substages `review-plan`/`review-prd`;
  - убрать терминологические конфликты в user-facing docs/templates;
  - явно указать alias notes в документации.
  **AC:** docs/templates согласованы по stage lexicon без изменения runtime validators.
  **Regression/tests:** docs checks + prompt-lint.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-1b (P0) Runtime accepts public `review-spec` (alias/umbrella) without drift** `tools/set_active_stage.py`, `tools/context_map_validate.py`, `tools/gate_workflow.py`, `tests/test_set_active_stage.py`, `tests/test_gate_workflow.py`:
  - добавить/выровнять alias handling: `review-spec` как public umbrella stage;
  - сохранить корректную internal маршрутизацию для `review-plan`/`review-prd`;
  - исключить drift между active-stage, scope keys и gate behavior.
  **AC:** runtime корректно принимает `review-spec` и не ломает internal review flow.
  **Regression/tests:** stage alias/unit + gate integration tests.
  **Effort:** M
  **Risk:** High

- [x] **W96-2 (P0) SKILL-first architecture policy contract (docs)** `AGENTS.md`, `templates/aidd/AGENTS.md`, `README.md`, `README.en.md`:
  - stage entrypoints -> `skills/<stage>/scripts/*`;
  - shared entrypoints target -> `skills/aidd-core/scripts/*` (Phase 3);
  - `tools/` -> shared libs/orchestrator + transition redirect-wrappers with transition window.
  **AC:** policy формализована как SoT и совпадает с migration plan.
  **Regression/tests:** lint-prompts + docs consistency checks.
  **Effort:** S
  **Risk:** Medium

- [x] **W96-3a (P0) Guard: canonical `.sh` must be bash (allowlist for fallback redirect-wrappers only)** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/skill-scripts-guard.py`, `tests/repo_tools/runtime-path-regression.sh`:
  - запретить python-shebang для canonical scripts в `skills/**/scripts/*.sh`;
  - добавить allowlist/классификацию fallback redirect-wrappers в `tools/*.sh`;
  - проверять `bash -n` для canonical scripts.
  **AC:** новые canonical scripts всегда bash; нарушения ловятся CI guard.
  **Regression/tests:** ci-lint + skill-scripts-guard + redirect-wrapper-regression.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-3b (P0) Test-runner standardization (no "Ran 0 tests")** `tests/repo_tools/ci-lint.sh`, `.github/workflows/ci.yml`, `pyproject.toml` (если нужно), `AGENTS.md`:
  - выбрать и зафиксировать единый путь исполнения тестов (pytest или unittest);
  - обеспечить реальный запуск ключевых test suites в CI path;
  - добавить guard на пустые test runs.
  **AC:** ключевые тестовые наборы исполняются; нет "Ran 0 tests" в целевом CI path.
  **Regression/tests:** `tests/repo_tools/ci-lint.sh` + selected test runner step.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-4 (P1) Canonical wrapper template + python bootstrap policy** `skills/aidd-reference/wrapper_lib.sh`, `AGENTS.md`, `templates/aidd/AGENTS.md`, `skills/*/scripts/*.sh`:
  - зафиксировать единый шаблон stage wrappers (`#!/usr/bin/env bash`, `set -euo pipefail`, guarded output);
  - стандартизировать bootstrap (`CLAUDE_PLUGIN_ROOT`, `PYTHONPATH`);
  - описать минимальный output/log contract для wrappers.
  **AC:** wrapper template единый и используемый для новых canonical scripts.
  **Regression/tests:** skill-scripts-guard + smoke wrapper flow.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-19 (P1) Tools inventory v2: canonical/redirect-wrapper/shared + consumers matrix** `tools/tools_inventory.py`, `tests/test_tools_inventory.py`, `tests/repo_tools/ci-lint.sh`, `README.md`, `README.en.md`, `AGENTS.md`:
  - добавить классификацию: `canonical_stage`, `shared_skill`, `redirect-wrapper`, `core_api_deferred`;
  - добавить consumer types: `agent`, `skill`, `hook`, `test`, `docs`, `redirect-wrapper`;
  - показывать `canonical_replacement_path` для redirect-wrapper entries.
  **AC:** inventory отражает migration status без false "unused".
  **Regression/tests:** test_tools_inventory + ci-lint guard.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-24 (P0) Deferred-core API freeze (stable external API, internal redirect-wrapper allowed)** `tools/init.sh`, `tools/research.sh`, `tools/tasks-derive.sh`, `tools/actions-apply.sh`, `tools/context-expand.sh`, `tests/test_init_aidd.py`, `tests/test_research_rlm_e2e.py`, `tests/test_tasks_derive.py`, `tests/test_context_expand.py`:
  - зафиксировать публичный контракт `tools/<entrypoint>`: путь/флаги/help/exit-code/hints стабильны в wave-1;
  - разрешить internal refactor: `tools/<entrypoint>` может стать redirect-wrapper на canonical `skills/.../scripts/...`, но без изменения внешнего контракта;
  - добавить contract tests на flags/help/exit codes/hints.
  **AC:** deferred-core APIs стабильны externally, internal redirect-wrapper strategy поддерживается тестами.
  **Regression/tests:** contract tests per deferred-core entrypoint + smoke.
  **Effort:** M
  **Risk:** High

- [x] **W96-25 (P1) Do-not-migrate guardrails for deferred-core APIs** `tests/repo_tools/lint-prompts.py`, `tools/tools_inventory.py`, `tests/test_tools_inventory.py`, `tests/repo_tools/ci-lint.sh`, `AGENTS.md`, `README.md`, `README.en.md`:
  - пометить deferred-core APIs в inventory (`core_api=true`, `migration_deferred=true`);
  - блокировать silent relocation без redirect-wrapper + migration note;
  - синхронизировать policy/CI/docs.
  **AC:** accidental relocation deferred-core APIs без compat слоя блокируется.
  **Regression/tests:** inventory/lint unit tests + CI scenario.
  **Effort:** S
  **Risk:** Medium

### Phase 1 — Stage-local shell relocation (required)

- [x] **W96-5 (P1) IDEA: relocate `analyst-check` to stage scripts + redirect-wrapper** `skills/idea-new/scripts/analyst-check.sh`, `skills/idea-new/SKILL.md`, `tools/analyst-check.sh`, `README.md`, `README.en.md`, `tests/repo_tools/runtime-path-regression.sh`.
- [x] **W96-6 (P1) PLAN: relocate `research-check` to stage scripts + redirect-wrapper** `skills/plan-new/scripts/research-check.sh`, `skills/plan-new/SKILL.md`, `tools/research-check.sh`, `README.md`, `README.en.md`, `tests/repo_tools/runtime-path-regression.sh`.
- [x] **W96-7 (P1) REVIEW-SPEC: relocate `prd-review` to stage scripts + redirect-wrapper** `skills/review-spec/scripts/prd-review.sh`, `skills/review-spec/SKILL.md`, `tools/prd-review.sh`, `tests/test_prd_review_agent.py`, `tests/repo_tools/runtime-path-regression.sh`.
- [x] **W96-8 (P1) RESEARCHER: relocate `research/reports-pack/rlm-*` wrappers to stage scripts + redirect-wrappers** `skills/researcher/scripts/*.sh`, `tools/research.sh`, `tools/reports-pack.sh`, `tools/rlm-*.sh`, `skills/researcher/SKILL.md`, `agents/researcher.md`, `tests/repo_tools/runtime-path-regression.sh`.
- [x] **W96-9 (P1) QA: canonical `skills/qa/scripts/qa.sh` + redirect-wrapper** `skills/qa/scripts/qa.sh`, `skills/qa/SKILL.md`, `tools/qa.sh`, `templates/aidd/config/gates.json`, `hooks/gate-qa.sh`, `tests/helpers.py`, `tests/test_qa_runner.py`.
- [x] **W96-10 (P1) STATUS: canonical `skills/status/scripts/status.sh` + `index-sync.sh` + redirect-wrappers** `skills/status/scripts/status.sh`, `skills/status/scripts/index-sync.sh`, `skills/status/SKILL.md`, `tools/status.sh`, `tools/index-sync.sh`, `README.md`, `README.en.md`, `tests/test_status.py`.
  **AC (for W96-5..W96-10):** canonical stage-local entrypoints используются stage skills; старые `tools/*.sh` остаются transition redirect-wrappers (stderr REDIRECT + exec canonical).
  **Regression/tests:** `bash tests/repo_tools/runtime-path-regression.sh`, stage-specific unit/integration tests, smoke-workflow.

- [x] **W96-21 (P1) Hook/docs hints: canonical + phased-out redirect-wrapper dual-path** `hooks/context_gc/pretooluse_guard.py`, `hooks/gate-tests.sh`, `hooks/gate-qa.sh`, `tools/gate_workflow.py`, `README.md`, `README.en.md`, `docs/fallback/commands/*.md`, `templates/aidd/AGENTS.md`:
  - заменить hints на canonical `skills/<stage>/scripts/*`;
  - оставить fallback `tools/*` только как phased-out transition note.
  **AC:** hooks/docs не рекомендуют неактуальный путь как primary.
  **Regression/tests:** hook tests + docs/lint checks.
  **Effort:** S
  **Risk:** Low

- [x] **W96-31 (P2, W96-X) gate-api-contract: decide (remove or wire) + docs note** `hooks/gate-api-contract.sh`, `hooks/hooks.json`, `tests/test_wave95_policy_guards.py`, `AGENTS.md`, `README.md`:
  - проверить текущее состояние gate-api-contract (stub/unwired/removed);
  - выбрать один вариант: окончательно удалить и вычистить refs, либо полноценно wire + покрыть тестом;
  - зафиксировать решение в docs/backlog notes.
  **AC:** нет мёртвой placeholder-логики gate-api-contract без явного решения.
  **Regression/tests:** `tests/test_wave95_policy_guards.py` + hook wiring checks.
  **Effort:** S
  **Risk:** Low

### Phase 2 — Stage-local python relocation (can be partial in this PR)

- [x] **W96-11 (P1) Relocate stage-specific python modules (idea/plan/review-spec) + compat stubs** `skills/idea-new/runtime/analyst_check.py`, `skills/plan-new/runtime/research_check.py`, `skills/review-spec/runtime/prd_review.py`, `tools/analyst_check.py`, `tools/research_check.py`, `tools/prd_review.py`.
- [x] **W96-12 (P1) Relocate researcher python modules + compat stubs** `skills/researcher/runtime/*.py`, `tools/reports_pack.py`, `tools/rlm_*.py`, `tools/research.py`.
- [x] **W96-13 (P1) Relocate review python modules + compat stubs** `skills/review/runtime/*.py`, `tools/context_pack.py`, `tools/review_pack.py`, `tools/review_report.py`, `tools/reviewer_tests.py`.
- [x] **W96-14 (P1) Lint/guards for `skills/<stage>/runtime/*`** `tests/repo_tools/lint-prompts.py`, `tests/repo_tools/skill-scripts-guard.py`, `tests/test_prompt_lint.py`, `AGENTS.md`.
  **AC (for W96-11..W96-14):** stage-specific python logic может жить рядом со skill без потери transition через tools stubs.

### Phase 3 — Shared shell relocation + full alignment

- [x] **W96-15 (P1) Relocate shared multi-stage shell entrypoints to `skills/aidd-core/scripts/*` + redirect-wrappers in tools** `skills/aidd-core/scripts/*.sh`, `tools/set-active-stage.sh`, `tools/set-active-feature.sh`, `tools/progress.sh`, `tools/stage-result.sh`, `tools/status-summary.sh`, `tools/tasklist-*.sh`, `tools/prd-check.sh`, `tools/diff-boundary-check.sh`.

- [x] **W96-16 (P1) Shared RLM skill for SUBAGENT preload only (`agents/*.md`)** `skills/aidd-rlm/SKILL.md`, `agents/*.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `tests/repo_tools/entrypoints-bundle.txt`:
  - добавить compact shared skill `aidd-rlm` для subagent preload;
  - обновлять `agents/*.md` frontmatter `skills:` на `aidd-rlm` where needed;
  - **не** добавлять `skills:` inheritance в `skills/*/SKILL.md`.
  **AC:** subagents preload RLM guidance через `skills:`; stage skills без skills-in-skills inheritance.
  **Regression/tests:** prompt-lint + entrypoints bundle checks.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-17 (P1) Shared implement/review/qa toolset contract without skills-in-skills inheritance** `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `skills/aidd-core/scripts/*`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - убрать reliance on inheritance in `SKILL.md`;
  - консолидировать общий toolset через shared canonical entrypoints и (опционально) генерацию allowed-tools baselines;
  - если preload нужен — только для subagents, не для stage skills.
  **AC:** implement/review/qa согласованы по shared toolset без skills-in-skills механики.
  **Regression/tests:** prompt-lint/baseline parity.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-18 (P1) Agent skill preload validation contract** `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `agents/*.md`:
  - lint проверяет `agents/*.md` frontmatter `skills:` -> существующий `skills/<name>/SKILL.md`;
  - lint запрещает в агентах прямые refs на stage-local `tools/<stage-specific>.sh` (кроме deferred-core/orchestrator/gates);
  - lint требует canonical refs `skills/<stage>/scripts/*` или shared skill scripts where applicable.
  **AC:** agent frontmatter preload refs валидны; direct stage-local tool refs в agents блокируются.
  **Regression/tests:** prompt-lint unit/integration coverage for agent rules.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-1c (P1) Full stage lexicon alignment after entrypoint relocation** `tools/set_active_stage.py`, `tools/context_map_validate.py`, `templates/aidd/docs/tasklist/template.md`, `templates/aidd/config/gates.json`, `tools/gate_workflow.py`, `README.md`, `README.en.md`:
  - завершить согласование runtime + templates + gates после фактической миграции entrypoints;
  - удалить transitional drift и неактуальные aliases where safe;
  - закрепить финальный contract в docs/tests.
  **AC:** runtime/templates/gates работают в едином lexicon без конфликтов и скрытых alias regressions.
  **Regression/tests:** gate/integration + smoke.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-22 (P1) Templates/docs per-stage structure** `templates/aidd/docs/shared/stage-lexicon.md`, `templates/aidd/docs/tasklist/template.md`, `templates/aidd/docs/prd/template.md`, `templates/aidd/docs/plan/template.md`, `templates/aidd/docs/research/template.md`.
- [x] **W96-23 (P1) Gates/config alignment to new canonical paths** `templates/aidd/config/gates.json`, `tools/gate_workflow.py`, `tools/research_guard.py`, `tools/status.py`, `tools/index_sync.py`, `tests/test_gate_workflow.py`, `tests/test_gate_qa.py`.

### Phase 4 — Optional hardening (P2)

- [x] **W96-26 (P2) Phase-2 blueprint: deferred-core and review-redirect-wrapper removal windows** `AGENTS.md`, `CHANGELOG.md`, `docs/fallback/commands/*.md`, `tests/repo_tools/runtime-path-regression.sh`:
  - зафиксировать removal windows для transition redirect-wrappers;
  - включить план удаления review redirect-wrappers (`tools/review-pack.sh`, `tools/review-report.sh`, `tools/reviewer-tests.sh`).
  **AC:** есть согласованный Phase-2 removal plan with rollback criteria.
  **Carry-over:** W95-E4

- [x] **W96-27 (P1) Cleanup tracked ad-hoc prompt artifact** `aidd_test_flow_prompt_ralph_script.txt`, `.gitignore`, `docs/examples/**`, `CHANGELOG.md`, `README.md`, `README.en.md`.
  **AC:** ad-hoc artifact либо удалён из tracking, либо формализован в examples.
  **Carry-over:** W95-F2

- [x] **W96-28 (P2) Output-contract: from diagnostic to enforceable gate policy input** `tools/output_contract.py`, `tools/loop_step.py`, `tools/gate_workflow.py`, `tools/stage_result.py`, `tests/test_output_contract.py`, `tests/test_loop_step.py`, `tests/test_gate_workflow.py`.
  **AC:** output-contract warnings могут детерминированно влиять на gate/loop decisions per profile.
  **Carry-over:** W89.5-8

- [x] **W96-29 (P2) Non-blocking recovery for `review_pack_stale` where regeneration succeeds** `tools/loop_step.py`, `tools/loop_run.py`, `tools/review_pack.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`, `tests/test_loop_semantics.py`.
  **AC:** stale-pack recoverable path не блокирует loop-run.
  **Carry-over:** W89.5-9

- [x] **W96-30 (P2) SKILL-first wrapper contract hardening in loop/gates** `tools/loop_step.py`, `tools/loop_run.py`, `tools/gate_workflow.py`, `skills/implement/scripts/preflight.sh`, `skills/review/scripts/preflight.sh`, `skills/qa/scripts/preflight.sh`, `tests/test_gate_workflow_preflight_contract.py`, `tests/test_loop_step.py`, `tests/repo_tools/smoke-workflow.sh`.
  **AC:** no false-success without mandatory wrapper artifacts + actions log.

### Phase 5 — Full `tools/` retirement (required, breaking)

- [x] **W96-32 (P0) Breaking migration contract + release policy for shell tools-free runtime** `AGENTS.md`, `README.md`, `README.en.md`, `CHANGELOG.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`:
  - зафиксировать целевой state: shell runtime entrypoints только в `skills/*/scripts/*` и `hooks/*`;
  - явно задокументировать breaking change policy и migration notes для shell API (`tools/*.sh` retired);
  - выровнять release metadata под breaking-wave.
  **AC:** policy/docs/metadata однозначно описывают shell tools-free runtime и breaking semantics.
  **Regression/tests:** docs lint + metadata consistency checks.
  **Effort:** S
  **Risk:** Medium

- [x] **W96-33 (P0) CI guardrails: block any new runtime dependency on `tools/`** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/lint-prompts.py`, `tests/repo_tools/skill-scripts-guard.py`, `tests/repo_tools/bash-runtime-guard.py`, `tests/test_prompt_lint.py`:
  - добавить fail-fast guard: runtime/skills/hooks/agents/templates не должны ссылаться на `tools/*.sh` (кроме тестовых allowlist-фикстур);
  - запретить `${CLAUDE_PLUGIN_ROOT}/tools/...*.sh` в canonical runtime paths;
  - добавить отчёт о нарушениях в CI.
  **AC:** новые/сохранившиеся runtime refs на `tools/*.sh` детерминированно блокируются в CI.
  **Regression/tests:** prompt-lint + guard unit/integration tests.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-34 (P1) Relocate remaining shared shell entrypoints out of `tools/` (no redirect-wrappers)** `skills/aidd-core/scripts/*.sh`, `skills/aidd-loop/scripts/*.sh`, `skills/*/scripts/*.sh`, `tools/*.sh`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/runtime-path-regression.sh`:
  - перенести оставшиеся shared shell entrypoints (`actions-validate`, `context-map-validate`, `loop-run`, `loop-step`, `doctor`, `md-*`, `*-review-gate`, `researcher-context`, `skill-contract-validate`, `tests-log`, `tools-inventory`) в canonical scripts под skills/hooks;
  - убрать redirect-wrapper-pattern и transition dual-path для этих entrypoints;
  - обновить smoke/регрессии под canonical-only вызовы.
  **AC:** runtime shell entrypoints не живут в `tools/`; redirect-wrapper-regression больше не требуется для удалённых путей.
  **Regression/tests:** smoke-workflow + repo tools regression suite.
  **Effort:** L
  **Risk:** High

- [x] **W96-35 (P1) Hook/runtime decoupling from `tools/*` execution paths** `hooks/*.sh`, `hooks/**/*.py`, `hooks/runtime/*.py`, `hooks/context_gc/pretooluse_guard.py`, `tests/test_gate_workflow*.py`, `tests/test_wave95_policy_guards.py`:
  - убрать shell-зависимости hook-ов от `tools/*.sh` и перевести на canonical `skills/*/scripts/*`;
  - переключить Python execution paths на `skills/*/runtime/*` (через wrappers/stubs);
  - обновить hook wiring/tests без fallback на `tools/*.sh`.
  **AC:** hooks выполняются без вызовов `tools/*.sh`; Python runtime исполняется из `skills/*/runtime/*`.
  **Regression/tests:** hook unit/integration + policy guard tests.
  **Effort:** L
  **Risk:** High

- [x] **W96-36 (P1) Shared Python runtime relocation to skill-owned runtime dirs** `skills/aidd-core/runtime/*.py`, `skills/aidd-loop/runtime/*.py`, `skills/aidd-init/runtime/*.py`, `skills/*/scripts/*.sh`, `tests/test_*`:
  - перенести shared Python runtime в `skills/*/runtime/*` по ownership (core/loop/init);
  - обновить canonical wrappers на запуск runtime из `skills/*/runtime/*`;
  - оставить `tools/*.py` только как transition import stubs/repo tooling.
  **AC:** shared runtime исполняется из `skills/*/runtime/*`; `tools/*.py` не является primary execution path.
  **Regression/tests:** unit + smoke + workflow integration.
  **Effort:** L
  **Risk:** High

- [x] **W96-37 (P1) Stage runtime completion: remove proxy wrappers in `skills/*/runtime`** `skills/idea-new/runtime/*.py`, `skills/plan-new/runtime/*.py`, `skills/review-spec/runtime/*.py`, `skills/researcher/runtime/*.py`, `skills/review/runtime/*.py`, `skills/qa/runtime/*.py`, `skills/status/runtime/*.py`, `tests/test_*`:
  - заменить текущие proxy-обёртки в stage runtime на реальные модули (без `from tools import ... as tools_module`);
  - привести imports/stage scripts к локальному runtime пути;
  - обновить stage-specific тесты.
  **AC:** `skills/<stage>/runtime/*` не содержит прокси на `tools`; stage flows проходят на локальном runtime.
  **Regression/tests:** stage unit/integration + smoke.
  **Effort:** L
  **Risk:** High

- [x] **W96-38 (P1) Canonical-path sweep in prompts/docs/templates/configs (tools-free runtime references)** `AGENTS.md`, `templates/aidd/AGENTS.md`, `templates/aidd/docs/**`, `templates/aidd/config/*.json`, `README.md`, `README.en.md`, `agents/*.md`, `skills/*/SKILL.md`, `hooks/*.sh`, `hooks/**/*.py`:
  - удалить/заменить все user-facing и hook hints c `tools/*` на canonical paths в `skills/*/scripts/*`, `skills/*/runtime/*` и `hooks/*`;
  - убрать fallback/transition примечания про `tools` из документации migration window;
  - синхронизировать prompt conventions и gate/config references.
  **AC:** в docs/prompts/config/hints нет runtime references на `tools/*`.
  **Regression/tests:** prompt lint + docs consistency + hook hint checks.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-39 (P1) Tests/CI harness migration to tools-free runtime layout** `tests/**/*.py`, `tests/repo_tools/*.sh`, `.github/workflows/ci.yml`, `tests/helpers.py`, `tests/test_deferred_core_api_contract.py`:
  - переписать тестовые harness/фикстуры с `tools/*` на canonical skills/hooks/runtime paths;
  - удалить/заменить contract tests, завязанные на deferred-core APIs в `tools/*`;
  - выровнять CI path filters и smoke сценарии под новый layout.
  **AC:** CI/smoke/test helpers не используют `tools/*`; regression coverage сохранена.
  **Regression/tests:** full `tests/repo_tools/ci-lint.sh` + `tests/repo_tools/smoke-workflow.sh` + targeted pytest.
  **Effort:** M
  **Risk:** High

- [x] **W96-40 (P0) Final runtime cutover: retire `tools/*.sh` and demote `tools/*.py` to transition layer** `tools/**`, `AGENTS.md`, `README.md`, `README.en.md`, `tests/repo_tools/ci-lint.sh`, `.github/workflows/ci.yml`:
  - удалить все runtime shell entrypoints из `tools/` и запретить их возвращение guard-ами;
  - перевести runtime execution на `skills/*/runtime/*`; `tools/*.py` оставить как transition import stubs;
  - проверить install/smoke/workflow после cutover.
  **AC:** `tools/*.sh` отсутствуют; primary runtime execution path — `skills/*/scripts/*` + `skills/*/runtime/*` + `hooks/*`.
  **Regression/tests:** full CI lint + smoke-workflow + critical stage flows.
  **Effort:** M
  **Risk:** High

- [x] **W96-41 (P0) Shared scripts ownership map: 1 owner = 1 canonical skill/hook path** `backlog.md`, `AGENTS.md`, `README.md`, `README.en.md`, `aidd/reports/tools/*.json`:
  - зафиксировать owner-matrix для оставшихся shared entrypoints (`loop-run`, `loop-step`, `doctor`, `dag-export`, `identifiers`, `skill-contract-validate`, `tests-log`, `tools-inventory`, `plan-review-gate`, `prd-review-gate`, `researcher-context`);
  - для каждого entrypoint определить только один canonical owner (`skills/<name>/scripts/*` или `hooks/*`) и migration destination;
  - отметить phased-out/removed candidates без canonical owner (если функциональность дублируется).
  **AC:** каждый shared entrypoint имеет однозначный owner и target path; нет "orphan/shared без владельца".
  **Regression/tests:** tools-inventory + docs consistency checks.
  **Effort:** S
  **Risk:** Medium

- [x] **W96-42 (P1) Execute ownership map: relocate all remaining `shared_tool` entrypoints** `skills/aidd-core/scripts/*.sh`, `skills/aidd-loop/scripts/*.sh`, `skills/aidd-init/scripts/*.sh`, `skills/aidd-maintainer/scripts/*.sh`, `hooks/*.sh`, `tools/*.sh`, `tests/repo_tools/smoke-workflow.sh`:
  - перенести оставшиеся `shared_tool` скрипты по owner-map в canonical skills/hooks paths;
  - удалить `researcher-context` path, если RLM-only pipeline покрывает сценарий без регресса;
  - обновить smoke/CLI examples на новые canonical entrypoints.
  **AC:** в inventory нет classification=`shared_tool`; все entrypoints либо canonical (`skills/hooks`), либо удалены.
  **Regression/tests:** smoke-workflow + loop/gate regression + inventory diff.
  **Effort:** L
  **Risk:** High

- [x] **W96-43 (P0) Command-skill execution contract: agents do not call wrappers directly** `AGENTS.md`, `templates/aidd/AGENTS.md`, `agents/*.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - закрепить контракт: wrappers (`skills/*/scripts/*`) вызываются только command-skills/hooks, не subagents;
  - запретить в `agents/*.md` прямые `Bash(${CLAUDE_PLUGIN_ROOT}/skills/*/scripts/*.sh *)` refs;
  - добавить lint-правило и migration notes для agent prompts.
  **AC:** агенты работают через артефакты и общий toolset; orchestration wrappers принадлежат command-skills/hooks.
  **Regression/tests:** prompt-lint unit/integration coverage for agent wrapper ban.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-44 (P1) User-invocable skills: local script ownership and no `tools/*` fallback** `skills/*/SKILL.md`, `skills/*/scripts/*.sh`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `README.md`, `README.en.md`:
  - привести user-invocable skills (`aidd-init`, `researcher`, `review`, `qa`, и др.) к вызову только canonical `skills/*/scripts/*` и `hooks/*`;
  - убрать остаточные `tools/*` refs в `allowed-tools` и steps;
  - валидировать, что у каждой user-invocable команды есть owner scripts по необходимости.
  **AC:** в user-invocable `SKILL.md` отсутствуют runtime refs на `tools/*`; command skills полностью self-contained по скриптам.
  **Regression/tests:** prompt-lint + skill contract checks + smoke for user commands.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-45 (P1) Deferred-core decomposition into skill owners (breaking)** `skills/aidd-init/scripts/*.sh`, `skills/researcher/scripts/*.sh`, `skills/aidd-core/scripts/*.sh`, `hooks/*.sh`, `tools/init.sh`, `tools/research.sh`, `tools/tasks-derive.sh`, `tools/actions-apply.sh`, `tools/context-expand.sh`:
  - разложить бывшие deferred-core API по ownership: init -> `aidd-init`, research -> `researcher`, tasks-derive/actions/context-expand -> `aidd-core`/hooks;
  - удалить deferred-core freeze assumptions и contract tests, ожидающие `tools/*` API;
  - выровнять вызовы в hooks/skills/docs на новые owner entrypoints.
  **AC:** бывшие deferred-core сценарии доступны только через canonical skills/hooks paths без `tools/*` API.
  **Regression/tests:** workflow integration + gate-tests + qa/research/tasklist paths.
  **Effort:** L
  **Risk:** High

### Phase 6 — Findings-driven decomposition program (SKILL-first v2)

#### Phase 6A — Skill contract hardening

- [x] **W96-58 (P0) Enforce stage command ownership: every user-invocable skill has canonical `scripts/run.sh`** `skills/*/SKILL.md`, `skills/*/scripts/run.sh`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - ввести контракт ownership: user-invocable stage skill обязан иметь локальный command entrypoint `skills/<stage>/scripts/run.sh`;
  - обновить skills без `run.sh` и синхронизировать их `allowed-tools`/Steps;
  - добавить lint guard на отсутствие canonical run-wrapper.
  **AC:** 100% user-invocable skills имеют собственный `scripts/run.sh` и проходят lint contract.
  **Deps:** -
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-59 (P1) Allowed-tools ownership contract for stage skills (own scripts + shared skills only)** `skills/*/SKILL.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - запретить refs на чужие stage-local wrappers, кроме canonical shared skills (`aidd-core`, `aidd-loop`, `aidd-rlm`, новые shared skills после split);
  - проверить, что stage skill вызывает собственные wrappers для stage-specific операций;
  - добавить whitelist/owner-map в lint.
  **AC:** stage skills используют только own scripts + approved shared scripts.
  **Deps:** W96-58
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-60 (P1) SKILL compactness + supporting-files policy** `skills/*/SKILL.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `AGENTS.md`:
  - закрепить policy: `SKILL.md` компактный (target <= 500 lines), детальные инструкции выносятся в supporting files;
  - нормализовать секции `Additional resources` (когда и зачем загружать references/templates);
  - добавить lint warning/error thresholds для oversized skills.
  - status note: закрыто в рамках Wave 97 (`W97-10`, `W97-11`) как superseding contract.
  **AC:** oversized skills покрыты policy и lint guards; supporting-files navigation явная.
  **Deps:** W96-58
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** S
  **Risk:** Low

#### Phase 6B — Close zero-owner stage skills

- [x] **W96-61 (P0) `spec-interview` self-owned command wrapper + stage runtime module** `skills/spec-interview/scripts/run.sh`, `skills/spec-interview/runtime/spec_interview.py`, `skills/spec-interview/SKILL.md`, `tests/test_cli_subcommands.py`, `tests/repo_tools/smoke-workflow.sh`:
  - добавить canonical `run.sh` для `spec-interview`;
  - вынести stage-specific orchestration в `runtime/spec_interview.py`;
  - обновить command contract/steps в `SKILL.md`.
  **AC:** `spec-interview` полностью self-owned (command wrapper + runtime) без косвенной зависимости на чужие stage wrappers.
  **Deps:** W96-58, W96-59
  **Regression/tests:** `python3 -m pytest -q tests/test_cli_subcommands.py`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-62 (P0) `tasks-new` self-owned command wrapper + stage runtime module** `skills/tasks-new/scripts/run.sh`, `skills/tasks-new/runtime/tasks_new.py`, `skills/tasks-new/SKILL.md`, `tests/test_tasklist_check.py`, `tests/repo_tools/smoke-workflow.sh`:
  - добавить canonical `run.sh` для `tasks-new`;
  - вынести stage-specific orchestration/normalize в `runtime/tasks_new.py`;
  - синхронизировать steps/allowed-tools с новым ownership.
  **AC:** `tasks-new` полностью self-owned (command wrapper + runtime) и проходит stage checks.
  **Deps:** W96-58, W96-59
  **Regression/tests:** `python3 -m pytest -q tests/test_tasklist_check.py`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-63 (P1) Stage-owner completeness guard for user commands** `tests/repo_tools/skill-scripts-guard.py`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - добавить repo guard на “нулевых владельцев” (user-invocable skill без local scripts/runtime owner);
  - валидировать согласованность `agent`/`context`/`run.sh` presence;
  - добавить понятный report по owner gaps.
  **AC:** owner gaps ловятся guard-ами до merge.
  **Deps:** W96-58, W96-59, W96-61, W96-62
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** S
  **Risk:** Low

#### Phase 6C — Decompose `aidd-core` into bounded shared skills

- [x] **W96-64 (P0) Create `aidd-policy` shared skill (contract/prompt policy)** `skills/aidd-policy/SKILL.md`, `skills/aidd-policy/references/*`, `agents/*.md`, `.claude-plugin/plugin.json`:
  - вынести output contract/question format/read-policy/wrapper-safety из `aidd-core`;
  - подключить `aidd-policy` в preload у subagents;
  - оставить `aidd-core` как runtime-ориентированный слой без policy-monolith.
  **AC:** policy guidance живёт в dedicated shared skill и переиспользуется агентами.
  **Deps:** W96-60
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-65 (P0) Create `aidd-docio` shared skill and relocate DocIO runtime ownership** `skills/aidd-docio/SKILL.md`, `skills/aidd-docio/runtime/*.py`, `skills/aidd-core/runtime/{md_*,actions_*,context_*}.py`:
  - перенести `md-slice`, `md-patch`, `actions-*`, `context-*` в `aidd-docio`;
  - обновить все consumers (skills/hooks/tests/docs) на новые canonical paths;
  - оставить минимально необходимые compatibility redirects на migration window (если нужно).
  **AC:** DocIO surface полностью принадлежит `aidd-docio`, без дубли ownership в `aidd-core`.
  **Deps:** W96-59
  **Regression/tests:** `python3 -m pytest -q tests/test_md_slice.py tests/test_context_expand.py tests/test_output_contract.py`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** L
  **Risk:** High

- [x] **W96-66 (P0) Create `aidd-flow-state` shared skill and relocate flow/state runtime ownership** `skills/aidd-flow-state/SKILL.md`, `skills/aidd-flow-state/runtime/*.py`, `skills/aidd-core/runtime/{set_active_*,progress*,tasklist_check,tasks_derive,stage_result,status_summary,prd_check}.py`:
  - вынести flow-state инструменты в отдельный shared skill;
  - синхронизировать все stage skill refs на новый canonical owner;
  - добавить owner-map validation для flow-state API.
  **AC:** flow-state API полностью принадлежит `aidd-flow-state`.
  **Deps:** W96-59
  **Regression/tests:** `python3 -m pytest -q tests/test_progress.py tests/test_tasklist_check.py tests/test_gate_workflow*.py`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** L
  **Risk:** High

- [x] **W96-67 (P1) Create `aidd-observability` shared skill and relocate observability runtime ownership** `skills/aidd-observability/SKILL.md`, `skills/aidd-observability/runtime/*.py`, `skills/aidd-core/runtime/{doctor,tools_inventory,tests_log,dag_export,identifiers}.py`:
  - вынести observability/reporting utilities из `aidd-core`;
  - обновить CI/docs/inventory consumers;
  - закрепить observability API contract в tests.
  **AC:** observability API имеет отдельного owner и независимый lifecycle.
  **Deps:** W96-59
  **Regression/tests:** `python3 -m pytest -q tests/test_tools_inventory.py tests/test_tests_log.py tests/test_error_output.py`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-68 (P1) Convert `aidd-core` into thin aggregator/navigation skill** `skills/aidd-core/SKILL.md`, `.claude-plugin/plugin.json`, `AGENTS.md`, `README.md`, `README.en.md`:
  - оставить в `aidd-core` только shared runtime navigation + cross-skill links;
  - убрать из `aidd-core` перегруженные policy/procedure блоки после split;
  - обновить plugin/docs чтобы отражать новую shared-skill topology.
  **AC:** `aidd-core` не является monolith SoT, а выступает в роли aggregator.
  **Deps:** W96-64, W96-65, W96-66, W96-67
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** S
  **Risk:** Medium

#### Phase 6D — Normalize RLM ownership

- [x] **W96-69 (P0) Move canonical RLM entrypoints to `skills/aidd-rlm/runtime/*`** `skills/aidd-rlm/SKILL.md`, `skills/aidd-rlm/runtime/*.py`, `skills/researcher/SKILL.md`, `agents/*.md`, `tests/test_rlm_wrappers.py`:
  - перенести shared RLM command surface в `aidd-rlm` (canonical Python runtime);
  - обновить `aidd-rlm` preload docs/allowed-tools на собственные runtime entrypoints;
  - оставить `researcher` stage ownership только для stage orchestration (`research.py`).
  **AC:** shared RLM API owned by `aidd-rlm`, а не stage-local `researcher`.
  **Deps:** W96-64
  **Regression/tests:** `python3 -m pytest -q tests/test_rlm_wrappers.py tests/test_research_rlm_e2e.py`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-70 (P1) Researcher stage boundary cleanup after RLM ownership move** `skills/researcher/SKILL.md`, `skills/researcher/runtime/research.py`, `skills/researcher/runtime/*.py`, `agents/researcher.md`:
  - зафиксировать, что `researcher` владеет stage pipeline orchestration, но не shared RLM API;
  - убрать скрытые cross-owner зависимости в steps/allowed-tools;
  - обновить stage docs/tests под новый ownership.
  **AC:** responsibilities `aidd-rlm` vs `researcher` чётко разделены и проверяемы.
  **Deps:** W96-69
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_research_rlm_e2e.py`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** M
  **Risk:** Medium

#### Phase 6E — Runtime module decomposition

- [x] **W96-71 (P1) Decompose `tasklist_check.py` into bounded modules** `skills/aidd-flow-state/runtime/tasklist_check.py`, `skills/aidd-flow-state/runtime/tasklist_*`, `tests/test_tasklist_check.py`:
  - разрезать модуль по domain units (parsing, validation, reporting, normalization);
  - сохранить CLI/output compatibility;
  - уменьшить когнитивную и тестовую связанность.
  **AC:** largest module decomposition completed; responsibilities isolated per module.
  **Deps:** W96-63
  **Regression/tests:** `python3 -m pytest -q tests/test_tasklist_check.py tests/test_cli_subcommands.py`.
  **Effort:** L
  **Risk:** High

- [x] **W96-72 (P1) Decompose `loop_step.py` into orchestration + policy + result handlers** `skills/aidd-loop/runtime/loop_step.py`, `skills/aidd-loop/runtime/loop_step_*`, `tests/test_loop_step.py`, `tests/test_gate_workflow_preflight_contract.py`:
  - вынести decision policy, preflight integration, result processing в отдельные модули;
  - снизить coupling с gate/workflow runtime;
  - сохранить deterministic behavior loop-step.
  **AC:** `loop_step` module split завершён без regressions по loop semantics.
  **Deps:** W96-63
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_semantics.py tests/test_gate_workflow_preflight_contract.py`.
  **Effort:** L
  **Risk:** High

- [x] **W96-73 (P1) Decompose `researcher_context.py` into read-budget/context-pack components** `skills/aidd-core/runtime/researcher_context.py`, `skills/aidd-core/runtime/researcher_context_*`, `tests/test_researcher_context.py`:
  - выделить selection/ranking/pack-shaping logic в отдельные units;
  - улучшить testability для read-budget поведения;
  - сохранить output compatibility для context artifacts.
  **AC:** context builder split на bounded components с сохранением контракта output.
  **Deps:** W96-63
  **Regression/tests:** `python3 -m pytest -q tests/test_researcher_context.py tests/test_reports_pack.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-74 (P1) Decompose `reports_pack.py` for deterministic pack assembly** `skills/aidd-rlm/runtime/reports_pack.py`, `skills/aidd-rlm/runtime/reports_pack_*`, `tests/test_reports_pack.py`:
  - выделить normalization/budget trim/serialization в отдельные модули;
  - зафиксировать deterministic behavior (stable ids/order/truncation);
  - снизить blast radius изменений в research pack pipeline.
  **AC:** pack assembly модульно разложен, deterministic guarantees покрыты тестами.
  **Deps:** W96-69, W96-70
  **Regression/tests:** `python3 -m pytest -q tests/test_reports_pack.py tests/test_research_rlm_e2e.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-75 (P2) Runtime module size/composition guard** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/runtime-module-guard.py`, `AGENTS.md`:
  - добавить repo guard для крупных runtime-модулей (warning -> error rollout);
  - задать target thresholds (например, >600 lines = warning, >900 = error);
  - документировать исключения/waivers.
  **AC:** новые runtime monoliths блокируются/сигнализируются автоматически.
  **Deps:** W96-71, W96-72, W96-73, W96-74
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`.
  **Effort:** S
  **Risk:** Low

#### Phase 6F — Agent preload matrix v2

- [x] **W96-76 (P1) Roll out preload matrix v2 by role** `agents/*.md`, `skills/aidd-policy/SKILL.md`, `skills/aidd-rlm/SKILL.md`, `skills/aidd-loop/SKILL.md`:
  - `aidd-policy` preload для всех subagents;
  - `aidd-rlm` preload только для analyst/planner/plan-reviewer/prd-reviewer/researcher/reviewer/spec-interview-writer/tasklist-refiner/validator;
  - `aidd-loop` preload только для implementer/reviewer/qa.
  **AC:** preload mapping минимизирует лишний контекст и совпадает с role responsibilities.
  **Deps:** W96-64, W96-69
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-77 (P1) Lint enforcement for preload matrix v2** `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `AGENTS.md`:
  - добавить lint-rule на role-based preload matrix;
  - запретить accidental preload drift;
  - добавить explicit waivers list для exceptional agents (если нужны).
  **AC:** preload matrix закреплён в lint и защищён от drift.
  **Deps:** W96-76
  **Regression/tests:** `python3 -m pytest -q tests/test_prompt_lint.py`, `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** S
  **Risk:** Low

#### Phase 6G — Template ownership finalization

- [x] **W96-78 (P1) Final template ownership lock: skill-local templates as canonical source** `skills/*/templates/*`, `skills/aidd-init/runtime/init.py`, `templates/aidd/**`, `AGENTS.md`, `README.md`, `README.en.md`:
  - оставить `templates/aidd` как bootstrap config + placeholders only;
  - stage content templates держать только в `skills/*/templates/*`;
  - закрепить init copy logic и docs SoT under skill ownership.
  **AC:** stage template SoT полностью skill-local, workspace templates не содержат дублей content templates.
  **Deps:** W96-65, W96-66, W96-68
  **Regression/tests:** `tests/repo_tools/smoke-workflow.sh`, `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** M
  **Risk:** Medium

#### Phase 6H — Improvement-plan backfill (without scope loss)

- [x] **W96-79 (P0) Prompt-lint baseline rehabilitation (backfill B-002)** `tests/repo_tools/lint-prompts.py`, `docs/skill-language.md`, `aidd/reports/migrations/commands_to_skills_frontmatter.json`:
  - восстановить canonical policy/baseline paths для prompt-lint;
  - добавить/обновить baseline entries для всех stage skills;
  - устранить текущие `missing policy/baseline` ошибки.
  **AC:** prompt-lint не падает на missing policy/baseline/stage entries.
  **Deps:** -
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-80 (P0) Single stage enum + alias map across runtime (backfill B-003)** `skills/aidd-core/runtime/set_active_stage.py`, `skills/aidd-core/runtime/context_map_validate.py`, `hooks/context_gc/pretooluse_guard.py`, `skills/aidd-core/templates/stage-lexicon.md`:
  - централизовать stage enum/alias map и переиспользовать в setter/validators/guards;
  - устранить расхождения stage семантики в runtime;
  - синхронизировать с stage-lexicon template.
  **AC:** setter/validators/guards принимают одинаковую stage семантику.
  **Deps:** W96-79
  **Regression/tests:** `python3 -m pytest -q tests/test_set_active_stage.py tests/test_wave93_validators.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W96-81 (P0) Canonical `spec-interview` stage assignment (backfill B-004)** `skills/spec-interview/SKILL.md`, `skills/aidd-core/runtime/set_active_stage.py`, `skills/aidd-core/runtime/context_map_validate.py`:
  - убрать drift между `spec`/`spec-interview` в command-stage assignment;
  - оставить только canonical semantics + явный alias (если нужен);
  - покрыть stage assignment тестами.
  **AC:** spec-interview stage consistently resolves to canonical stage.
  **Deps:** W96-80
  **Regression/tests:** `python3 -m pytest -q tests/test_set_active_stage.py`.
  **Effort:** S
  **Risk:** Low

- [x] **W96-82 (P1) Remove unsupported `release` stage placeholders (backfill B-005)** `skills/tasks-new/templates/tasklist.template.md`, `skills/aidd-core/templates/stage-lexicon.md`:
  - удалить placeholder stages, которых нет в runtime lexicon;
  - выровнять tasklist template с каноничным stage набором;
  - добавить guard на появление unsupported stages в template.
  **AC:** tasklist template содержит только supported stages/aliases.
  **Deps:** W96-80
  **Regression/tests:** `python3 -m pytest -q tests/test_tasklist_check.py`.
  **Effort:** S
  **Risk:** Low

- [x] **W96-83 (P1) PRD gate path cleanup and single authority (backfill B-006)** `hooks/hooks.json`, `hooks/gate-prd-review.sh`, `skills/aidd-core/runtime/gate_workflow.py`:
  - выбрать и закрепить единый путь PRD gating (hook vs internal gate-workflow path);
  - убрать двусмысленность/двойной gate execution;
  - обновить tests/docs под выбранный контракт.
  **AC:** в hook inventory нет неиспользуемых PRD-gate скриптов и дублирующего поведения.
  **Deps:** W96-80
  **Regression/tests:** `python3 -m pytest -q tests/test_gate_prd_review.py tests/test_gate_workflow.py tests/test_wave95_policy_guards.py`.
  **Effort:** S
  **Risk:** Low

- [x] **W96-84 (P2) CI/security expansion and required-check parity (backfill B-012)** `.github/workflows/ci.yml`, `.github/workflows/*.yml`, `AGENTS.md`, `README.md`, `README.en.md`:
  - добавить минимум 2 security controls (secret scan/SAST/SBOM) в CI;
  - сделать parity между documented release checks и enforced CI checks;
  - ввести staged rollout (non-blocking -> required).
  **AC:** security checks запускаются на PR и дают стабильный actionable signal.
  **Deps:** W96-79
  **Regression/tests:** GitHub Actions runs + `tests/repo_tools/ci-lint.sh`.
  **Effort:** M
  **Risk:** Medium

## Wave 97 — Python-only runtime canon (no `run.sh` / no shell wrappers)

_Статус: завершен, приоритет 0. Цель — убрать shell-прокладки (`skills/*/scripts/*.sh`) из runtime API и перейти на прямые Python entrypoints с единым контрактом логов/outputs._

_Важное: этот wave **supersedes shell-wrapper assumptions** из Wave 96 (включая обязательность `scripts/run.sh`). Исторические задачи Wave 96 не удаляются, но для дальнейшего развития считаются legacy path._

### Phase 7A — Canon + compatibility strategy

- [x] **W97-0 (P0) ADR: Python-only runtime contract + deprecation policy for shell wrappers** `AGENTS.md`, `README.md`, `README.en.md`, `CHANGELOG.md`, `backlog.md`:
  - зафиксировать новый канон: user/shared runtime entrypoints = `python3 <skills/*/runtime/*.py>`;
  - описать, где shell ещё допустим (например, системные bootstrap hooks) и где запрещён;
  - зафиксировать deprecation window + rollback criteria.
  **AC:** docs/ADR однозначно определяют Python-only runtime API и судьбу `scripts/*.sh`.
  **Deps:** -
  **Regression/tests:** docs consistency + `tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** S
  **Risk:** Medium

- [x] **W97-1 (P0) Runtime API inventory v3: map shell entrypoints -> python owners** `skills/aidd-core/runtime/tools_inventory.py`, `aidd/reports/tools/*.json`, `tests/test_tools_inventory.py`:
  - собрать полную таблицу shell wrappers и соответствующих Python modules;
  - классифицировать: `legacy_shell_wrapper`, `python_entrypoint`, `hook_shell_only`;
  - подготовить migration order (stage/shared/hooks).
  **AC:** есть machine-readable mapping всех `.sh` runtime entrypoints к python-owner.
  **Deps:** W97-0
  **Regression/tests:** `python3 -m pytest -q tests/test_tools_inventory.py`.
  **Effort:** M
  **Risk:** Medium

### Phase 7B — Python entrypoints migration

- [x] **W97-2 (P0) Create shared Python launcher contract (replace `wrapper_lib.sh`)** `skills/aidd-core/runtime/runtime.py`, `skills/aidd-core/runtime/launcher.py`, `tests/test_runtime_launcher.py`:
  - вынести в Python общий контракт: context resolve, log path, output budget, deterministic exit codes;
  - обеспечить parity с текущим wrapper behavior (`stdout/stderr` limits, report-to-log);
  - добавить API для stage/shared entrypoints.
  **AC:** новый launcher покрывает весь контракт wrapper_lib без shell dependency.
  **Deps:** W97-1
  **Regression/tests:** `python3 -m pytest -q tests/test_runtime_launcher.py tests/test_error_output.py`.
  **Effort:** M
  **Risk:** High

- [x] **W97-3 (P0) Stage user commands: migrate from `scripts/run.sh` to python entrypoints** `skills/*/runtime/*.py`, `skills/*/SKILL.md`, `tests/test_cli_subcommands.py`, `tests/repo_tools/smoke-workflow.sh`:
  - для всех user-invocable stage skills зафиксировать canonical Python command surface;
  - удалить runtime-dependency на `skills/<stage>/scripts/run.sh` в `SKILL.md`;
  - сохранить stage-specific behavior (`spec-interview`, `tasks-new`, implement/review/qa orchestration).
  **AC:** user-invocable skills работают через Python entrypoints без `run.sh`.
  **Deps:** W97-2
  **Regression/tests:** `python3 -m pytest -q tests/test_cli_subcommands.py`, `bash tests/repo_tools/smoke-workflow.sh`.
  **Effort:** L
  **Risk:** High

- [x] **W97-4 (P0) Shared core/loop command migration to python-only API** `skills/aidd-core/runtime/*.py`, `skills/aidd-loop/runtime/*.py`, `README*.md`, `tests/test_loop_*.py`:
  - заменить shell runtime API (`skills/aidd-core/scripts/*.sh`, `skills/aidd-loop/scripts/*.sh`) на python canonical commands;
  - обновить все consumers (skills, hooks, tests, docs);
  - удалить dual-path hints, где shell считался primary.
  **AC:** shared runtime вызывается напрямую через Python entrypoints.
  **Deps:** W97-2, W97-3
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_run.py tests/test_gate_workflow.py`.
  **Effort:** L
  **Risk:** High

- [x] **W97-5 (P1) Hook runtime decoupling from shell wrappers** `hooks/*.sh`, `hooks/**/*.py`, `hooks/hooks.json`, `tests/test_wave95_policy_guards.py`:
  - перевести hook orchestration на python entrypoints (или thin shell only where platform-required);
  - убрать зависимости hooks на `skills/*/scripts/*.sh`;
  - сохранить deterministic blocking semantics.
  **AC:** hooks не зависят от stage/shared shell wrappers.
  **Deps:** W97-4
  **Regression/tests:** `python3 -m pytest -q tests/test_wave95_policy_guards.py tests/test_gate_workflow.py`.
  **Effort:** M
  **Risk:** Medium

### Phase 7C — Lint/guards/canary enforcement

- [x] **W97-6 (P0) Prompt-lint contract update: forbid shell-wrapper canon for skills** `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - убрать правило “mandatory `scripts/run.sh`”;
  - добавить правило: stage skills указывают python runtime entrypoint в `allowed-tools`/steps;
  - запретить новые runtime refs на `skills/*/scripts/*.sh` (кроме allowlist на migration window).
  **AC:** lint защищает Python-only канон, shell-wrapper drifts блокируются.
  **Deps:** W97-3
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W97-7 (P0) Repo guard update: no runtime shell wrappers in skills** `tests/repo_tools/skill-scripts-guard.py`, `tests/repo_tools/runtime-path-regression.sh`, `tests/repo_tools/ci-lint.sh`:
  - поменять guard policy: runtime canonical = python modules, не `scripts/*.sh`;
  - добавить explicit allowlist only для non-runtime utility shell scripts (если останутся);
  - обеспечить CI fail-fast на новый shell runtime drift.
  **AC:** CI блокирует появление новых shell wrappers как runtime API.
  **Deps:** W97-6
  **Regression/tests:** `bash tests/repo_tools/ci-lint.sh`.
  **Effort:** M
  **Risk:** Medium

- [x] **W97-8 (P1) Remove shell wrapper layer and cleanup artifacts** `skills/*/scripts/*.sh`, `skills/aidd-reference/wrapper_lib.sh`, `tests/repo_tools/entrypoints-bundle.txt`, `README*.md`:
  - удалить obsolete shell wrappers после прохождения migration gates;
  - удалить wrapper_lib и связанные references;
  - обновить entrypoints inventory/bundle под python-only layout.
  **AC:** runtime shell wrappers удалены из skills; bundle/docs соответствуют python-only.
  **Deps:** W97-4, W97-7
  **Regression/tests:** `python3 tests/repo_tools/entrypoints_bundle.py --root .`, `bash tests/repo_tools/ci-lint.sh`.
  **Effort:** M
  **Risk:** Medium

### Phase 7D — SKILL best-practice contract (Claude Code + other coding agents)

- [x] **W97-9 (P0) Cross-agent SKILL authoring guide (Claude Code/Codex/Cursor/Copilot)** `docs/agent-skill-best-practices.md`, `AGENTS.md`, `README*.md`:
  - собрать unified best practices из официальных источников (Claude Code memories/subagents/commands, Codex AGENTS.md, Cursor Rules, Copilot custom instructions);
  - зафиксировать общий принцип: concise + focused + scoped + explicit command contracts;
  - описать, что переносится в supporting files vs что остаётся в `SKILL.md`.
  **AC:** есть согласованный guide с actionable policy для repo.
  **Deps:** W97-0
  **Regression/tests:** docs review + `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** S
  **Risk:** Low

- [x] **W97-10 (P0) SKILL detail level policy: script contract cards, not implementation retell** `AGENTS.md`, `skills/*/SKILL.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - ввести policy для описания скриптов в SKILL:
    - when to run;
    - input flags/required context;
    - outputs/artifacts;
    - failure modes + next action;
  - запретить line-by-line пересказ реализации;
  - добавить lint checks на наличие contract-level описания для critical commands.
  **AC:** SKILL описывает “interface contract” каждого critical script, без дублирования кода.
  **Deps:** W97-9
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** Low

- [x] **W97-11 (P1) SKILL compactness and progressive disclosure hardening** `skills/*/SKILL.md`, `skills/*/references/*`, `tests/repo_tools/lint-prompts.py`:
  - зафиксировать target size/structure (compact SKILL + references for deep details);
  - нормализовать `Additional resources`: когда читать файл и зачем;
  - добавить warnings/errors для oversized and unscoped skill docs.
  **AC:** skill docs соответствуют progressive-disclosure policy и не раздувают context.
  **Deps:** W97-10
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** S
  **Risk:** Low

### Phase 7E — Final verification

- [x] **W97-12 (P0) End-to-end python-only verification matrix** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/python-only-regression.sh`, `.github/workflows/ci.yml`:
  - добавить отдельный regression suite для python-only runtime command surface;
  - убедиться, что smoke/ci не опираются на shell wrappers;
  - обновить required checks policy под новый канон.
  **AC:** full CI/smoke проходят без runtime shell wrappers; regression matrix green.
  **Deps:** W97-8, W97-11
  **Regression/tests:** `bash tests/repo_tools/ci-lint.sh`, `bash tests/repo_tools/smoke-workflow.sh`, `bash tests/repo_tools/python-only-regression.sh`.
  **Effort:** M
  **Risk:** Medium

## Wave 90 — Research RLM-only (python-only flow, без legacy context artifacts)

_Статус: завершено, приоритет 1. Канон: runtime entrypoints только `skills/*/runtime/*.py`, без `tools/*`, без `*-context*` и legacy `*-targets.json`._
_Пере-проверка: 2026-02-09 — подтверждено после фиксов (`hooks/gate-tests.sh` переведён на `*-rlm-targets.json`, legacy test-paths вычищены)._

- [x] **W90-1** `skills/aidd-core/runtime/research_hints.py`, `skills/researcher/runtime/research.py`, `skills/idea-new/templates/prd.template.md`, `tests/test_research_hints.py`, `tests/test_research_command.py`:
  - добавить парсер `AIDD:RESEARCH_HINTS` (Paths/Keywords/Notes) с нормализацией (split `:`/`,`/whitespace, trim, dedupe);
  - сделать hints обязательными для research (минимум `paths` или `keywords`);
  - обновить PRD template/commands: явно требовать заполнения `AIDD:RESEARCH_HINTS` на этапе analyst.
  **AC:** есть единый парсер hints; research не стартует при пустых hints; PRD template содержит строгий формат.
  **Deps:** -

- [x] **W90-2** `skills/aidd-core/runtime/rlm_targets.py`, `skills/aidd-core/runtime/rlm_manifest.py`, `skills/aidd-rlm/runtime/rlm_links_build.py`, `skills/aidd-rlm/runtime/rlm_nodes_build.py`, `tests/test_rlm_targets.py`, `tests/test_research_rlm_e2e.py`:
  - RLM targets строятся напрямую из `AIDD:RESEARCH_HINTS` (paths/keywords/notes), без `*-targets.json`;
  - удалить `_load_research_targets` и любые зависимости от `reports/research/*-targets.json`;
  - `targets_mode=explicit` при наличии paths.
  **AC:** `aidd/reports/research/<ticket>-rlm-targets.json` генерируется только из PRD hints; `*-targets.json` нигде не читается.
  **Deps:** W90-1

- [x] **W90-3** `skills/researcher/runtime/research.py`, `skills/aidd-core/runtime/researcher_context.py`, `skills/aidd-rlm/runtime/reports_pack.py`, `skills/aidd-core/runtime/research_hints.py`:
  - убрать сбор `*-context.json`/`*-context.pack.json` и `*-targets.json`;
  - удалить/заменить `ResearcherContextBuilder` и связанный CLI-surface (`researcher_context.py`) на RLM-only orchestration;
  - canonical research entrypoint `skills/researcher/runtime/research.py` запускает только RLM pipeline (targets → manifest → worklist) + materialize `docs/research/<ticket>.md`;
  - удалить `reports.research_pack_budget` логику в `skills/aidd-rlm/runtime/reports_pack.py`.
  **AC:** research runtime не создаёт `*-context*` и legacy `*-targets.json`; остаются только RLM артефакты (`*-rlm-*`) и `docs/research/<ticket>.md`.
  **Deps:** W90-1, W90-2

- [x] **W90-4** `skills/aidd-core/runtime/research_guard.py`, `skills/aidd-core/runtime/gate_workflow.py`, `skills/aidd-flow-state/runtime/tasks_derive.py`, `skills/status/runtime/index_sync.py`, `skills/status/runtime/status.py`:
  - валидировать readiness research только по RLM артефактам (`*-rlm-targets.json`, `*-rlm-manifest.json`, `*-rlm.worklist.pack.json`, `*-rlm.nodes.jsonl`, `*-rlm.links.jsonl`, `*-rlm.pack.json`);
  - handoff‑derive для research берёт данные только из `*-rlm.pack.json` (без fallback на context);
  - удалить ссылки на `*-context.json` и legacy `*-targets.json` из gate/index/status/task derive.
  **AC:** гейты/status/handoff работают без `*-context*`; warnings/blocked основаны на RLM readiness policy.
  **Deps:** W90-2, W90-3

- [x] **W90-5** `skills/aidd-rlm/runtime/rlm_finalize.py`, `skills/aidd-rlm/runtime/rlm_nodes_build.py`, `skills/aidd-rlm/runtime/reports_pack.py`:
  - убрать `--update-context` и любые обновления `context.json`;
  - `rlm_finalize` оперирует только `nodes/links` и пишет `*-rlm.pack.json` + `rlm_status` без записи в context artifacts;
  - убедиться, что finalize/pack pipeline не имеет implicit dependency на `researcher_context`.
  **AC:** `rlm_finalize` работает без `context.json`; pack детерминированно строится из nodes/links.
  **Deps:** W90-3

- [x] **W90-6** `agents/researcher.md`, `skills/researcher/SKILL.md`, `skills/aidd-rlm/SKILL.md`, `AGENTS.md`, `skills/aidd-core/templates/workspace-agents.md`, `README.md`, `README.en.md`, `templates/aidd/config/conventions.json`:
  - удалить упоминания `*-context.json`/`*-context.pack.json`/legacy `*-targets.json` в docs/prompts/skills;
  - зафиксировать RLM‑only policy и обязательность `AIDD:RESEARCH_HINTS` для research stage;
  - обновить command contracts в `researcher`/`aidd-rlm` под python-only runtime flow;
  - удалить `reports.research_pack_budget` из `config/conventions.json`.
  **AC:** документация и канон описывают только RLM артефакты; нет ссылок на context/targets.
  **Deps:** W90-1, W90-3

- [x] **W90-7** `tests/*`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/ci-lint.sh` (если нужно), `tests/helpers.py`:
  - удалить/переписать тесты, опирающиеся на `*-context.json`/legacy `*-targets.json`;
  - расширить покрытие для `AIDD:RESEARCH_HINTS` parser + RLM targets из PRD;
  - обновить smoke/ci regression под RLM-only research flow (без context artifacts).
  **AC:** тесты/смоук проходят в режиме RLM-only; отсутствуют runtime-упоминания `*-context*` и legacy `*-targets.json`.
  **Deps:** W90-1, W90-2, W90-3, W90-4, W90-5

## Wave 98 — Research flow v2 (subagents-first + RLM-only consistency)

_Статус: план, приоритет 0. Цель — довести research до целевой модели “stage skill = orchestration, subagent = content”, убрать legacy зависимости на `*-context*`/`*-targets.json` и синхронизировать prompts/gates/tests._

### Success Metrics (tracked per checkpoint)

- **R98-M1a:** в `skills/researcher/SKILL.md` отсутствуют `context: fork` и `agent:` (target `0`).
  **Check:** `rg -n "^\\s*context:\\s*fork|^\\s*agent:" skills/researcher/SKILL.md`.
- **R98-M1b:** в `skills/researcher/SKILL.md` ровно один orchestration-вызов `Run subagent`.
  **Check:** `test "$(rg -n "Run subagent" skills/researcher/SKILL.md | wc -l | tr -d ' ')" = "1"`.
- **R98-M1c:** в `skills/researcher/SKILL.md` нет fork-формулировок/двойной делегации в steps.
  **Check:** `test -z "$(rg -n "forked context|\\(fork\\)|Delegate to subagent" skills/researcher/SKILL.md)"`.
- **R98-M2:** runtime/hints не читают и не записывают legacy `*-context.json`/`*-targets.json` вне compat-fixtures.
  **Check (runtime/docs surfaces):** `rg -n "reports/research/[^/]+-context\\.json|reports/research/[^/]+-targets\\.json" skills hooks tools templates docs dev | rg -v "rlm-targets\\.json"`.
  **Check (tests outside compat-fixtures):** `rg -n "reports/research/[^/]+-context\\.json|reports/research/[^/]+-targets\\.json" tests | rg -v "rlm-targets\\.json" | rg -v "fixtures|compat"`.
  **Write-check:** `rg -n "context\\.json|targets\\.json" skills hooks tools | rg -v "rlm-targets\\.json"`.
- **R98-M3:** legacy permission pattern (colon-wildcard form) удалён из canonical prompts/docs/baselines/templates/plugin metadata.
  **Check:** `rg -n "Bash\\([^)]*:\\*\\)" skills agents docs templates tests dev .claude-plugin`.
- **R98-M4:** research regression suites green в RLM-only режиме.
  **Check:** `python3 -m pytest -q tests/test_research_command.py tests/test_research_check.py tests/test_gate_researcher.py tests/test_gate_workflow.py tests/test_tasks_derive.py` + `tests/repo_tools/smoke-workflow.sh`.
- **R98-M4b:** CI path реально исполняет pytest (нет drift к пустым test runs).
  **Check:** `rg -n "python3 -m pytest|pytest -q" .github/workflows tests/repo_tools/ci-lint.sh`.

### Phase 98A — Contract inventory + migration scaffolding

#### Inventory snapshot (2026-02-09)
- Execution map:
  - Stage command skill `skills/researcher/SKILL.md` -> stage runtime `skills/researcher/runtime/research.py` -> explicit subagent `agents/researcher.md`.
  - Shared RLM owner surface `skills/aidd-rlm/runtime/*` is consumed via handoff, not directly from stage skill.
  - Gate/readiness surfaces: `skills/aidd-core/runtime/research_guard.py`, `skills/aidd-core/runtime/gate_workflow.py`, `skills/aidd-flow-state/runtime/tasks_derive.py`, `skills/status/runtime/index_sync.py`.
- Drift fixed in this wave step:
  - removed `context: fork` + `agent:` from `skills/researcher/SKILL.md`;
  - migrated permission grammar to canonical `Bash(cmd *)` across skills/agents/docs/tests/baselines;
  - added strict lint policy for legacy colon-wildcard grammar (`AIDD_BASH_LEGACY_POLICY`, default `error`).
- Rollout boundaries:
  - non-breaking: grammar parser dual-accept (`warn|allow` compatibility mode), new preload-only skill `aidd-stage-research`;
  - breaking policy: default lint/CI rejects legacy colon-wildcard syntax.

- [x] **W98-1 (P0) Research migration inventory and drift map (repo vs target flow)** `skills/researcher/SKILL.md`, `agents/researcher.md`, `skills/aidd-core/runtime/research_guard.py`, `skills/aidd-core/runtime/gate_workflow.py`, `skills/aidd-flow-state/runtime/tasks_derive.py`, `skills/status/runtime/index_sync.py`, `tools/*.py`, `AGENTS.md`, `backlog.md`:
  - собрать фактическую матрицу `stage skill -> subagent -> artifacts -> gates` для research;
  - покрыть оба execution-пространства: `skills/**/runtime` и `tools/` (если присутствует compat/runtime codepath);
  - зафиксировать drift: `context: fork`, legacy colon-wildcard permission grammar, legacy `*-context*`/`*-targets.json` зависимости, несовпадения docs/tests/runtime;
  - определить execution order и rollout-границы (breaking/non-breaking) для Wave 98.
  **AC:** есть единая migration-map для research с привязкой к конкретным файлам/проверкам.
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** S
  **Risk:** Medium

- [x] **W98-2a (P0) Permission grammar compatibility scaffold (dual-accept, warn-old)** `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `docs/skill-language.md`:
  - временно поддержать оба формата (canonical wildcard и legacy colon-wildcard) в lint;
  - добавить warning на legacy `:*` для canonical prompts;
  - зафиксировать cutover-план (warn -> error) в policy docs.
  **AC:** migration не блокируется, но legacy-pattern получает детерминированный warning.
  **Deps:** W98-1
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W98-2b (P0) Permission grammar migration for research scope** `skills/researcher/SKILL.md`, `agents/researcher.md`, `skills/aidd-rlm/SKILL.md`, `skills/researcher/templates/research.template.md`, `docs/skill-language.md`:
  - перевести research-related prompts/docs на `Bash(cmd *)`;
  - синхронизировать examples/hints в research и shared RLM surface;
  - исключить новый legacy drift в пределах research scope.
  **AC:** research scope не содержит legacy colon-wildcard grammar.
  **Deps:** W98-2a
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W98-2c (P1) Repo-wide permission grammar enforcement (legacy colon-wildcard -> error)** `skills/*/SKILL.md`, `agents/*.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `tests/repo_tools/ci-lint.sh`, `dev/reports/migrations/commands_to_skills_frontmatter.json`:
  - завершить cutover: legacy colon-wildcard grammar становится fail-fast ошибкой в lint/CI;
  - обновить baseline/migration artifacts под новый grammar;
  - зафиксировать rollback note на случай drift в downstream forks.
  **AC:** legacy colon-wildcard grammar блокируется как policy violation на уровне CI.
  **Precondition:** перед включением fail-fast `rg -n "Bash\\([^)]*:\\*\\)" skills agents` должен вернуть `0` строк; иначе enforcement переносится в следующую волну.
  **Deps:** W98-2b, W98-10
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** M
  **Risk:** Medium

### Phase 98B — Research orchestrator/subagent contract

- [x] **W98-3 (P0) Refactor `researcher` stage skill into pure orchestrator (no `context: fork`)** `skills/researcher/SKILL.md`, `agents/researcher.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - убрать `context: fork`/`agent:` из `skills/researcher/SKILL.md`;
  - оставить в stage skill только orchestration: preflight/state, запуск `research.py`, явный `Run subagent`, post-validation/handoff;
  - исключить двойную делегацию и зафиксировать явный next-step contract.
  **AC:** `researcher` работает как orchestration-stage без скрытого fork-сабагента; `Run subagent` присутствует ровно один раз; state sync (`set_active_feature/set_active_stage`) выполняется до subagent; next-step contract явно возвращает следующий stage command.
  **Deps:** W98-1, W98-2a
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W98-4 (P1) Add stage reference preload for researcher (`aidd-stage-research`)** `skills/aidd-stage-research/SKILL.md`, `agents/researcher.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - создать reference-only skill с stage-specific research contract (read policy, handoff policy, evidence policy);
  - frontmatter policy для reference skill: `user-invocable: false`, explicit `description`, без `disable-model-invocation: true` (omit/false);
  - подключить preload в `agents/researcher.md` (и роли-потребители при необходимости) без skills inheritance в stage-skills;
  - зафиксировать policy, что stage-specific knowledge приходит в subagent через `skills:`.
  **AC:** subagent researcher получает stage guidance через explicit preload, без implicit inheritance.
  **Deps:** W98-3
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** Medium

### Phase 98Bx — Carry-over (out of research core scope)

- [x] **W98-5 (P2) Carry-over: rollout orchestrator/no-fork contract to non-research stages** `skills/idea-new/SKILL.md`, `skills/tasks-new/SKILL.md`, `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - применить тот же паттерн к stage skills с текущим `context: fork`;
  - унифицировать структуру: Inputs -> Preflight -> Run subagent -> Postflight -> Output;
  - убрать special-case `FORK_STAGES` policy из lint в пользу общего orchestration contract после закрытия research wave.
  **AC:** non-research stage skills не завязаны на `context: fork`; subagent вызовы остаются явными и детерминированными.
  **Deps:** W98-12
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** L
  **Risk:** High

### Phase 98C — RLM-only runtime and gate consistency

- [x] **W98-6 (P0) Complete RLM-only runtime: remove context-side effects from shared RLM API** `skills/aidd-rlm/runtime/rlm_nodes_build.py`, `skills/aidd-rlm/runtime/rlm_finalize.py`, `skills/aidd-rlm/runtime/reports_pack.py`, `skills/researcher/runtime/research.py`, `templates/aidd/config/conventions.json`:
  - убрать `context.json` update semantics (`--update-context`, implicit status writes);
  - удалить legacy `reports.research_pack_budget` path и связанные fallback-настройки;
  - закрепить pipeline: `rlm-targets -> rlm-manifest -> rlm.worklist.pack -> nodes/links -> rlm.pack`.
  **AC:** RLM runtime не мутирует `*-context.json`; source of truth только RLM artifacts.
  **Deps:** W98-1, W98-6b
  **Regression/tests:** `python3 -m pytest -q tests/test_rlm_nodes_build.py tests/test_rlm_links_build.py tests/test_reports_pack.py tests/test_research_rlm_e2e.py`.
  **Effort:** L
  **Risk:** High

- [x] **W98-6b (P0) Migration policy for existing workspaces (legacy -> RLM-only)** `AGENTS.md`, `templates/aidd/AGENTS.md`, `README.md`, `README.en.md`, `skills/researcher/SKILL.md`, `skills/aidd-core/runtime/research_guard.py`:
  - зафиксировать policy для historical workspace state: regenerate vs soft-read window vs hard-break;
  - описать deterministic handoff для отсутствующих RLM artifacts (`rerun research`, explicit command hints);
  - синхронизировать policy с gate behavior и user-facing troubleshooting.
  **AC:** есть единая documented стратегия перехода для старых workspace-артефактов; behavior гейтов соответствует documentation.
  **Deps:** W98-1
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, targeted gate tests.
  **Effort:** M
  **Risk:** Medium

- [x] **W98-7 (P0) Rewrite research gate to consume only RLM artifacts** `skills/aidd-core/runtime/research_guard.py`, `skills/aidd-core/runtime/research_check.py`, `skills/researcher/SKILL.md`:
  - исключить hard dependency на `reports/research/<ticket>-context.json` и legacy `<ticket>-targets.json`;
  - базировать readiness на `*-rlm-targets.json`, `*-rlm-manifest.json`, `*-rlm.worklist.pack.json`, `*-rlm.nodes.jsonl`, `*-rlm.links.jsonl`, `*-rlm.pack.json`;
  - синхронизировать BLOCK/WARN semantics и handoff hints с новым контрактом.
  **AC:** research gate проходит/блокирует без обращения к context artifacts; для missing RLM artifacts выдаёт deterministic reason_code по минимальному обязательному набору (targets/manifest/worklist/nodes/links/pack).
  **Deps:** W98-6, W98-6b
  **Regression/tests:** `python3 -m pytest -q tests/test_research_check.py tests/test_gate_researcher.py`.
  **Effort:** M
  **Risk:** High

- [x] **W98-8 (P0) Downstream consumers cleanup (`gate_workflow` / `tasks_derive` / `status`)** `skills/aidd-core/runtime/gate_workflow.py`, `skills/aidd-flow-state/runtime/tasks_derive.py`, `skills/status/runtime/index_sync.py`, `skills/status/runtime/status.py`:
  - перевести default research report path на `*-rlm.pack.json` и pack-first reading;
  - удалить fallback/marker refs на `*-context.json` и legacy `*-targets.json`;
  - обновить hints/summary/index outputs и handoff-source labels под RLM-only artifact names;
  - синхронизировать index/status/checks outputs с RLM-only research policy.
  **AC:** workflow/status/handoff работают с RLM pack без legacy контекста.
  **Deps:** W98-7
  **Regression/tests:** `python3 -m pytest -q tests/test_gate_workflow.py tests/test_tasks_derive.py tests/test_status.py`.
  **Effort:** M
  **Risk:** High

- [x] **W98-9 (P1) Retire legacy researcher context modules and dead compat paths** `skills/aidd-core/runtime/researcher_context.py`, `skills/aidd-core/runtime/researcher_context_pack.py`, `tests/repo_tools/runtime-module-guard.py`:
  - убрать runtime usage of legacy context builders (или переместить в explicit deprecated-only layer);
  - вычистить stale imports/call-sites и неиспользуемые CLI switches;
  - зафиксировать ownership cleanup для research runtime surface.
  **AC:** research runtime surface не зависит от `ResearcherContextBuilder` и context-pack builders.
  **Deps:** W98-8
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_researcher_context.py`, `tests/repo_tools/ci-lint.sh`.
  **Effort:** M
  **Risk:** Medium

### Phase 98D — Docs/templates/tests alignment + final enforcement

- [x] **W98-10 (P0) Docs and templates alignment with RLM-only + subagents-first flow** `AGENTS.md`, `templates/aidd/AGENTS.md`, `README.md`, `README.en.md`, `skills/researcher/templates/research.template.md`, `skills/researcher/SKILL.md`, `skills/aidd-rlm/SKILL.md`, `docs/skill-language.md`:
  - удалить упоминания `*-context.json`/legacy `*-targets.json` из canonical docs/templates;
  - описать research stage как orchestration + explicit subagent handoff;
  - обновить примеры команд/permission patterns под `Bash(cmd *)`.
  **AC:** docs/prompts/templates не противоречат RLM-only и orchestration contract.
  **Deps:** W98-3, W98-7, W98-8
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, docs consistency checks.
  **Effort:** M
  **Risk:** Medium

- [x] **W98-11 (P0) Rewrite research regression suite for new contract** `tests/test_research_command.py`, `tests/test_research_check.py`, `tests/test_gate_researcher.py`, `tests/test_gate_workflow.py`, `tests/test_tasks_derive.py`, `tests/test_reports_pack.py`, `tests/repo_tools/smoke-workflow.sh`:
  - заменить ожидания по `*-context.json`/legacy `*-targets.json` на RLM-only artifacts;
  - покрыть кейсы `rlm_status=pending|warn|ready`, links-empty semantics и explicit handoff;
  - добавить negative guard test: runtime не должен читать legacy `*-context.json`/`*-targets.json` при наличии валидных RLM artifacts;
  - обновить smoke assertions и fixture builders под новый artifact-set.
  **AC:** целевой research regression suite зелёный в RLM-only режиме; есть отдельный тест, доказывающий отказ от чтения legacy research artifacts.
  **Deps:** W98-6, W98-7, W98-8
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_research_check.py tests/test_gate_researcher.py tests/test_gate_workflow.py tests/test_tasks_derive.py`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** L
  **Risk:** High

- [x] **W98-12 (P0) Final CI enforcement + backlog consolidation (close/supersede W90 research leftovers)** `tests/repo_tools/lint-prompts.py`, `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`, `backlog.md`:
  - включить строгие guard-ы: запрет legacy colon-wildcard grammar, запрет runtime refs на research legacy artifacts;
  - зафиксировать и выполнить close/supersede strategy для W90-3..W90-7 после миграции Wave 98;
  - обновить quality gates и release checklist по новому research contract.
  **AC:** CI блокирует возврат legacy-паттернов; backlog не содержит дублирующих открытых research-монолит задач.
  **Deps:** W98-2c, W98-11
  **Regression/tests:** `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.
  **Effort:** M
  **Risk:** Medium

### Wave 98 Critical Path

1. `W98-1` -> `W98-2a` -> `W98-3` -> `W98-4`
2. `W98-6b` -> `W98-6` -> `W98-7` -> `W98-8`
3. `W98-2b` -> `W98-10` -> `W98-11` -> `W98-2c` -> `W98-12`
4. `W98-5` — carry-over task вне критического пути research wave.

## Wave 99 — E2E audit fallout hardening (TST-001)

_Статус: активен (re-open). Приоритет 0. Цель — закрыть дефекты, найденные в полном E2E-аудите (`TST-001`), и убрать ложные BLOCKED в loop/qa path._

- [x] **W99-1 (P0) QA test execution parsing: inline-list tasks/filters must be parsed as command list** `skills/aidd-core/runtime/tasklist_parser.py`, `skills/qa/runtime/qa.py`, `tests/test_qa_agent.py`:
  - починить разбор `AIDD:TEST_EXECUTION` для формата `tasks: ["cmd1", "cmd2"]` (не как одна строка);
  - сохранить обратную совместимость для scalar/list форматов (`tasks: cmd1; cmd2`, markdown list);
  - добавить regression tests на реальный кейс из аудита (`[./gradlew ...` должен исчезнуть).
  **AC:** QA запускает каждую команду отдельно; `tests_executed.command` не содержит bracket-prefixed мусор.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_qa_agent.py`.
  **Effort:** M
  **Risk:** High

- [x] **W99-2 (P0) Fail-fast guard for malformed `CLAUDE_PLUGIN_ROOT` (`.../skills` instead of plugin root)** `skills/aidd-core/runtime/runtime.py`, `tests/test_runtime_write_safety.py`:
  - добавить структурную валидацию plugin root и явную ошибку конфигурации для `CLAUDE_PLUGIN_ROOT=<plugin>/skills`;
  - убрать downstream-симптом `contract_missing .../skills/skills/<stage>/CONTRACT.yaml` как primary signal;
  - синхронизировать сообщение с ENV diagnostics/healthcheck policy.
  **AC:** misconfigured plugin root детектируется сразу с понятным reason.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_runtime_write_safety.py`.
  **Effort:** S
  **Risk:** Medium

- [x] **W99-3 (P1) Report loader diagnostics for pack/json miss (`*-rlm.pack.json` vs `*-rlm.json`)** `skills/aidd-core/runtime/reports/loader.py`, `tests/test_reports_loader.py`:
  - сделать детерминированную ошибку, если одновременно отсутствуют pack и json;
  - включить в сообщение оба ожидаемых пути (pack + json) для быстрой triage;
  - исключить misleading “only `*-rlm.json` missing” без контекста pack-first.
  **AC:** ошибка загрузки отчёта сразу показывает полный missing-set.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_reports_loader.py`.
  **Effort:** S
  **Risk:** Low

- [x] **W99-4 (P1) Loop preflight/scope hardening for work-item format drift** `skills/aidd-loop/runtime/loop_run.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`:
  - добавить явный precheck для отсутствующего/невалидного `work_item_key` до запуска stage orchestration;
  - улучшить diagnostics при `scope_key_mismatch` (что было ожидаемо, что выбрал loop-pack, как repair path);
  - снизить долю ложных `stage_result_missing_or_invalid` при запуске без активного work item.
  **AC:** loop path выдаёт actionable blocked reason до глубоких ретраев и без ambiguous scope drift.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W99-5 (P0) Preflight artifact path enforcement: block non-canonical write targets for scope-bound stages** `skills/aidd-loop/runtime/preflight_prepare.py`, `skills/aidd-loop/runtime/preflight_result_validate.py`, `tests/test_loop_step.py`:
  - валидировать, что `--actions-template`, `--readmap-*`, `--writemap-*`, `--result` соответствуют canonical путям из `{ticket,scope_key,stage}`;
  - блокировать preflight (`reason_code=artifact_path_mismatch`) при попытке писать в глобальные/нескоуповые пути (`aidd/reports/readmap.json`, `.../I1/...` вместо `.../iteration_id_I1/...`);
  - добавить diagnostics: expected vs provided path для triage в audit logs.
  **AC:** preflight не может завершиться `ok`, если артефакты направлены в non-canonical paths.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py`.
  **Effort:** M
  **Risk:** High

- [x] **W99-6 (P0) Seed-stage canonical orchestration guard: enforce preflight->run->postflight chain for implement/review** `skills/aidd-loop/runtime/loop_step_wrappers.py`, `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `tests/test_loop_step.py`:
  - добавить hard guard на stage wrappers: seed run считается валидным только при наличии wrapper logs + `stage.<stage>.result.json` в canonical scope path;
  - исключить частично-ручной preflight-only path как "успех" seed-итерации;
  - синхронизировать stage SKILL contracts: canonical путь orchestration через wrapper chain.
  **AC:** seed не может завершиться без `aidd/reports/loops/<ticket>/<scope_key>/stage.implement.result.json` и `stage.review.result.json`.
  **Deps:** W99-5
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_run.py`.
  **Effort:** L
  **Risk:** High

- [x] **W99-7 (P1) Loop-step recovery from non-loop active stage (`tasklist`/`plan`/etc.) with preserved work-item context** `skills/aidd-loop/runtime/loop_step.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`:
  - для `active.stage` вне `{implement,review,qa}` при валидном `work_item_key=iteration_id=*` выполнять controlled recovery в `implement` (WARN), а не immediate `unsupported_stage`;
  - сохранить strict BLOCK для действительно невалидного/отсутствующего work item;
  - фиксировать recovery reason в cli log/event payload.
  **AC:** `loop_run` не падает в `blocked stage=tasklist` после seed при валидном iteration work item.
  **Deps:** W99-6
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_run.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W99-8 (P1) QA command normalization for prefixed tasklist entries (`Backend:`/`Frontend:`)** `skills/qa/runtime/qa.py`, `skills/aidd-core/runtime/tasklist_parser.py`, `tests/test_qa_agent.py`:
  - нормализовать prefixed commands из `AIDD:TEST_EXECUTION` перед exec (убрать label-prefix, сохранить команду и cwd semantics);
  - не допускать `command not found: Backend:`/`Frontend:` в QA fallback path;
  - сохранить совместимость с markdown/list/scalar форматами.
  **AC:** QA корректно исполняет команды с human-readable префиксами и логирует нормализованный command.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_qa_agent.py`.
  **Effort:** S
  **Risk:** Medium

### Wave 99B — TST-001 loop/stage-result compatibility hardening

- [x] **W99-9 (P0) Legacy stage-result compatibility bridge for loop-step parser** `skills/aidd-loop/runtime/loop_step_stage_result.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`:
  - добавить контролируемую совместимость для legacy stage schemas `aidd.stage_result.<stage>.v1`, не ослабляя canonical schema (`aidd.stage_result.v1`) как SoT;
  - поддержать migration mapping `status -> result` (`ok/pass/success -> continue`, `blocked/fail/error -> blocked`, `done/completed -> done`) только для legacy payload;
  - сохранить fail-fast для truly invalid schemas/results (`v0`, unknown schema/status, wrong stage).
  **AC:** `loop-step` не блокируется на historical legacy stage results из seed-run, но продолжает блокировать реально битые payload.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_run.py`.
  **Effort:** M
  **Risk:** High

- [x] **W99-10 (P0) Loop-step blocked-diagnostic clarity for invalid/mixed stage-result candidates** `skills/aidd-loop/runtime/loop_step_stage_result.py`, `skills/aidd-loop/runtime/loop_step.py`, `tests/test_loop_step.py`:
  - улучшить diagnostics для mixed candidate sets (preferred + fallback candidates) с явным статусом причины (`invalid-schema`, `invalid-result`, `wrong-stage`);
  - не терять `scope_key` signal при recoverable mismatch (diag должен показывать selected candidate path + reason);
  - исключить ambiguous reason strings в `stage_result_missing_or_invalid` triage.
  **AC:** при BLOCKED из-за stage-result в cli log видно, какой именно candidate и почему отвергнут/принят.
  **Deps:** W99-9
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W99-11 (P1) Seed-stage orchestration prompt contract hardening (no manual stage.result writes)** `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `tests/repo_tools/lint-prompts.py`:
  - явно зафиксировать policy: запрещено писать `aidd/reports/loops/**/stage.*.result.json` вручную через `Write/cat`;
  - закрепить единственный допустимый путь через canonical postflight chain (`.../actions_apply.py` + `.../stage_result.py`);
  - добавить lint-check на обязательный текст policy в command contracts loop stages.
  **AC:** prompt contracts и lint исключают ручной non-canonical stage-result path в seed/loop flow.
  **Deps:** -
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`.
  **Effort:** M
  **Risk:** Medium

- [x] **W99-12 (P1) Audit-derived regression fixtures for TST-001 fallout** `tests/test_loop_step.py`, `tests/test_loop_run.py`, `tests/fixtures/loop_step/*`:
  - добавить regression fixture c legacy `stage.review.result.json` (`schema=aidd.stage_result.review.v1`, `status=ok`) и проверить, что loop-run продолжает progression;
  - добавить negative fixture на unknown legacy status/scheme -> deterministic BLOCKED;
  - проверить, что `wrapper_logs`/`stage_result_diag` остаются информативными при mixed candidates.
  **AC:** воспроизводимость TST-001 class regressions в unit/integration tests без ручного воспроизведения большого E2E.
  **Deps:** W99-9, W99-10
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_run.py`.
  **Effort:** M
  **Risk:** Medium

### Wave 99C — E2E prompt and contract hardening (TST-001 follow-up)

- [x] **W99-13 (P0) Stage-skill contract hardening: wrappers-only path for implement/review/qa (no manual preflight command path in operator guidance)** `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - убрать из user-facing command contracts guidance, который выглядит как manual stage execution через прямой вызов `preflight_prepare.py`/ручные stage-result шаги;
  - оставить только canonical orchestration path (slash stage command + wrapper chain), чтобы prompt не провоцировал non-canonical recovery;
  - усилить lint/test guard, чтобы возврат manual-path guidance в этих stage skills ловился автоматически.
  **AC:** implement/review/qa skill contracts не подсказывают manual preflight as recovery path; prompt-lint блокирует регресс.
  **Deps:** W99-11
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** M
  **Risk:** High

- [x] **W99-14 (P1) QA command hygiene: block single-entry shell chains in `AIDD:TEST_EXECUTION` tasks** `skills/aidd-core/runtime/tasklist_parser.py`, `skills/qa/runtime/qa.py`, `tests/test_qa_agent.py`, `tests/test_tasklist_check.py`:
  - детектировать `&&`, `||`, `;` внутри одного task-entry и маркировать как malformed test command chain;
  - не исполнять такую цепочку как одну команду, а возвращать явный diagnostics reason для triage;
  - сохранить совместимость с валидными list/scalar форматами, где команды разделены корректно.
  **AC:** QA не запускает shell-chain, если она пришла одной task строкой; в отчёте есть явный reason code/diagnostics.
  **Deps:** W99-1, W99-8
  **Regression/tests:** `python3 -m pytest -q tests/test_qa_agent.py tests/test_tasklist_check.py`.
  **Effort:** S
  **Risk:** Medium

- [x] **W99-15 (P1) E2E prompt contract tests for retry triggers and seed invariants** `aidd_test_flow_prompt_ralph_script_full.txt`, `aidd_test_flow_prompt_ralph_script.txt`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - зафиксировать и тестировать правила: retry только по явному stage-return questions/BLOCK, запрет retry в шаге 6 seed, запрет manual preflight drift path;
  - добавить contract-test, который проверяет наличие обязательных guard-правил в full/smoke prompt templates;
  - включить проверку в repo tooling, чтобы изменения prompt не ломали e2e policy.
  **AC:** prompt policy для retry/seed/manual-path проверяется автоматизированным тестом и не деградирует между волнами.
  **Deps:** W99-13
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

### Wave 99D - Runtime contract closure from TST-001 root causes

- [x] **W99-16 (P0) Canonical stage-result parity between writer, loop parser, and status-summary** `skills/aidd-flow-state/runtime/stage_result.py`, `skills/aidd-flow-state/runtime/status_summary.py`, `skills/aidd-loop/runtime/loop_step_stage_result.py`, `tests/test_stage_result.py`, `tests/test_status_summary.py`, `tests/test_loop_step.py`:
  - выровнять единый contract: runtime writer всегда пишет `schema=aidd.stage_result.v1` + canonical `result` для loop stages;
  - использовать общий normalizer для legacy payload (`aidd.stage_result.<stage>.v1`) в `status_summary` и `loop_step_stage_result`, чтобы verdict не расходился между consumers;
  - исключить рекомендации ручной правки `stage.*.result.json`: consumers должны давать только diagnostics + canonical repair hint.
  **AC:** одинаковый stage-result payload даёт одинаковый verdict в `status_summary` и `loop_step`; canonical writer не производит legacy-only shape.
  **Deps:** W99-9
  **Regression/tests:** `python3 -m pytest -q tests/test_stage_result.py tests/test_status_summary.py tests/test_loop_step.py`.
  **Effort:** M
  **Risk:** High

- [x] **W99-17 (P0) Scope key canonicalization end-to-end (`I<N>` alias input, `iteration_id_I<N>` storage only)** `skills/aidd-loop/runtime/loop_run.py`, `skills/aidd-loop/runtime/loop_step.py`, `skills/aidd-loop/runtime/preflight_prepare.py`, `skills/aidd-loop/runtime/loop_step_stage_result.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`:
  - нормализовать work-item alias один раз на входе orchestration и передавать только canonical scope key в downstream stages;
  - при mixed candidate set (`.../I1/...` + `.../iteration_id_I1/...`) выбирать canonical path детерминированно и явно маркировать alias candidate как stale;
  - запретить новые записи в alias-директории (`/loops/<ticket>/I<N>/...`) через preflight/write-path guards.
  **AC:** новые loop артефакты создаются только в canonical scope path; mixed candidates не вызывают ambiguous scope drift.
  **Deps:** W99-5
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py`.
  **Effort:** M
  **Risk:** High

- [x] **W99-18 (P1) Wrapper-to-preflight invocation contract guard (required args + format validation)** `skills/aidd-loop/runtime/loop_step_wrappers.py`, `skills/aidd-loop/runtime/preflight_prepare.py`, `skills/aidd-loop/runtime/preflight_result_validate.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`, `tests/fixtures/loop_step/*`:
  - формализовать обязательные preflight args для implement/review/qa wrappers (`ticket`, `work-item`, `result`, `actions/readmap/writemap paths`);
  - добавить fail-fast validation до запуска preflight: при нарушении контракта возвращать deterministic `reason_code=preflight_contract_mismatch`;
  - покрыть регрессией кейсы из аудита: missing args, неканоничный `work_item`, path mismatch.
  **AC:** wrappers не стартуют preflight с неполным/невалидным аргументным набором; в логах есть точный mismatch reason.
  **Deps:** W99-6, W99-17
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_step.py tests/test_loop_run.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W99-19 (P1) Seed review stall fail-fast with scope-aware diagnostics** `skills/aidd-loop/runtime/loop_step.py`, `skills/aidd-loop/runtime/loop_run.py`, `skills/aidd-flow-state/runtime/status_summary.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`:
  - добавить watchdog на no-progress seed-stage execution с переводом в deterministic blocked reason вместо бесконечного ожидания;
  - в blocked diagnostics выводить active stage/work item, выбранный scope candidate и последний валидный stage-result candidate;
  - синхронизировать timeout verdict с loop summary/event payload для triage без ручного `ps/tail`.
  **AC:** зависание seed review завершает шаг в deterministic `NOT VERIFIED (silent stall)` с полным scope-aware diagnostics набором.
  **Deps:** W99-10, W99-17
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py`.
  **Effort:** M
  **Risk:** Medium

### Wave 99E — Prompt/runtime convergence from TST-001 RCA

- [x] **W99-20 (P0) Research runtime must refresh existing `docs/research/<ticket>.md` (no stale template placeholders)** `skills/researcher/runtime/research.py`, `skills/researcher/templates/research.template.md`, `tests/test_research_command.py`, `tests/test_research_check.py`:
  - для существующего `aidd/docs/research/<ticket>.md` обновлять обязательные секции (`AIDD:PRD_OVERRIDES`, `AIDD:RLM_EVIDENCE`, status-related header fields), а не только создавать файл при первом запуске;
  - удалять/перезаписывать template placeholders (`{{...}}`) в canonical блоках после любого успешного `research.py --auto`;
  - фиксировать детерминированный статус-договор: `reviewed` только при готовом RLM evidence; иначе `pending|warn` + явный handoff hint.
  **AC:** повторный запуск researcher не оставляет template-state в `aidd/docs/research/<ticket>.md`; `research_check` видит актуальный, не-плейсхолдерный документ.
  **Deps:** -
  **Regression/tests:** `python3 -m pytest -q tests/test_research_command.py tests/test_research_check.py`.
  **Effort:** M
  **Risk:** High

- [x] **W99-21 (P0) Research->Plan handshake hardening: deterministic reason codes for blocked readiness** `skills/aidd-core/runtime/research_guard.py`, `skills/plan-new/runtime/research_check.py`, `tests/test_research_check.py`, `tests/test_gate_workflow.py`:
  - унифицировать reason codes для ключевых blocked-состояний (`research_template_stale`, `rlm_status_pending`, `rlm_pack_missing`, `baseline_missing`);
  - вернуть одношаговый canonical next action для каждого reason code (без неоднозначных/legacy подсказок);
  - исключить prompt-drift на `plan-new`: stage должен завершаться быстрым deterministic BLOCKED до длинной исследовательской ветки.
  **AC:** при неготовом research `plan-new` завершается предсказуемо и выдаёт единый reason code + canonical next action.
  **Deps:** W99-20
  **Regression/tests:** `python3 -m pytest -q tests/test_research_check.py tests/test_gate_workflow.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W99-22 (P0) `tasks-new` fail-fast on structural blockers (no deep drift when plan/spec/tasklist invalid)** `skills/tasks-new/runtime/tasks_new.py`, `skills/aidd-flow-state/runtime/tasklist_validate.py`, `tests/test_tasklist_check.py`, `tests/test_cli_subcommands.py`:
  - для stage `tasklist` поднимать severity до error на структурных блокерах (`plan not found`, invalid `PROGRESS_LOG`, invalid Priority/State placeholders в активных итерациях);
  - запускать `tasks_new.py` в strict-mode по умолчанию в slash-orchestration path;
  - при blocked возвращать короткий canonical remediation path (без subagent deep-dive на незакрытых prereqs).
  **AC:** `tasks-new` детерминированно останавливается на структурных блокерах и не уходит в non-converging orchestration.
  **Deps:** W99-21
  **Regression/tests:** `python3 -m pytest -q tests/test_tasklist_check.py tests/test_cli_subcommands.py`.
  **Effort:** M
  **Risk:** High

- [x] **W99-23 (P1) Canonical stage-command vocabulary guard (ban legacy aliases in stage skill guidance)** `skills/review-spec/SKILL.md`, `skills/tasks-new/SKILL.md`, `skills/qa/SKILL.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - запретить в user-facing stage guidance устаревшие команды (`/feature-dev-aidd:planner`, `tasklist-refiner`, `implementer`, `reviewer`) там, где есть canonical stage commands;
  - закрепить canonical equivalents (`plan-new`, `tasks-new`, `implement`, `review`, `qa`) в contracts/next actions;
  - добавить lint-check на banned command vocabulary для stage skills.
  **AC:** stage skills и lint не допускают legacy command drift в рекомендациях.
  **Deps:** W99-13
  **Regression/tests:** `python3 tests/repo_tools/lint-prompts.py --root .`, `python3 -m pytest -q tests/test_prompt_lint.py`.
  **Effort:** S
  **Risk:** Medium

- [x] **W99-24 (P1) Prompt-policy parity tests: audit prompt vs stage skills (manual preflight prohibition must match)** `aidd_test_flow_prompt_ralph_script_full.txt`, `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `tests/repo_tools/test_e2e_prompt_contract.py`:
  - формализовать проверку непротиворечивости: если audit policy запрещает manual preflight recovery, stage skills не должны продвигать manual preflight как default recovery path;
  - проверять parity правил retry/blocked classification для `Unknown skill`, `manual preflight drift`, seed-stage constraints;
  - включить parity-check в repo tooling regression suite.
  **AC:** конфликт prompt-policy между audit шаблоном и stage skill contracts детектируется тестом до релиза.
  **Deps:** W99-13, W99-15, W99-23
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

### Wave 99E Critical Path

1. `W99-20` -> `W99-21` -> `W99-22`
2. `W99-13` -> `W99-23` -> `W99-24`

### Wave 99F — Auto-loop liveness and permission-mode hardening (TST-001 RCA)

- [x] **W99-25 (P0) Stream-aware liveness contract for loop-run/loop-step (main log + stream artifacts)** `skills/aidd-loop/runtime/loop_run.py`, `skills/aidd-loop/runtime/loop_step.py`, `skills/aidd-loop/runtime/loop_step_wrappers.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`:
  - зафиксировать liveness как composite-сигнал: `main log` + `stream_jsonl` (+ `stream.log` при наличии);
  - исключить false `silent_stall`, когда `main log` статичен, но stream продолжает расти;
  - добавить в loop payload/diagnostics явные поля роста (bytes/updated_at) для внешних probe-скриптов.
  **AC:** stream-run не классифицируется как stall при активном `*.stream.jsonl`; диагностический payload содержит оба источника liveness.
  **Deps:** W99-19
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py`.
  **Effort:** M
  **Risk:** High

- [x] **W99-26 (P0) Nested runner permission propagation in Auto-loop (no approval deadlock in non-interactive runs)** `skills/aidd-loop/runtime/loop_step_wrappers.py`, `skills/aidd-loop/runtime/loop_step.py`, `skills/aidd-loop/runtime/loop_run.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`:
  - обеспечить deterministic propagation non-interactive режима для nested `claude` runner (`--dangerously-skip-permissions` policy-driven);
  - для несоответствия режима возвращать явный `reason_code=loop_runner_permissions` до деградации в `stage_result_missing_or_invalid`;
  - сохранить совместимость с custom runner через opt-in/opt-out env policy.
  **AC:** Auto-loop не уходит в approval-denied цикл при корректной конфигурации; при некорректной — быстрый deterministic blocked с точным reason code.
  **Deps:** W99-25
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py`.
  **Effort:** M
  **Risk:** High

- [x] **W99-27 (P1) Stage-result legacy shape compatibility: support `schema_version` alias without relaxing canonical contract** `aidd_runtime/stage_result_contract.py`, `skills/aidd-loop/runtime/loop_step_stage_result.py`, `tests/test_loop_step.py`, `tests/test_stage_result.py`:
  - добавить контролируемый alias `schema_version -> schema` для legacy payload c `aidd.stage_result.v1`;
  - сохранить strict-block для truly invalid schemas/results (v0/unknown/wrong-stage);
  - улучшить diagnostics (`invalid-schema` vs `legacy-alias-used`) для корректного RCA.
  **AC:** legacy payload c `schema_version=aidd.stage_result.v1` корректно нормализуется; реальные invalid schema продолжают блокироваться.
  **Deps:** W99-9, W99-10
  **Regression/tests:** `python3 -m pytest -q tests/test_stage_result.py tests/test_loop_step.py`.
  **Effort:** S
  **Risk:** Medium

- [x] **W99-28 (P1) Reason-code precedence for Auto-loop blocked outcomes (permission mismatch before stage-result fallout)** `skills/aidd-loop/runtime/loop_step.py`, `skills/aidd-loop/runtime/loop_run.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`:
  - при одновременном наборе симптомов (approval-denied + missing stage result) поднимать первопричину permission mismatch как primary reason code;
  - сохранять secondary diagnostics в payload (`stage_result_diagnostics`) без смены root-cause;
  - синхронизировать reason precedence между `loop_step` и `loop_run` summary/event logs.
  **AC:** blocked verdict отражает root cause детерминированно; triage не уходит в ложный `stage_result_missing_or_invalid` как первичный сигнал.
  **Deps:** W99-26, W99-27
  **Regression/tests:** `python3 -m pytest -q tests/test_loop_run.py tests/test_loop_step.py`.
  **Effort:** M
  **Risk:** Medium

- [x] **W99-29 (P1) Prompt/runtime parity tests for stream-liveness and stage-return-only signal extraction** `tests/repo_tools/test_e2e_prompt_contract.py`, `aidd_test_flow_prompt_ralph_script_full.txt`, `aidd_test_flow_prompt_ralph_script.txt`:
  - добавить contract-тест на обязательные правила: stream-aware liveness, запрет false-stall при растущем stream, stage-return-only trigger extraction;
  - валидировать, что prompt policy не трактует вложенные `WARN/Q*` из artifact excerpts как stage incident trigger;
  - включить в CI path рядом с текущими prompt contract checks.
  **AC:** изменения e2e prompt не ломают правила liveness/signal extraction; false-positive drift policy покрыта автоматизированно.
  **Deps:** W99-15, W99-24, W99-25
  **Regression/tests:** `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py`.
  **Effort:** M
  **Risk:** Medium

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
