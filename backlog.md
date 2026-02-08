# Product Backlog

## Wave 96 — Runtime stabilization after W94 (E2E parity)

_Статус: новый, приоритет 0. Цель — закрыть блокеры TST-001 и вернуть детерминированный e2e-contract для idea/loop/qa._

### P0 — Fast path к зелёному e2e

- [ ] **W96-0 (P0) Repro harness + e2e contract checks** `tests/test_e2e_contract_minimal.py`, `tests/test_loop_step.py`, `tests/test_gate_workflow_preflight_contract.py`, `tests/repo_tools/smoke-workflow.sh`:
  - добавить/расширить минимальный integration contract-check: temp workspace, минимальный прогон стадий и проверка обязательных артефактов;
  - зафиксировать инварианты `.active.json` и базовый набор stage wrapper outputs в одном тестовом месте;
  - обеспечить воспроизведение slug pollution и missing preflight artifacts без ручного e2e.
  **AC:** contract-check локально воспроизводит текущие проблемы и детерминированно показывает регрессию/фикс.
  **Regression/tests:** новый `tests/test_e2e_contract_minimal.py` или эквивалентное расширение существующих integration тестов.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-1 (P0) Slug hygiene: `slug_hint` только токен** `tools/active_state.py`, `tools/feature_ids.py`, `tools/runtime.py`, `tests/test_active_state.py`, `tests/test_feature_ids_root.py`:
  - развести `slug_hint` (стабильный токен) и feature label/note/answers (отдельное поле или только PRD/plan/tasklist);
  - обновить writer active-state для `idea-new`: валидный slug пишется как есть, note никогда не конкатенируется в `slug_hint`;
  - добавить валидацию slug токена (`^[a-z0-9][a-z0-9-]{0,80}$`) и правило: невалидный второй аргумент трактуется как note.
  **AC:** после `idea-new TST-001 tst-001-demo <note>` поле `aidd/docs/.active.json.slug_hint` равно `tst-001-demo`; повторный запуск с `AIDD:ANSWERS` не загрязняет slug.
  **Regression/tests:** unit + integration кейс “slug + длинный note” сохраняет чистый `slug_hint`.
  **Effort:** M
  **Risk:** High

- [ ] **W96-2 (P0, blocker) SKILL_FIRST wrappers: preflight/readmap/writemap/actions/logs always-on** `tools/loop_step.py`, `tools/loop_run.py`, `tools/gate_workflow.py`, `tools/output_contract.py`, `skills/aidd-reference/wrapper_lib.sh`, `skills/implement/scripts/preflight.sh`, `skills/review/scripts/preflight.sh`, `skills/qa/scripts/preflight.sh`, `tests/test_gate_workflow_preflight_contract.py`, `tests/test_output_contract.py`, `tests/test_loop_step.py`, `tests/repo_tools/smoke-workflow.sh`:
  - выровнять единый stage wrapper orchestration для `implement|review|qa` (preflight -> stage core -> run/postflight) в ручном и loop путях;
  - гарантировать минимальные артефакты даже при “нулевых действиях”: `actions.template/actions`, `readmap/writemap`, `stage.preflight.result`, `wrapper.*.log`;
  - усилить enforcement в gate-workflow (SKILL_FIRST): отсутствие обязательных артефактов и `AIDD:ACTIONS_LOG` не проходит как success;
  - зафиксировать workspace path resolution: записи только в `$PROJECT_DIR/aidd/**`, отсутствие root = явный BLOCKED.
  **AC:** после seed `implement` и `review` обязательные артефакты созданы, output-contract содержит существующий `AIDD:ACTIONS_LOG`.
  **Regression/tests:** unit + integration + smoke проверяют полный набор обязательных wrapper outputs.
  **Effort:** L
  **Risk:** High

### P1 — Семантика loop/qa и инварианты

- [ ] **W96-3 (P1) `user_approval_required` contract + loop-run diagnostics** `tools/loop_run.py`, `tools/loop_step.py`, `tools/runtime.py`, `tests/test_loop_run.py`, `tests/test_loop_step.py`:
  - унифицировать семантику reason-code: если нужен approval, стадия возвращает `blocked`, а loop-run останавливается на текущей стадии;
  - убрать сценарий “continue на implement -> blocked на review” для одного и того же work item;
  - расширить диагностику blocked: обязательные `reason_code`, `reason`, ссылка на stage result и wrapper/cli logs.
  **AC:** при `user_approval_required` loop-run завершается детерминированно на корректной стадии с полным diagnostic output (без “немого” exit 20).
  **Regression/tests:** integration fixture на approval-required + unit mapping reason-code -> status/exit.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-4 (P1) iteration_id format policy (`M#` и `I#`)** `tools/feature_ids.py`, `tools/active_state.py`, `tools/loop_step.py`, `tools/loop_run.py`, `tests/test_feature_ids_root.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`:
  - быстрый путь: принять оба формата `iteration_id=(I|M)\\d+` в валидаторах/invariants;
  - синхронизировать проверки loop/stage/tests и устранить лишние WARN из-за расхождения ожиданий;
  - документировать выбранную политику формата в backlog/release notes при необходимости.
  **AC:** `iteration_id=M1` и `iteration_id=I1` валидны в active state/loop/test contracts.
  **Regression/tests:** unit валидатора + integration loop-step без деградации на `M1`.
  **Effort:** S
  **Risk:** Low

- [ ] **W96-5 (P1) QA exit-code policy aligned with report status** `tools/qa.py`, `tools/qa.sh`, `hooks/gate-qa.sh`, `tools/runtime.py`, `tests/test_qa_runner.py`, `tests/test_gate_qa.py`:
  - синхронизировать exit-code команды QA со статусом отчёта;
  - policy: `BLOCKED -> exit 2`, `READY|WARN -> exit 0`, и одинаковая семантика в stdout/stage_result/report;
  - исключить “exit 0 при BLOCKED report” в CI automation path.
  **AC:** QA возвращает не-zero при `BLOCKED`, а generated report/stage_result/stdout не противоречат друг другу.
  **Regression/tests:** unit mapping report_status -> exit_code + integration fixture с blocker findings.
  **Effort:** S
  **Risk:** Medium

### Wave 96 follow-up — re-audit gaps (TST-001 rerun)

- [ ] **W96-6 (P0) Manual seed parity: wrappers обязательны не только в loop-step** `tools/runtime.py`, `tools/loop_step.py`, `tools/output_contract.py`, `skills/implement/scripts/preflight.sh`, `skills/review/scripts/preflight.sh`, `tests/test_loop_step.py`, `tests/test_output_contract.py`, `tests/repo_tools/smoke-workflow.sh`:
  - выровнять исполнение `implement/review` в ручном seed и loop-path: одинаковый wrapper chain и одинаковые артефакты;
  - исключить сценарий “seed exit=0, но actions/readmap/writemap/preflight/logs отсутствуют”;
  - закрепить в output contract обязательный `AIDD:ACTIONS_LOG` для seed run.
  **AC:** ручные seed `implement` + `review` создают тот же обязательный набор wrapper-артефактов, что и loop-step.
  **Regression/tests:** integration тест seed run проверяет наличие `stage.preflight.result.json`, readmap/writemap, actions.template/actions, wrapper logs.
  **Effort:** M
  **Risk:** High

- [ ] **W96-7 (P0) Gate preflight enforcement без зависимости от src-changes** `tools/gate_workflow.py`, `tools/loop_step.py`, `tests/test_gate_workflow_preflight_contract.py`, `tests/test_loop_step.py`:
  - убрать условие, при котором проверка preflight contract срабатывает только при `has_src_changes`;
  - для SKILL_FIRST stage-success требовать обязательный preflight/docops минимум независимо от diff типа (code/doc/none);
  - сохранить осмысленную диагностику `reason_code` при BLOCK.
  **AC:** stage не может пройти success без обязательных preflight/docops артефактов даже при отсутствии src-изменений.
  **Regression/tests:** unit + integration кейс “no src changes, stage success” должен блокироваться при отсутствии preflight contract.
  **Effort:** M
  **Risk:** High

- [ ] **W96-8 (P1) Scope-key consistency между wrapper chain и stage_result** `tools/loop_step.py`, `tools/feature_ids.py`, `tools/runtime.py`, `tests/test_loop_step.py`, `tests/test_feature_ids_root.py`:
  - устранить дрейф scope key (например, wrapper logs под `I1`, а iteration summary сообщает `I2`);
  - закрепить единый источник scope key для preflight/run/postflight и финального stage_result;
  - добавить trace в loop logs: `scope_key_before`, `scope_key_after`, `scope_key_effective`.
  **AC:** paths в wrapper logs, actions/context и `stage.<stage>.result.json` совпадают по одному `scope_key` на итерацию.
  **Regression/tests:** integration fixture проверяет совпадение scope key в путях артефактов и summary loop-step.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-9 (P1) BLOCKED diagnostics completeness: reason/reason_code/stage_result_path обязательны** `tools/loop_run.py`, `tools/loop_step.py`, `tools/stage_result.py`, `skills/review/scripts/postflight.sh`, `tests/test_loop_run.py`, `tests/test_stage_result.py`:
  - запретить “немой blocked”: если `result=blocked`, то должны быть заполнены `reason_code` и человекочитаемый `reason`;
  - добавить fallback mapping в loop-run при blocked без reason-code (например `blocked_without_reason`);
  - в postflight wrappers пробрасывать исходные ошибки shell/permission в stage_result.
  **AC:** любой blocked в loop-run имеет детерминированный `reason_code`, `reason` и ссылку на stage_result/wrapper log.
  **Regression/tests:** фикстура blocked без reason приводит к стабильному fallback reason-code и информативному loop-run output.
  **Effort:** M
  **Risk:** High

- [ ] **W96-10 (P1) QA tri-source consistency: report vs stage_result vs process exit** `tools/qa.py`, `tools/stage_result.py`, `hooks/gate-qa.sh`, `tests/test_qa_runner.py`, `tests/test_gate_qa.py`, `tests/test_stage_result.py`:
  - устранить рассинхрон, когда QA report `WARN`, а `stage.qa.result` = `blocked/no_tests_hard`;
  - определить единый SoT для QA финального статуса и маппинг в exit-code/loop semantics;
  - добавить явные правила для `no_tests_hard`: когда это WARN, когда BLOCKED.
  **AC:** QA report, stage_result и код процесса согласованы и не противоречат друг другу в одном прогоне.
  **Regression/tests:** matrix тестов на `READY|WARN|BLOCKED|no_tests_hard` проверяет единый итоговый статус и код выхода.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-11 (P2) Contract/docs alignment for audit tooling (work_item + QA/loop semantics)** `templates/aidd/AGENTS.md`, `templates/aidd/docs/prompting/conventions.md`, `aidd_test_flow_prompt_ralph_script.txt`, `tests/repo_tools/smoke-workflow.sh`:
  - синхронизировать аудит-инварианты с runtime: допустимый формат `work_item` (`iteration_id=<ticket>-I<N>|M<N>`), QA exit `2` при BLOCKED, `user_approval_required` как корректный hard stop;
  - обновить e2e-подсказки, чтобы валидное поведение не помечалось как ложный FAIL;
  - сохранить backward-compatible формулировки для legacy mode.
  **AC:** аудит-скрипт не выдаёт ложных blocker-findings на корректное поведение Wave 96.
  **Regression/tests:** smoke/audit fixture проверяет новые контракты и не падает на ожидаемых WARN-сценариях.
  **Effort:** S
  **Risk:** Low

### Wave 96 architecture follow-up — shared skills/tooling split

_Статус: proposed, приоритет 1. Цель — убрать дубли в frontmatter/tools и перейти к явной shared-skill модели без breaking-change._

- [ ] **W96-12 (P1) Shared RLM skill for agents/stages via frontmatter preload** `skills/aidd-rlm/SKILL.md`, `agents/*.md`, `skills/*/SKILL.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `tools/entrypoints-bundle.txt`, `dev/reports/migrations/commands_to_skills_frontmatter.json`:
  - добавить preloaded shared skill `aidd-rlm` (user-invocable: false) как единый SoT для `rlm-slice/rlm-*` тулов;
  - подключить его в frontmatter (`skills:`) у агентов/стадий, где сейчас повторяется одинаковый RLM toolset;
  - сократить дубли `allowed-tools` и зафиксировать policy в lint/baseline.
  **AC:** RLM toolset задаётся в одном shared skill, агенты/стадии подключают его через frontmatter без копипасты списков.
  **Regression/tests:** prompt-lint + baseline parity + entrypoints bundle проходят; нет drift по agent/skill frontmatter.
  **Effort:** L
  **Risk:** High

- [ ] **W96-13 (P1) Stage skill inheritance contract for shared runtime toolsets** `tests/repo_tools/lint-prompts.py`, `tools/entrypoints_bundle.py`, `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `dev/reports/migrations/commands_to_skills_frontmatter.json`, `tests/test_prompt_lint.py`:
  - ввести явный контракт наследования shared toolsets для stage skills (через `skills:`/preload вместо ручного дублирования общих tool entries);
  - обновить lint так, чтобы stage skills могли валидно ссылаться на shared runtime skill и не падали на ложный baseline mismatch;
  - сохранить обратную совместимость: на переходный период поддержать старый полный `allowed-tools` до завершения миграции.
  **AC:** `implement/review/qa` используют общий runtime skill-contract; в stage SKILL.md нет повторения одинакового списка shared тулов.
  **Regression/tests:** lint-prompts фиксирует новый контракт наследования и не допускает пустых/битых preload ссылок.
  **Effort:** L
  **Risk:** High

- [ ] **W96-14 (P1) Migrate stage-only singleton tools to stage scripts + deprecation shims** `skills/idea-new/scripts/*`, `skills/plan-new/scripts/*`, `skills/review-spec/scripts/*`, `skills/status/scripts/*`, `tools/analyst-check.sh`, `tools/research-check.sh`, `tools/prd-review.sh`, `tools/status.sh`, `tools/index-sync.sh`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/shim-regression.sh`:
  - перенести stage-only entrypoints (используемые одной стадией) в `skills/<stage>/scripts/*` и вызывать их из stage SKILL;
  - оставить `tools/*.sh` как deprecation shims (warn-only), чтобы не ломать legacy CLI/хуки;
  - добавить migration notes и явный removal-window для shim-фазы.
  **AC:** stage-only команды живут рядом со стадией; старые `tools/*.sh` продолжают работать через shims с deprecation warning.
  **Regression/tests:** smoke + shim-regression подтверждают совместимость и отсутствие runtime regressions.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-15 (P2) Relocate `aidd-reference` runtime assets out of skill-like folder** `tools/wrappers/wrapper_lib.sh`, `tools/wrappers/wrapper_contract.md`, `skills/aidd-reference/wrapper_lib.sh`, `skills/aidd-reference/wrapper_contract.md`, `tests/repo_tools/skill-scripts-guard.py`, `AGENTS.md`:
  - перенести shared wrapper runtime assets в `tools/wrappers/*` как canonical путь для shared tooling;
  - в `skills/aidd-reference/*` оставить совместимые прокси/копии на deprecation window;
  - обновить guards/docs, чтобы было явно: это runtime library, а не user skill entrypoint.
  **AC:** canonical wrapper library находится в `tools/wrappers/*`; все stage scripts работают без изменения поведения; legacy path остаётся совместим.
  **Regression/tests:** skill-scripts-guard + wrapper contract tests проходят для нового canonical path и shim path.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-16 (P1) Tools inventory v2: shared-skill consumers + shim awareness** `tools/tools_inventory.py`, `tests/test_tools_inventory.py`, `tests/repo_tools/ci-lint.sh`, `AGENTS.md`, `README.md`, `README.en.md`:
  - расширить inventory отчёт: отдельно показывать canonical stage scripts, shared skills и deprecated `tools/*.sh` shims;
  - добавить классификацию consumers (`agent`, `skill`, `hook`, `test`, `shim`) и флаг “tool has canonical replacement”;
  - использовать отчёт для контроля deprecation progress без ложных “unused” сигналов.
  **AC:** inventory различает canonical/shared/shim пути и корректно показывает потребителей после миграции.
  **Regression/tests:** unit тесты inventory + CI guard на неконсистентные shims/canonical mappings.
  **Effort:** M
  **Risk:** Medium

### Wave 96 migration backlog — additional candidates (CI/lint aware)

- [ ] **W96-17 (P1) Researcher toolchain relocation to stage scripts + compatibility shims** `skills/researcher/scripts/rlm-*.sh`, `skills/researcher/scripts/reports-pack.sh`, `tools/rlm-*.sh`, `tools/reports-pack.sh`, `skills/researcher/SKILL.md`, `agents/researcher.md`, `tests/repo_tools/smoke-workflow.sh`, `tests/repo_tools/shim-regression.sh`:
  - перенести researcher-only entrypoints (`rlm-nodes-build`, `rlm-links-build`, `rlm-jsonl-compact`, `rlm-finalize`, `rlm-verify`, `reports-pack`) в `skills/researcher/scripts/*`;
  - оставить `tools/*` как deprecation shims с warn-only режимом;
  - обновить stage/agent refs на canonical `skills/researcher/scripts/*`.
  **AC:** researcher stage использует canonical stage scripts; legacy `tools/rlm-*.sh` и `tools/reports-pack.sh` продолжают работать через shims.
  **Regression/tests:** smoke research path + shim-regression подтверждают отсутствие breakage.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-18 (P1) QA runtime entrypoint relocation (`qa.sh`) with gate/template compatibility** `skills/qa/scripts/qa.sh`, `tools/qa.sh`, `skills/qa/SKILL.md`, `templates/aidd/config/gates.json`, `hooks/gate-qa.sh`, `tests/helpers.py`, `tests/test_qa_runner.py`:
  - ввести canonical `skills/qa/scripts/qa.sh` (обёртка над `tools/qa.py`) и переключить stage path на него;
  - сохранить `tools/qa.sh` как совместимый shim для hooks/tests/legacy docs;
  - выровнять ссылки в gates/templates/helpers, чтобы не было path drift.
  **AC:** QA stage запускается через stage script; gate/config/test harness остаются совместимыми в переходный период.
  **Regression/tests:** QA unit/integration + gate-qa + smoke проходят для canonical path и shim path.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-19 (P1) Status stage relocation (`status.sh` + `index-sync.sh`)** `skills/status/scripts/status.sh`, `skills/status/scripts/index-sync.sh`, `tools/status.sh`, `tools/index-sync.sh`, `skills/status/SKILL.md`, `README.md`, `README.en.md`, `tests/test_status.py`:
  - перенести status-stage singleton entrypoints к stage scripts;
  - оставить `tools/status.sh` и `tools/index-sync.sh` как deprecated compatibility shims;
  - синхронизировать docs/examples, чтобы canonical путь был у status skill.
  **AC:** status skill использует `skills/status/scripts/*`; legacy tool entrypoints работают и печатают deprecation notice.
  **Regression/tests:** status/index tests + smoke подтверждают parity поведения.
  **Effort:** M
  **Risk:** Low

- [ ] **W96-20 (P1) Shared loop-runtime skill contract (non-RLM) for implement/review/qa** `skills/aidd-loop-runtime/SKILL.md`, `skills/implement/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `tests/repo_tools/lint-prompts.py`, `dev/reports/migrations/commands_to_skills_frontmatter.json`, `tests/test_prompt_lint.py`:
  - вынести общий loop runtime toolset (`progress`, `stage-result`, `status-summary`, `tasklist-*`, `loop-pack`, `diff-boundary-check`) в preloaded shared skill;
  - подключить shared skill через `skills:` в implement/review/qa и убрать дубли перечислений;
  - обновить lint/baseline контракт, чтобы inheritance был валиден и проверяем.
  **AC:** implement/review/qa используют единый shared loop-runtime contract, а не три несинхронных списка tool entries.
  **Regression/tests:** prompt-lint/baseline parity + loop smoke не показывают регрессию по разрешённым tool paths.
  **Effort:** L
  **Risk:** High

- [ ] **W96-21 (P2) Hook/docs/reference path normalization for migrated canonical scripts** `hooks/context_gc/pretooluse_guard.py`, `hooks/gate-tests.sh`, `hooks/gate-qa.sh`, `tools/gate_workflow.py`, `README.md`, `README.en.md`, `docs/legacy/commands/*.md`, `templates/aidd/docs/prompting/conventions.md`:
  - нормализовать подсказки/ошибки/доки: canonical path указывать как `skills/<stage>/scripts/*`, а `tools/*` обозначать как compatibility shim;
  - для hook hints добавить dual-path guidance (canonical + legacy) на deprecation window;
  - убрать ложные рекомендации, которые ведут на устаревший entrypoint без пояснения.
  **AC:** hook messages и docs последовательно указывают canonical путь после миграции, при этом legacy-путь остаётся документирован как shim.
  **Regression/tests:** docs/lint checks + hook tests подтверждают консистентность ссылок и отсутствие stale paths.
  **Effort:** S
  **Risk:** Low

### Wave 96 deferred core APIs — keep stable in first wave

_Статус: proposed, приоритет 0. Цель — не трогать high-coupling entrypoints в первой волне, но подготовить безопасную фазу 2 без регрессий._

- [ ] **W96-22 (P0) Freeze + contract snapshot for `tools/init.sh` bootstrap API** `tools/init.sh`, `tools/init.py`, `tools/runtime.py`, `tools/gate_workflow.py`, `hooks/gate-tests.sh`, `hooks/gate-prd-review.sh`, `hooks/gate-qa.sh`, `tests/test_init_aidd.py`, `tests/helpers.py`, `.github/workflows/ci.yml`:
  - зафиксировать `tools/init.sh` как canonical bootstrap API для wave-1 (no relocation), чтобы не ломать хуки/рантайм/CI подсказки;
  - добавить contract snapshot тест/guard: workspace-root bootstrap, idempotency, `--force`, `--detect-build-tools`, hook error hints;
  - подготовить migration seam (shim policy + explicit phase-2 gate), но без фактического переноса entrypoint.
  **AC:** любые изменения вокруг init не ломают текущий bootstrap контракт и hook guidance; accidental relocation блокируется CI guard.
  **Regression/tests:** `tests/test_init_aidd.py` + hook integration checks + smoke на init path.
  **Effort:** M
  **Risk:** High

- [ ] **W96-23 (P0) Hook-coupling hardening for `tools/research.sh` and `tools/tasks-derive.sh`** `tools/research.sh`, `tools/research.py`, `tools/tasks-derive.sh`, `tools/tasks_derive.py`, `hooks/gate-tests.sh`, `hooks/gate-qa.sh`, `tools/gate_workflow.py`, `tools/research_guard.py`, `skills/researcher/SKILL.md`, `skills/review/SKILL.md`, `skills/qa/SKILL.md`, `tests/test_tasks_derive.py`, `tests/test_research_rlm_e2e.py`:
  - закрепить эти entrypoints как hook-facing stable API в wave-1 (без переноса в stage scripts);
  - вынести в один SoT формулировки подсказок/hints для `research` и `tasks-derive`, чтобы убрать string drift между hooks/tools/docs;
  - добавить compatibility matrix тестов на вызов из hooks + stage skills + direct CLI.
  **AC:** `research.sh`/`tasks-derive.sh` остаются стабильными публичными точками для hooks и stage flow; подсказки консистентны.
  **Regression/tests:** gate-qa/gate-tests + tasks-derive/research e2e тесты подтверждают отсутствие path regressions.
  **Effort:** M
  **Risk:** High

- [ ] **W96-24 (P0) Public DocOps API hardening for `tools/actions-apply.sh` and `tools/context-expand.sh`** `tools/actions-apply.sh`, `tools/actions_apply.py`, `tools/context-expand.sh`, `tools/context_expand.py`, `hooks/context_gc/pretooluse_guard.py`, `skills/aidd-core/scripts/context_expand.sh`, `skills/*/scripts/postflight.sh`, `tests/test_context_expand.py`, `tests/repo_tools/schema-guards.sh`:
  - зафиксировать DocOps API surface как canonical `tools/*` (не переносить в первой волне), потому что на него опираются pretooluse guard и loop wrappers;
  - оформить explicit compatibility policy (schemas, exit codes, audit log contract, CLI flags) и добавить regression checks;
  - добавить anti-regression guard: любые изменения в этих API требуют обновления schema/contract tests в одном PR.
  **AC:** `actions-apply`/`context-expand` сохраняют стабильный публичный контракт; loop и context-gc не деградируют при refactor.
  **Regression/tests:** `tests/test_context_expand.py` + schema guards + wrapper smoke покрывают API контракты end-to-end.
  **Effort:** M
  **Risk:** High

- [ ] **W96-25 (P1) Do-not-migrate guardrails in lint/inventory/CI for deferred APIs** `tests/repo_tools/lint-prompts.py`, `tools/tools_inventory.py`, `tests/test_tools_inventory.py`, `tests/repo_tools/ci-lint.sh`, `AGENTS.md`, `README.md`, `README.en.md`:
  - добавить явные guardrails: `init.sh`, `research.sh`, `tasks-derive.sh`, `actions-apply.sh`, `context-expand.sh` считаются deferred-core APIs в wave-1;
  - inventory должен помечать их как `core_api=true`/`migration_deferred=true` и не рекомендовать auto-relocate;
  - lint/CI должны ловить silent relocation без shim/compat notes.
  **AC:** accidental перенос deferred-core API без shim и migration note блокируется CI.
  **Regression/tests:** inventory/lint unit tests + CI lint scenario на нарушение deferred policy.
  **Effort:** S
  **Risk:** Medium

- [ ] **W96-26 (P2) Phase-2 migration blueprint for deferred-core APIs (design-only, no move)** `aidd/reports/audit/wave_96_changes.md`, `AGENTS.md`, `CHANGELOG.md`, `docs/legacy/commands/*.md`:
  - подготовить дизайн-план phase-2 для каждого deferred API: target canonical path, shim strategy, hook rollout order, rollback plan;
  - определить deprecation window и exit criteria (какие hooks/tests/docs должны перейти первыми);
  - не переносить код в этом таске, только зафиксировать пошаговый blueprint и риски.
  **AC:** есть согласованный план phase-2 без кодовых переносов, с явно заданными критериями готовности и rollback шагами.
  **Regression/tests:** n/a (design-only artifact), но smoke/ci должны оставаться зелёными.
  **Effort:** S
  **Risk:** Low

### Wave 96 doc-context minimization — AIDD docs через SKILL + scripts

_Статус: proposed, приоритет 1. Цель — сократить контекст в planning/loop стадиях за счёт slice/patch-first доступа к `aidd/docs/**`, при этом canonical doc-io entrypoints лежат рядом с SKILL._

- [ ] **W96-27 (P0) Canonical перенос `md-slice`/`md-patch` в `skills/aidd-core/scripts` + tool shims** `skills/aidd-core/scripts/md-slice.sh`, `skills/aidd-core/scripts/md-patch.sh`, `skills/aidd-core/SKILL.md`, `tools/md-slice.sh`, `tools/md-patch.sh`, `tests/test_md_slice.py`, `tests/repo_tools/shim-regression.sh`, `tests/test_prompt_lint.py`:
  - перенести canonical doc-io shell entrypoints в `skills/aidd-core/scripts/*` и обновить stage usage на эти пути;
  - `tools/md-slice.sh` и `tools/md-patch.sh` оставить как compatibility shims с deprecation warning;
  - нормализовать stdout contract: `AIDD:READ_LOG`/`AIDD:ACTIONS_LOG` должны ссылаться на существующие workspace-артефакты.
  **AC:** canonical doc-io path = `skills/aidd-core/scripts/md-*.sh`; legacy `tools/md-*.sh` работает как shim без изменения поведения.
  **Regression/tests:** unit/integration для `md-slice`/`md-patch` + shim-regression + prompt-lint на canonical path.
  **Effort:** M
  **Risk:** High

- [ ] **W96-28 (P1) Planning stages migration на canonical SKILL scripts (`md-slice`/`md-patch`)** `skills/idea-new/SKILL.md`, `skills/researcher/SKILL.md`, `skills/plan-new/SKILL.md`, `skills/review-spec/SKILL.md`, `skills/tasks-new/SKILL.md`, `agents/*.md`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`:
  - для `idea/research/plan/review-spec/tasks` сделать `skills/aidd-core/scripts/md-slice.sh` и `skills/aidd-core/scripts/md-patch.sh` дефолтным путём чтения/записи `aidd/docs/**`;
  - прямой full-file Read/Write разрешить только как fallback с обязательной фиксацией причины в `AIDD:READ_LOG`;
  - синхронизировать frontmatter и stage инструкции, чтобы избежать drift между skill и agent промптами.
  **AC:** planning-stage SKILLs используют canonical `skills/aidd-core/scripts/md-*.sh` как default; прямой full-doc доступ становится явным исключением.
  **Regression/tests:** prompt-lint + smoke на planning stages фиксируют slice-first поведение и canonical script paths.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-29 (P1) Hook/lint guardrails для full-doc IO и context bloat** `hooks/context_gc/pretooluse_guard.py`, `tests/test_hook_rw_policy.py`, `tests/repo_tools/lint-prompts.py`, `tests/test_prompt_lint.py`, `AGENTS.md`:
  - ужесточить pretooluse policy: full-doc чтение/запись `aidd/docs/**` без block-ref считается нарушением (strict=BLOCK, fast=WARN);
  - добавить controlled escape hatch (`AIDD_ALLOW_FULL_DOC_IO=1`) с обязательным reason-code в логах;
  - в lint добавить проверку, что stage prompt не рекомендует full-doc Read как default и указывает canonical SKILL scripts для doc-io.
  **AC:** контекст-блоат сценарии ловятся hook/lint до выполнения стадии; отклонения имеют явный reason-code и fallback-путь.
  **Regression/tests:** `test_hook_rw_policy` + `test_prompt_lint` покрывают strict/fast + escape-hatch ветки.
  **Effort:** M
  **Risk:** High

- [ ] **W96-30 (P1) Script-mediated writes для planning docs через canonical `md-patch` + DocOps actions** `tools/docops.py`, `tools/actions_apply.py`, `skills/aidd-core/scripts/md-patch.sh`, `skills/*/scripts/postflight.sh`, `tests/test_context_expand.py`, `tests/test_output_contract.py`:
  - расширить набор DocOps-операций для planning-доков (section replace/append/checklist update) вместо прямого редактирования больших файлов;
  - `md-patch` path в SKILL должен генерировать/применять actions с детерминированным audit trail;
  - сохранить публичную совместимость `tools/actions-apply.sh` (canonical API) в первой волне.
  **AC:** обновления PRD/plan/tasklist выполняются через actions/patch pipeline с повторяемым результатом и логами.
  **Regression/tests:** DocOps/action apply tests подтверждают корректное обновление секций без full-file rewrite.
  **Effort:** L
  **Risk:** High

- [ ] **W96-31 (P1) Read/Write telemetry budgets + gate integration** `tools/output_contract.py`, `tools/gate_workflow.py`, `tools/context_pack.py`, `tests/test_output_contract.py`, `tests/test_gate_workflow.py`, `templates/aidd/config/gates.json`:
  - ввести machine-readable read/write telemetry (`read_items`, bytes, full-read count) и лимиты на стадию;
  - добавить gate-policy: превышение budget => WARN/BLOCK (по профилю), с явным `reason_code`;
  - связать telemetry с `AIDD:READ_LOG`/`AIDD:ACTIONS_LOG`, чтобы аудит видел причину роста контекста.
  **AC:** stage-result и gate-workflow показывают измеримый расход контекста и детерминированно реагируют на превышение лимитов.
  **Regression/tests:** matrix тестов на budget breach для fast/strict профилей.
  **Effort:** M
  **Risk:** Medium

- [ ] **W96-32 (P2) CI/inventory enforcement для Doc IO migration** `tools/tools_inventory.py`, `tests/test_tools_inventory.py`, `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`, `README.md`, `README.en.md`:
  - добавить в inventory отдельную классификацию doc-io consumers (canonical SKILL scripts vs compatibility shims vs direct model IO);
  - CI/lint должны сигнализировать, если stage вернулся к full-doc default или использует `tools/md-*.sh` как primary path;
  - обновить docs c dual-path guidance: canonical `skills/aidd-core/scripts/md-*.sh` + compatibility `tools/md-*.sh`.
  **AC:** migration status по Doc IO прозрачно виден в inventory/CI; откаты в full-doc default и drift на tool-path ловятся автоматически.
  **Regression/tests:** inventory unit + smoke/assertions на обязательное присутствие canonical SKILL scripts в stage flow.
  **Effort:** M
  **Risk:** Medium

## Wave 97 — Residual backlog after W95/W89.5 audit

_Статус: новый, приоритет 0. Цель — оставить только реально незакрытые задачи после code-аудита и убрать исторический шум._

- [ ] **W97-1 (carry-over W95-F2, P1) Cleanup tracked ad-hoc prompt artifact** `aidd_test_flow_prompt_ralph_script.txt`, `.gitignore`, `docs/examples/**`, `CHANGELOG.md`, `README.md`, `README.en.md`:
  - определить статус `aidd_test_flow_prompt_ralph_script.txt`: удалить из tracking или перенести в `docs/examples/**` с metadata header;
  - синхронизировать `.gitignore` и release notes (сейчас ignore-паттерн есть, но файл всё ещё tracked);
  - убрать dangling references после финального решения по пути.
  **AC:** ad-hoc артефакт либо удалён из tracking, либо формализован в `docs/examples/**`; docs/changelog не противоречат фактическому состоянию.
  **Effort:** S
  **Risk:** Low
  **Carry-over:** W95-F2

- [ ] **W97-2 (carry-over W95-E4, P2) Phase-2 removal plan for deprecated review shims** `tools/review-pack.sh`, `tools/review-report.sh`, `tools/reviewer-tests.sh`, `README.md`, `README.en.md`, `CHANGELOG.md`, `tests/repo_tools/shim-regression.sh`:
  - зафиксировать срок и условия удаления compatibility shim entrypoints review toolchain;
  - описать migration window и release policy для breaking-change;
  - добавить guard, чтобы после removal-window shim path действительно удалялся.
  **AC:** утверждён phase-2 план удаления review shim-ов с конкретным removal-window и проверками в CI/docs.
  **Effort:** S
  **Risk:** Medium
  **Carry-over:** W95-E4

- [ ] **W97-3 (carry-over W89.5-8, P1) Enforce output-contract warnings in loop/gates** `tools/output_contract.py`, `tools/loop_step.py`, `tools/gate_workflow.py`, `tools/stage_result.py`, `tests/test_output_contract.py`, `tests/test_loop_step.py`, `tests/test_gate_workflow.py`:
  - перевести `output.contract.json` из diagnostic-only в policy input (минимум WARN/BLOCK rules по профилю fast|strict);
  - добавить явный reason-code propagation в stage_result/loop payload при нарушениях read-budget/read-order/status mismatch;
  - покрыть интеграционными тестами сценарии `read_log_too_long`, `full_doc_without_missing_fields`, `read_order_*`.
  **AC:** нарушения output-contract детерминированно влияют на gate/loop решение; `reason_code` отражается в stage_result и loop logs.
  **Effort:** M
  **Risk:** High
  **Carry-over:** W89.5-8

- [ ] **W97-4 (carry-over W89.5-9, P1) Non-blocking stale review-pack recovery path** `tools/loop_step.py`, `tools/loop_run.py`, `tools/review_pack.py`, `tests/test_loop_step.py`, `tests/test_loop_run.py`, `tests/test_loop_semantics.py`:
  - убрать hard-block на `review_pack_stale` в recoverable сценариях (при успешной регенерации pack/review evidence);
  - оставить BLOCK только для неустранимых состояний (`review_pack_missing` после retry, invalid schema и т.п.);
  - добавить telemetry в loop logs: `stale_recovered` vs `stale_blocked`.
  **AC:** stale review-pack по recoverable сценариям не останавливает loop-run; tests фиксируют recovery path и отличимые reason-codes.
  **Effort:** M
  **Risk:** Medium
  **Carry-over:** W89.5-9

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
