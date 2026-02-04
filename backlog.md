# Product Backlog

## Wave 89 — Doc consolidation + Flow simplification (pack-first, меньше чтений, без anchors)

_Статус: новый, приоритет 1. Цель — убрать дубли документации, сократить чтения, упростить runtime, сделать pack‑first единственным режимом._

- [x] **W89-1** `templates/aidd/docs/architecture/**`, `templates/aidd/docs/**`, `templates/aidd/reports/context/template.context-pack.md`, `commands/*.md`, `agents/*.md`, `README*.md`, `AGENTS.md`, `templates/aidd/AGENTS.md`, `backlog.md`:
  - полностью удалить архитектурные документы и все упоминания архитектурного профиля;
  - удалить `templates/aidd/docs/architecture/**`;
  - убрать `arch_profile` из context pack шаблонов и любых “Paths”/References;
  - обновить команды/агенты/доки, где фигурировали архитектурные пути.
  **AC:** нет упоминаний `architecture`/`arch_profile` в docs/templates/commands/agents/README/AGENTS; проверки tools/CI покрываются W89-27.
  **Deps:** -

- [x] **W89-2** `templates/aidd/docs/anchors/*`, `templates/aidd/docs/prompting/conventions.md`, `templates/aidd/conventions.md`, `commands/*.md`, `agents/*.md`, `tests/*`:
  - удалить anchors как обязательный источник чтения;
  - перенести stage‑specific правила в `conventions.md` (разделы по стадиям);
  - удалить директорию `templates/aidd/docs/anchors/`;
  - удалить `templates/aidd/conventions.md` и любые ссылки на этот файл;
  - обновить ссылки в командах/агентах/доках и тестах.
  **AC:** anchors не требуются и не читаются; stage‑специфика живёт в `conventions.md`; ссылки на anchors удалены; нет ссылок на `templates/aidd/conventions.md`.
  **Deps:** W89-1

- [x] **W89-3** `templates/aidd/ast-grep/**`, `templates/aidd/docs/**`, `commands/*.md`, `agents/*.md`, `README*.md`, `AGENTS.md`:
  - полностью удалить все упоминания `ast-grep` (доки, шаблоны, тесты, пайплайны);
  - удалить `templates/aidd/ast-grep/**` и любые связанные примеры/fixtures;
  - обновить любые ссылки/инструкции, где `ast-grep` фигурировал как источник evidence.
  **AC:** нет упоминаний `ast-grep` в docs/templates/commands/agents/README/AGENTS; удаление из tools/tests покрывается W89-29.
  **Deps:** -

- [x] **W89-4** `backlog.md`:
  - удалить закрытые/исторические волны из `backlog.md` (без архивирования);
  - оставить только активные и актуальные задачи.
  **AC:** в `backlog.md` нет закрытых волн; файл содержит только активные/актуальные волны.
  **Deps:** W89-1, W89-2, W89-3

- [x] **W89-5** `README.md`, `README.en.md`, `AGENTS.md`, `templates/aidd/AGENTS.md`, `templates/aidd/docs/**/README.md`:
  - runtime‑документация не содержит README: удалить все `templates/aidd/docs/**/README.md`;
  - все runtime‑правила держать в `AGENTS.md`/`templates/aidd/AGENTS.md` + `templates/aidd/docs/prompting/conventions.md`;
  - root `README.md`/`README.en.md` остаются human‑доками без agent‑policy.
  **AC:** в `templates/aidd/docs/**` нет README файлов; runtime‑правила есть только в `AGENTS.md` и `docs/prompting/conventions.md`.
  **Deps:** W89-1, W89-2, W89-3

- [x] **W89-6** `AGENTS.md`, `templates/aidd/AGENTS.md`, `commands/*.md`, `agents/*.md`, `tests/repo_tools/*`:
  - использовать только `AGENTS.md` как runtime‑guidance (без `CLAUDE.md`);
  - удалить любые упоминания `CLAUDE.md` из команд/агентов/доков/тестов;
  - `aidd-init` не создаёт и не обновляет `CLAUDE.md`.
  **AC:** в репозитории нет упоминаний `CLAUDE.md`; runtime‑правила описаны только через `AGENTS.md`.
  **Deps:** W89-1, W89-5

- [x] **W89-7** `templates/aidd/docs/prompting/conventions.md`, `templates/aidd/docs/prompting/examples/*`, `commands/*.md`, `agents/*.md`:
  - Добавить few-shot “канонические примеры” (минимум 3) и закрепить их как эталон:
    1) implementer: `READY|WARN` + `Tests` + `AIDD:READ_LOG` + ссылки на `aidd/reports/**`
    2) reviewer: `REVISE` + findings + **Fix Plan** (структурированный) + ссылки
    3) qa: `WARN` (soft missing evidence) + handoff + traceability
  - Требования к примерам:
    - укладываются в budgets (TL;DR/Blockers/NEXT_3 и т.п.);
    - не содержат логов/диффов/стектрейсов, только ссылки;
    - используют обязательные поля output‑контракта (из W88-11).
  - В `conventions.md` добавить ссылку “смотри examples/* как эталон”.
  **AC:**
  - Примеры добавлены и явно указаны как эталон в каноне.
  - Команды/агенты ссылаются на эти примеры (минимум в conventions.md).
  **Deps:** W89-2, W88-11

- [x] **W89-8** `README.md`, `README.en.md`, `AGENTS.md`, `templates/aidd/AGENTS.md`, `commands/*.md`, `agents/*.md`, `templates/aidd/docs/**`:
  - финальный sweep ссылок после консолидации + добавления examples:
    - проверить, что все упоминания конвенций/examples ведут в канон;
    - убедиться, что нигде не осталось путей на удалённые файлы;
    - обновить краткие описания/линки.
  **AC:** в документации нет устаревших путей; все упоминания ведут на канонические файлы; examples интегрированы ссылками.
  **Deps:** W89-1, W89-2, W89-3, W89-4, W89-5, W89-6, W89-7

- [x] **W89-9** `commands/*.md`, `agents/*.md`, `templates/aidd/docs/prompting/conventions.md`:
  - зафиксировать pack‑first как единственную политику чтения;
  - ввести read‑budget (1–3 файла) и правило “полный документ только при missing fields в pack”;
  - добавить обязательный `AIDD:READ_LOG` в pack и отразить его как обязательный в output‑контракте.
  **AC:** команды/агенты следуют pack‑first; read‑budget описан и используется в examples; `AIDD:READ_LOG` обязателен.

- [x] **W89-10** `tools/context_pack.py`, `tools/context-pack.sh`, `templates/aidd/reports/context/template.context-pack.md`, `commands/*.md`:
  - перейти на единый rolling pack `aidd/reports/context/<ticket>.pack.md`;
  - включить поля `stage`, `agent`, `read_next`, `artefact_links`;
  - удалить поддержку stage‑packs.
  **AC:** rolling pack — единственный формат; stage‑packs отсутствуют.

- [x] **W89-11** `tools/set_active_feature.py`, `tools/set_active_stage.py`, `tools/feature_ids.py`, `tools/index_sync.py`, `tools/status.py`:
  - заменить `.active_*` на `aidd/docs/.active.json`;
  - удалить поддержку старых `.active_*`.
  **AC:** только один файл активных маркеров; фолбэков нет.

- [x] **W89-12** `tools/tasklist_check.py`, `commands/implement.md`, `commands/review.md`, `commands/qa.md`:
  - кешировать hash tasklist (`aidd/.cache/tasklist.hash`);
  - `tasklist-check` вызывается только при изменении hash или смене стадии.
  **AC:** tasklist‑check пропускается при неизменённом tasklist.

- [x] **W89-13** `hooks/context_gc/*.py`, `hooks/context-gc-*.sh`, `templates/aidd/config/context_gc.json`:
  - добавить режим `light` по умолчанию;
  - `pretooluse` запускается только при изменении `aidd/**`;
  - env `AIDD_CONTEXT_GC=full|light|off`.
  **AC:** pretooluse GC не выполняется на каждом tool call.

- [x] **W89-14** `hooks/*.sh`, `hooks/hooks.json`, `tools/gates.py`, `templates/aidd/config/gates.json`:
  - добавить fast‑hooks (`AIDD_HOOKS_MODE=fast`);
  - `lint-deps` в fast‑mode → no‑op;
  - тестовая политика стадий (implement/review/qa) остается обязательной и определяется W89-19.
  **AC:** fast‑mode сокращает стоп‑хуки, не ослабляя обязательную политику тестов по стадиям.

- [x] **W89-15** `tools/gate_workflow.py`, `tools/stage_result.py`, `hooks/gate-workflow.sh`, `templates/aidd/config/gates.json`:
  - добавить `fast_mode` gating:
    - allow implement при PRD+Tasklist READY без review‑spec (WARN);
    - diff boundary OUT_OF_SCOPE → WARN + auto‑extend, BLOCKED только FORBIDDEN.
  **AC:** fast‑mode отражается через `reason_code=fast_mode_warn` и в status_summary.

- [x] **W89-16** `tests/*`, `tests/repo_tools/*`:
  - обновить тесты под rolling pack, `.active.json`, отсутствие anchors, pack‑first policy;
  - добавить регресcии для fast hooks и light context GC.
  **AC:** CI проходит; тесты не ссылаются на anchors; pack‑first/rolling‑pack покрыт.

- [x] **W89-17** `templates/aidd/**`, `commands/*.md`, `agents/*.md`, `AGENTS.md`:
  - удалить любые fallback/legacy/migration‑инструкции из runtime‑доков и промптов;
  - не оставлять ветки “если старые артефакты существуют” — обратная совместимость не поддерживается.
  **AC:** `rg -n "(fallback|legacy|migration|compat|обратн.*совмест)" templates/aidd commands agents AGENTS.md` не находит совпадений.

- [x] **W89-18** `templates/aidd/**`, `commands/*.md`, `agents/*.md`, `AGENTS.md`, `README*.md`, `tests/*`, `tools/*`:
  - вычистить неактуальные/депрекейтнутые упоминания, артефакты и логику (deprecated, obsolete, removed, legacy и т.п.);
  - удалить ссылки на несуществующие команды/агенты/артефакты;
  - удалить “мертвые” секции в шаблонах, которые больше не используются в текущем флоу.
  **AC:** `rg -n "(deprecated|obsolete|removed|legacy|unused|мертв|устарев)" templates/aidd commands agents AGENTS.md README* tests tools` не находит совпадений; нет ссылок на несуществующие артефакты.

- [x] **W89-19** `hooks/format-and-test.sh`, `hooks/gate-tests.sh`, `hooks/gate-qa.sh`, `tools/gates.py`, `templates/aidd/config/gates.json`, `commands/implement.md`, `commands/review.md`, `commands/qa.md`, `agents/*.md`, `templates/aidd/docs/prompting/conventions.md`, `tests/*`:
  - упростить политику тестов по стадиям:
    - **implement:** тесты запрещены (no tests); format-only допускается;
    - **review:** только compile + точечные тесты по только что изменённому коду (targeted);
    - **qa:** полный тестовый прогон (full);
  - если QA тесты падают — обязательный возврат в цикл `implement → review → implement` до зелёного QA, даже если падение не связано с текущими изменениями;
  - обновить гейты/хуки, чтобы enforce логика стадий и запретить “лишние” тесты вне своей стадии.
  **AC:** implement не запускает тесты; review запускает только compile/targeted; qa запускает full; падение qa всегда приводит к возврату в implement/review loop.

- [x] **W89-20** `hooks/hooks.json`, `hooks/*.sh`, `hooks/hooklib.py`, `tools/gates.py`, `templates/aidd/config/gates.json`, `tests/*`:
  - выполнить stage‑scoped запуск стоп‑хуков:
    - `gate-qa` только при `stage=qa` (или изменении `aidd/reports/qa/<ticket>.json`);
    - `gate-tests` только при `stage=review|qa` или при code‑changes;
    - `lint-deps` только при изменении зависимостей (allowlist файлов).
  **AC:** Stop/SubagentStop не запускает лишние гейты вне своей стадии; документы/metadata не триггерят gate‑tests/lint‑deps; тесты обновлены.
  **Deps:** W89-14

- [x] **W89-21** `tools/gates.py`, `hooks/hooklib.py`, `templates/aidd/config/gates.json`, `AGENTS.md`, `templates/aidd/AGENTS.md`, `templates/aidd/docs/prompting/conventions.md`, `tests/*`:
  - сделать fast‑mode значением по умолчанию при отсутствии `AIDD_HOOKS_MODE`;
  - strict‑mode активируется только явным `AIDD_HOOKS_MODE=strict`.
  **AC:** поведение без env соответствует fast‑mode; strict включается только явно; тесты фиксируют дефолт.
  **Deps:** W89-14

- [x] **W89-22** `tools/diff_boundary_check.py`, `tools/prd_check.py`, `tools/prd-check.sh`, `tools/diff-boundary-check.sh`, `tests/*`:
  - добавить кеш‑skip для повторных проверок:
    - `aidd/.cache/diff-boundary.hash` (diff/allowed_paths);
    - `aidd/.cache/prd-check.hash` (PRD status + ключевые секции);
  - при совпадении hash — skip с явным логом `reason_code=cache_hit`.
  **AC:** повторные прогоны при неизменённом входе пропускаются; лог фиксирует cache‑hit; тесты покрывают.
  **Deps:** W89-9

- [x] **W89-23** `hooks/format-and-test.sh`, `hooks/gate-tests.sh`, `tools/gates.py`, `templates/aidd/config/gates.json`, `tests/*`:
  - docs‑only shortcut:
    - если изменения только в `aidd/**`/docs → `format-and-test` не запускается (полный no‑op);
    - при запуске `gate-tests` и `tests_required=soft` → `WARN` (не `BLOCKED`).
  **AC:** doc‑итерации не запускают тесты; при `tests_required=soft` нет блокировок; тесты обновлены.
  **Deps:** W89-19

- [x] **W89-24** `README.md`, `README.en.md`:
  - обновить root README под pack‑first/rolling‑pack и fast‑hooks;
  - убрать ссылки на удалённые артефакты (anchors/architecture/ast-grep) после W89-1/2/3/5/8;
  - уточнить краткий быстрый старт (идея → research → plan → review-spec → tasklist → implement → review → qa) с упоминанием fast‑mode.
  **AC:** README не содержит устаревших ссылок; pack‑first/fast‑mode явно описаны; quick‑start соответствует текущему флоу.
  **Deps:** W89-1, W89-2, W89-3, W89-5, W89-8, W89-9, W89-10, W89-14

- [x] **W89-25** `aidd_test_flow_prompt_ralph_script.txt`:
  - синхронизировать скрипт тестового прогона с pack‑first/rolling‑pack, fast‑hooks и новой политикой тестов;
  - удалить упоминания anchors/architecture/ast‑grep/context/targets (после W89-1/2/3/10);
  - обновить список must‑read до минимального канона (AGENTS + prompting conventions + loop pack template + tasklist).
  **AC:** скрипт не ссылается на удалённые артефакты; отражает rolling‑pack и fast‑mode; тест‑политика соответствует W89-19.
  **Deps:** W89-1, W89-2, W89-3, W89-9, W89-10, W89-14, W89-19

- [x] **W89-26** `tools/*.py`, `hooks/*.sh`, `hooks/context_gc/*.py`, `tests/*`, `tests/repo_tools/*`:
  - провести ревью Python‑скриптов (tools/hooks) на соответствие новому флоу;
  - убрать дубли, неиспользуемые ветки и legacy‑поддержку;
  - упростить кодовые пути, минимизировать IO/чтения, но сохранить требования качества (gates/tests/outputs).
  **AC:** удалены неиспользуемые/legacy‑ветки; hot‑path упрощён; поведение гейтов/тестов/выходов не деградирует; регрессии обновлены.
  **Deps:** W89-1, W89-2, W89-3, W89-9, W89-10, W89-11, W89-14, W89-18, W89-19

- [x] **W89-27** `tools/arch_profile_validate.py`, `tools/arch-profile-validate.sh`, `tools/init.py`, `tools/loop_pack.py`, `tests/repo_tools/ci-lint.sh`, `tests/*`:
  - убрать все упоминания `architecture/profile.md` и `arch_profile` из tools/CI;
  - удалить валидатор arch_profile и любые вызовы в CI;
  - удалить поле `arch_profile` из loop pack front‑matter.
  **AC:** нет ссылок на `arch_profile` в tools/CI/loop pack; `rg -n "arch_profile|architecture/profile" tools tests` пусто; тесты обновлены.
  **Deps:** W89-1

- [x] **W89-28** `tools/context_pack.py`, `tools/context-pack.sh`, `hooks/context_gc/working_set_builder.py`, `tools/prompt_template_sync.py`, `tests/*`:
  - убрать anchor‑экстракцию и зависимости от `docs/anchors/**`;
  - перевести context pack на template‑only/rolling pack;
  - working‑set builder читает только rolling pack + tasklist summary.
  **AC:** anchors не читаются; context pack строится только по шаблону; working‑set не читает PRD/Plan/Research целиком; тесты обновлены.
  **Deps:** W89-2, W89-10

- [x] **W89-29** `tools/research.py`, `tools/reports_pack.py`, `tools/tasks_derive.py`, `tools/ast_grep_scan.py`, `tools/gate_workflow.py`, `tests/*`:
  - полностью удалить поддержку ast‑grep (scan/pack/derive/guards);
  - убрать связанные предупреждения и INSTALL_HINT;
  - обновить research/gates/tests под RLM‑only.
  **AC:** ast‑grep не упоминается в tools; research/gates работают без ast‑grep; тесты обновлены.
  **Deps:** W89-3

- [x] **W89-30** `tools/stage_result.py`, `tools/tasklist_check.py`, `tools/index_sync.py`, `hooks/context_gc/working_set_builder.py`, `tests/*`:
  - адаптировать проверки/summary под rolling pack (`aidd/reports/context/<ticket>.pack.md`) и новые поля (`stage/agent/read_next/artefact_links`);
  - убрать зависимости от stage‑packs (`<ticket>.<stage>.pack.md`).
  **AC:** stage‑packs не используются; stage_result/tasklist_check/index_sync читают rolling pack; тесты обновлены.
  **Deps:** W89-10

- [x] **W89-31** `tools/runtime.py`, `tools/loop_pack.py`, `tools/loop_step.py`, `tools/diff_boundary_check.py`, `tools/review_pack.py`, `hooks/hooklib.py`, `tests/*`:
  - перейти на единый `aidd/docs/.active.json` (ticket/slug/stage/work_item);
  - удалить поддержку `.active_ticket/.active_feature/.active_stage/.active_work_item`;
  - обновить оставшиеся чтения/записи активных маркеров в tools/hooks (кроме core‑writer из W89-11).
  **AC:** активные маркеры хранятся только в `.active.json`; старые файлы не читаются/не пишутся; тесты обновлены.
  **Deps:** W89-11

- [x] **W89-32** `hooks/context_gc/*.py`, `tools/reports/loader.py`, `tools/reports_pack.py`, `tests/*`:
  - минимизировать I/O в context GC и reports loader:
    - не читать PRD/Research/Plan целиком;
    - использовать rolling pack и краткие excerpts из tasklist.
  **AC:** контекст‑GC читает <=2 файла (pack + tasklist); нет чтений полноразмерных документов; тесты обновлены.
  **Deps:** W89-9, W89-10, W89-13

- [x] **W89-33** `commands/*.md`, `agents/*.md`, `templates/aidd/**`:
  - провести вычитку команд/агентов/шаблонов от legacy‑логики и устаревших веток;
  - убрать любые “если есть старые артефакты/фолбэки/миграции” из инструкций;
  - сократить шаги до pack‑first/read‑budget/rolling‑pack и актуальных гейтов.
  **AC:** в commands/agents/templates отсутствуют legacy‑ветки; инструкции краткие и соответствуют новому канону; тесты/линтеры промптов проходят.
  **Deps:** W89-9, W89-10, W89-17, W89-18

## Wave 89.5 — AIDD Flow Audit fixes (Ralph loop compliance + QA/tests)

_Статус: новый, приоритет 1. Закрывает выявленные проблемы аудита флоу/loop-паков и тест‑evidence._

- [ ] **W89.5-1** `tools/research_guard.py`, `tools/research.py`, `tools/reports_pack.py`, `tests/*`:
  - при `rlm.require_links=true` и `links_total=0` (или entries=0) — выставлять WARN (не reviewed/ready), reason_code `rlm_links_empty_warn`;
  - в research отчёте фиксировать отсутствие links и ссылаться на `*-rlm.links.stats.json`/pack;
  - гейт не должен считать research “ready” при пустых links.
  **AC:** пустые links → WARN + reason_code; research не может быть READY; tests обновлены.
  **Deps:** -

- [ ] **W89.5-2** `agents/reviewer.md`, `commands/review.md`, `hooks/review-report.sh`, `tools/review_report.py`, `tests/*`:
  - унифицировать вывод findings: reviewer пишет JSON (AIDD:WRITE_JSON), `review-report.sh` читает через `--findings-file`;
  - гарантировать генерацию `review.latest.pack.md` и review report per scope_key;
  - при REVISE обязателен `review.fix_plan.json` + ссылка в `stage_result.evidence_links.fix_plan_json`;
  - при ошибке записи report/pack → явный BLOCKED (reason_code `review_report_write_failed`).
  **AC:** report + pack всегда создаются; REVISE всегда пишет fix_plan + ссылку; tests обновлены.
  **Deps:** -

- [ ] **W89.5-3** `tools/review_report.py`, `tools/stage_result.py`, `tests/*`:
  - если `tests_required=soft|hard` и tests skipped/no‑evidence → review verdict `REVISE`/`BLOCKED` соответственно;
  - reason_code должен отражать no-tests (`no_tests_soft|no_tests_hard`);
  - `stage_result.evidence_links.tests_log` обязателен и указывает на tests log.
  **AC:** soft → REVISE, hard → BLOCKED; reason_code корректный; tests_log всегда в evidence_links; tests обновлены.
  **Deps:** -

- [ ] **W89.5-4** `tools/qa.py`, `tools/tasklist_parse.py` (или эквивалент), `tests/*`:
  - извлекать `AIDD:TEST_EXECUTION` из tasklist и использовать как набор QA‑команд (если profile != none);
  - расширить skip‑детекцию (RU/EN фразы) и всегда писать tests_log (run|skipped + reason_code);
  - при skipped tests_summary не может быть `pass` (должно быть warn/skip).
  **AC:** QA использует тест‑команды из tasklist; skipped корректно распознаётся; tests_summary корректен; tests_log обязателен; tests обновлены.
  **Deps:** -

- [ ] **W89.5-5** `tools/context_pack.py`, `tools/context-pack.sh`, `commands/implement.md`, `commands/review.md`, `commands/qa.md`, `tests/*`:
  - добавить CLI‑поля `read_next/what_to_do/artefact_links` и заполнение вместо placeholder‑строк;
  - команды implement/review/qa передают значения из артефактов;
  - если заполнить нельзя — выставлять WARN (placeholder не допускается молча).
  **AC:** rolling pack без placeholder‑строк; при missing values — WARN; tests обновлены.
  **Deps:** -

- [ ] **W89.5-6** `tools/loop_pack.py`, `tools/diff_boundary_check.py`, `tests/*`:
  - если Boundaries пусты — fallback к Expected paths (tasklist), затем allowed_paths (rolling pack);
  - при авто‑расширении выставлять WARN (`auto_boundary_extend_warn`), не BLOCKED.
  **AC:** loop pack всегда содержит границы; авто‑расширение даёт WARN; tests обновлены.
  **Deps:** -

- [ ] **W89.5-7** `tools/tasklist_check.py`, `tests/*`:
  - добавить проверку консистентности: progress log отмечен done, а checkbox `[ ]` не установлен;
  - выводить WARN с указанием work_item_key (без авто‑фикса).
  **AC:** несоответствие лог/checkbox даёт WARN; не происходит авто‑изменений; tests обновлены.
  **Deps:** -

- [ ] **W89.5-8** `tools/output_contract.py` (новый) или `tools/runtime.py`, `tests/*`:
  - валидация output‑контракта для implement/review/qa (Status/Work item/Tests/AIDD:READ_LOG/Next actions);
  - WARN при неполных полях, с reason_code `output_contract_warn`.
  **AC:** неполный вывод детектируется как WARN; причина отражена в stage_result; tests обновлены.
  **Deps:** -

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

## Wave 91 — Skill-first prompts (канон в skills, короткие entrypoints)

_Статус: новый, приоритет 1. Цель — вынести канон из команд/агентов в skills, сократить промпты и перевести stage entrypoints на skills._

- [ ] **W91-1** `skills/aidd-core/**`, `skills/aidd-loop/**`, `skills/aidd-reference/**` (опционально):
  - создать `skills/aidd-core/SKILL.md` (контекст‑преференс, pack‑first/read‑budget, `AIDD:READ_LOG`, output‑контракт, формат вопросов, запрет на `.active.json`);
  - создать `skills/aidd-loop/SKILL.md` (loop discipline, test policy, out‑of‑scope/REVISE правила);
  - для `aidd-core` и `aidd-loop`: `disable-model-invocation: true` + `user-invocable: false` (скрыть из /‑меню; preload в subagents остаётся);
  - для `aidd-reference` (если используется): по умолчанию `disable-model-invocation: true`, `user-invocable: false` (вручной вызов при необходимости);
  - длинные справочники вынести в отдельный **non‑preloaded** skill (`skills/aidd-reference/**`) или в docs; core/loop держать минимальными;
  - supporting files допускаются только на **один уровень глубины** (SKILL.md → DETAILS/REFERENCE, без цепочек).
  **AC:** `skills/aidd-core` и `skills/aidd-loop` существуют; `SKILL.md` ≤ 250–300 строк; **общий размер директории** (SKILL + supporting files) ограничен (например ≤ 400 строк суммарно или ≤ 60KB); длинные справочники вынесены в non‑preloaded skill/доки; `description` у preloaded skills ≤ 1–2 строки; supporting files не глубже 1 уровня.
  **Deps:** -

- [ ] **W91-2** `agents/*.md`:
  - добавить `skills:` preload (минимум `feature-dev-aidd:aidd-core`; для loop‑агентов — также `feature-dev-aidd:aidd-loop`);
  - удалить дубли канона (context precedence/read policy/output contract/loop discipline) из агентов, оставить только роль‑/стадия‑специфику;
  - оставить короткий якорь: “Output follows aidd-core skill”.
  **AC:** все агенты preload‑ят core/loop skills по роли; повторяющиеся блоки канона удалены; роли остаются исполнимыми; есть smoke‑проверка, что skills реально подхватились (front‑matter `skills:` содержит нужные значения или compiled‑prompt check).
  **Deps:** W91-1

- [ ] **W91-3** `skills/<stage>/**`, `commands/*.md`:
  - создать stage skills: `aidd-init`, `idea-new`, `researcher`, `plan-new`, `review-spec`, `spec-interview`, `tasks-new`, `implement`, `review`, `qa`, `status`;
  - перенести “исполняемый алгоритм” в `SKILL.md` (кратко), длинные справочные блоки — в `DETAILS.md`/`CHECKLIST.md`;
  - перенести `allowed-tools` из `commands/*.md` в `skills/<stage>/SKILL.md`;
  - перенести `argument-hint`, `model: inherit`, `prompt_version`, `source_version` из `commands/*.md` в `skills/<stage>/SKILL.md`;
  - проставить `disable-model-invocation: true` для side‑effects (init/idea/research/plan/review‑spec/spec‑interview/tasks/implement/review/qa); для `status` оставить `disable-model-invocation: false`; `user-invocable` выставить по смыслу (core/loop/reference = false).
  - команды либо превращаются в короткие wrappers, либо переносятся в `docs/legacy/commands/` (без авто‑сканирования).
  **AC:** каждый stage имеет `skills/<stage>/SKILL.md` ≤ 250–400 строк; side‑effect skills помечены `disable-model-invocation: true`; **нет stage‑entrypoints в `commands/`** после миграции; нет больших канон‑дублей.
  **Deps:** W91-1

- [ ] **W91-3.0** `commands/`, `skills/**`:
  - name collision check: после добавления stage skills убедиться, что в `commands/` нет файлов с теми же `/feature-dev-aidd:<stage>`;
  - `commands/` либо удалён/переименован, либо очищен от stage entrypoints (иначе дубли).
  **AC:** каждый `/feature-dev-aidd:<stage>` определяется ровно один раз (skill‑first).
  **Deps:** W91-3

- [ ] **W91-4** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`:
  - зарегистрировать `skills` в плагине; обновить список entrypoints (skills vs commands);
  - сохранить совместимость `/feature-dev-aidd:<stage>` (без дублей/конфликтов);
  - при user‑facing изменениях обновить версии и `CHANGELOG.md`.
  **AC:** plugin.json содержит `skills`; entrypoints доступны; версии/CHANGELOG синхронизированы при необходимости.
  **Deps:** W91-3.0

- [ ] **W91-5** `tests/repo_tools/*`, `tools/prompt_template_sync.py`, `tests/test_gate_workflow.py`:
  - адаптировать lint/regression под `skills/**` (section titles, output‑contract checks, prompt‑version bump);
  - обновить `prompt_template_sync.py` и тесты, которые ожидают `commands/`/`agents/` пути;
  - добавить guard “SKILL.md ≤ N lines” и **guard на общий размер preloaded skill‑директории**; проверку `disable-model-invocation` для side‑effects;
  - добавить guard на обязательные front‑matter поля для skills (`description`, `lang`, `prompt_version`, `source_version`, `model`);
  - добавить guard: `description` у stage skills ≤ 1–2 строки;
  - добавить тест на отсутствие stage‑entrypoints в `commands/` после миграции;
  - добавить guard “supporting files ≤ 1 уровень глубины” для `.md` supporting docs (подпапки типа `scripts/` допускаются).
  **AC:** `tests/repo_tools/ci-lint.sh` проходит; lint/regression учитывают skills; новые guards (line + dir size + depth) работают; тест на отсутствие stage‑commands проходит.
  **Deps:** W91-3.0, W91-4

- [ ] **W91-6** `templates/aidd/AGENTS.md`, `templates/aidd/docs/prompting/conventions.md`, `README*.md`, `aidd_test_flow_prompt_ralph_script.txt`:
  - синхронизировать канон с skill‑first подходом (короткие ссылки на skills вместо дублей);
  - обновить примеры/доки, чтобы отражали новые entrypoints и структуру skills;
  - проверить bootstrap (`/feature-dev-aidd:aidd-init`) и smoke‑workflow.
  **AC:** шаблоны и README соответствуют skill‑first; bootstrap и smoke проходят.
  **Deps:** W91-2, W91-3, W91-5

## Wave 92 — Skill‑local scripts + tool proximity (wrappers + shims)

_Статус: новый, приоритет 2. Цель — приблизить исполняемую логику к skills без поломки runtime: stage‑локальные wrapper‑скрипты и аккуратные shims для tool‑миграции._

- [ ] **W92-1** `skills/<stage>/scripts/*`:
  - инвентаризировать `tools/*.sh` и их вызовы (commands/agents/hooks/tests) → **сформировать отчёт** `aidd/reports/tools/tools-inventory.{md,json}` (script → consumers);
  - добавить генератор отчёта `tools/tools-inventory.sh` (или `tools/tools_inventory.py` + `.sh` entrypoint);
  - добавить `templates/aidd/reports/tools/.gitkeep` для каталога отчётов;
  - зафиксировать **wrapper‑контракт**: аргументы `--ticket` (обяз.), `--stage` (опц.), `--scope-key` (опц., иначе вычисляется), summary‑артефакт в `aidd/reports/**`, stdout ≤ 5–20 строк + пути к артефактам;
  - для stage‑локальных шагов создать wrapper‑скрипты в `skills/<stage>/scripts/` (preflight/postflight/bundle);
  - wrapper = orchestration (склеивает существующие tools), не дублирует их логику;
  - в `skills/<stage>/SKILL.md` ссылаться на wrapper‑скрипты вместо длинных списков tool‑вызовов.
  **AC:** у implement/review/qa (минимум) есть wrapper‑скрипты; SKILL.md короче и ссылается на scripts; wrapper‑скрипты пишут summary‑артефакты (например `aidd/reports/<stage>/<ticket>/<scope_key>.wrapper.<name>.{md,json}`) и большие выводы — в `aidd/reports/**`.
  **Deps:** W91-3

- [ ] **W92-2** `tools/*.sh`:
  - определить минимальный набор скриптов, реально переносимых из `tools/` в `skills/<stage>/scripts/` по критериям: **используется только одним stage, не вызывается из hooks/tests**;
  - для перенесённых — оставить shim в `tools/` (проксирование в новый путь) до полной миграции ссылок;
  - shim‑контракт: `exec` 1:1, сохранение exit‑code, deprecation‑notice в stderr (stdout не ломать);
  - обновить ссылки в skills/commands/agents на новый путь (через `${CLAUDE_PLUGIN_ROOT}/skills/<stage>/scripts/...`).
  **AC:** переносимые tool‑скрипты имеют shims; shims используют `exec`, сохраняют exit‑code, пишут notice в stderr; нет разрыва совместимости; ссылки обновлены поэтапно.
  **Deps:** W92-1

- [ ] **W92-3** `tests/repo_tools/*`:
  - добавить guards для `skills/<stage>/scripts/*`:
    - `.sh` обязаны иметь `set -euo pipefail`;
    - stdout ≤ 200 строк (или ≤ 50KB); всё большее — только в `aidd/reports/**` с коротким tail;
    - каждый скрипт упомянут в соответствующем `SKILL.md` **или** `DETAILS.md`;
    - запрет тяжёлых бинарей/данных в `skills/**` (лимиты + список расширений);
    - `#!/usr/bin/env bash` + исполняемый бит для `.sh`.
  **AC:** ci‑lint ловит нарушения; stage skills с scripts проходят guards; stdout/size лимиты соблюдаются.
  **Deps:** W92-1

- [ ] **W92-4** `hooks/hooks.json`, `tests/*`:
  - правило: hooks/CI используют только `tools/*` (или shims), **не** `skills/**`;
  - проверить, что hooks/CI продолжают ссылаться на `tools/*` (или на shims) без изменения поведения;
  - добавить регрессию: в `hooks/**` нет `${CLAUDE_PLUGIN_ROOT}/skills/` и `skills/` в путях вызова.
  - добавить регрессию на shim‑совместимость.
  **AC:** hooks работают без изменений; регрессии подтверждают проксирование.
  **Deps:** W92-2

- [ ] **W92-5** `templates/aidd/docs/prompting/conventions.md`, `README*.md`:
  - документировать правило: “stage‑локальные скрипты живут в `skills/<stage>/scripts/`; shared tooling остаётся в `tools/`”;
  - описать формат wrapper‑скриптов и правила вывода в `aidd/reports/**`;
  - описать shim‑lifecycle (зачем, как устроен, когда удаляется).
  **AC:** документация отражает новую структуру; нет конфликтов с W91.
  **Deps:** W92-1, W92-2, W92-3, W92-4

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
