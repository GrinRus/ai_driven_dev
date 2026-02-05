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
  **Статус (audit 2026-02-05):** FAIL — `*-rlm.links.jsonl` пуст, но research помечен reviewed.
  **Риск:** downstream стадии идут без RLM links‑evidence.

- [ ] **W89.5-2** `agents/reviewer.md`, `commands/review.md`, `hooks/review-report.sh`, `tools/review_report.py`, `tests/*`:
  - унифицировать вывод findings: reviewer пишет JSON (AIDD:WRITE_JSON), `review-report.sh` читает через `--findings-file`;
  - гарантировать генерацию `review.latest.pack.md` и review report per scope_key;
  - при REVISE обязателен `review.fix_plan.json` + ссылка в `stage_result.evidence_links.fix_plan_json`;
  - при ошибке записи report/pack → явный BLOCKED (reason_code `review_report_write_failed`).
  - если `review_pack_v2_required=true`, любой v1 pack → BLOCKED (reason_code `review_pack_v2_required`);
  - findings с severity=blocking должны иметь `blocking=true`, `blocking_findings_count` корректен;
  - reviewer marker `aidd/reports/reviewer/<ticket>/<scope_key>.tests.json` всегда создаётся (включая handoff scope_key вроде `id_review_F*`).
  **AC:** report + pack всегда создаются; REVISE всегда пишет fix_plan + ссылку; blocking_findings_count корректен; reviewer marker всегда есть для всех scope_key; tests обновлены.
  **Deps:** -
  **Статус (audit 2026-02-05):** FAIL — отсутствуют `review.latest.pack.md` и `reviewer/<scope_key>.json`; loop‑run blocked `review_pack_missing`.
  **Риск:** loop‑runner не продвигается после review, автолооп останавливается.

- [ ] **W89.5-3** `tools/review_report.py`, `tools/stage_result.py`, `tests/*`:
  - если `tests_required=soft|hard` и tests skipped/no‑evidence → review verdict `REVISE`/`BLOCKED` соответственно;
  - reason_code должен отражать no-tests (`no_tests_soft|no_tests_hard`);
  - `stage_result.evidence_links.tests_log` обязателен и указывает на tests log.
  - нормализовать `scope_key`/`work_item_key` (не допускать `id_` вместо `iteration_id_`) и писать stage_result в корректный путь;
  - stage_result обязателен для review и должен быть найден loop-run (иначе BLOCKED).
  - WARN‑причины (например `review_context_pack_placeholder_warn`) не должны выставлять `result=blocked`; статус = WARN/REVISE с `result=continue`.
  - `Status` в выводе review должен совпадать со `stage_result.result` (или `status-summary.sh`).
  **AC:** soft → REVISE, hard → BLOCKED; reason_code корректный; tests_log всегда в evidence_links; WARN не превращается в blocked; stage_result путь корректен; tests обновлены.
  **Deps:** -
  **Статус (audit 2026-02-05):** НЕ ПОДТВЕРЖДЕНО — кейсы `no_tests_soft|no_tests_hard` в прогоне не воспроизведены.
  **Риск:** возможен повтор рассинхрона `Status` vs `stage_result` при пропуске тестов в review.

- [ ] **W89.5-4** `tools/qa.py`, `tools/tasklist_parse.py` (или эквивалент), `tests/*`:
  - извлекать `AIDD:TEST_EXECUTION` из tasklist и использовать как набор QA‑команд (если profile != none);
  - расширить skip‑детекцию (RU/EN фразы) и всегда писать tests_log (run|skipped + reason_code);
  - при skipped tests_summary не может быть `pass` (должно быть warn/skip).
  - stage_result для QA обязателен (scope_key=ticket) и reason_code совпадает с QA report (`qa_blocked|qa_warn`).
  - stage.qa.result `evidence_links` должны ссылаться на QA‑логи/qa report, а не loop-step.
  **AC:** QA использует тест‑команды из tasklist; skipped корректно распознаётся; tests_summary корректен; tests_log обязателен; stage_result обязателен; qa evidence links корректные; tests обновлены.
  **Deps:** -
  **Статус (audit 2026-02-05):** PARTIAL — QA берёт команды из tasklist, но tests_log vs stdout расходятся; CWD тестов = `.../aidd`.
  **Риск:** ложные BLOCKED/FAIL в QA, несоответствие evidence.

- [x] **W89.5-5** `tools/context_pack.py`, `tools/context-pack.sh`, `commands/implement.md`, `commands/review.md`, `commands/qa.md`, `tests/*`:
  - добавить CLI‑поля `read_next/what_to_do/artefact_links` и заполнение вместо placeholder‑строк;
  - команды implement/review/qa передают значения из артефактов;
  - если заполнить нельзя — выставлять WARN (placeholder не допускается молча).
  - удалять шаблонную строку типа “Fill stage/agent/read_next/artefact_links…” при генерации context pack (или WARN, если осталась).
  **AC:** rolling pack без placeholder‑строк; при missing values — WARN; шаблонная строка не попадает в pack; tests обновлены.
  **Deps:** -
  **Статус (audit 2026-02-05):** PASS — placeholder‑строк в context pack не обнаружено, read_next/artefact_links заполнены.

- [x] **W89.5-6** `tools/loop_pack.py`, `tools/diff_boundary_check.py`, `tests/*`:
  - если Boundaries пусты — fallback к Expected paths (tasklist), затем allowed_paths (rolling pack);
  - при авто‑расширении выставлять WARN (`auto_boundary_extend_warn`), не BLOCKED.
  - OUT_OF_SCOPE|NO_BOUNDARIES_DEFINED → WARN + reason_code `out_of_scope_warn|no_boundaries_defined_warn`;
  - FORBIDDEN → BLOCKED (reason_code `forbidden`).
  - если commands_required явно требует изменения существующего файла — включать его в allowed_paths (или фиксировать WARN с auto‑expand).
  **AC:** loop pack всегда содержит границы; авто‑расширение даёт WARN; commands_required не конфликтует с boundaries; reason_code маппится корректно; tests обновлены.
  **Deps:** -
  **Статус (audit 2026-02-05):** PASS — auto_boundary_extend_warn выставляется, allowed_paths заполнены.

- [x] **W89.5-7** `tools/tasklist_check.py`, `tests/*`:
  - добавить проверку консистентности: progress log отмечен done, а checkbox `[ ]` не установлен;
  - выводить WARN с указанием work_item_key (без авто‑фикса).
  - проверять `AIDD:NEXT_3`: не включает итерации с незакрытыми deps (иначе WARN с указанием deps).
  **AC:** несоответствие лог/checkbox даёт WARN; NEXT_3 не содержит unmet deps или выдаёт WARN; не происходит авто‑изменений; tests обновлены.
  **Deps:** -
  **Статус (audit 2026-02-05):** PASS (по проверке кода/тестов); в e2e прогоне конфликтов не возникало.

- [ ] **W89.5-8** `tools/output_contract.py` (новый) или `tools/runtime.py`, `tests/*`:
  - валидация output‑контракта для implement/review/qa (Status/Work item/Tests/AIDD:READ_LOG/Next actions);
  - WARN при неполных полях, с reason_code `output_contract_warn`.
  - enforce read‑budget: AIDD:READ_LOG максимум 1–3 файла, без полного PRD/Plan/Tasklist при наличии excerpt;
  - enforce read order: implement/review читают `loop pack → review pack (если есть) → rolling pack → excerpt`, qa — rolling pack первым;
  - Status в выводе должен совпадать со `stage_result` (иначе WARN).
  - фиксировать WARN, если `AIDD:READ_LOG` содержит >3 файлов или включает full PRD/Plan/Spec/Tasklist без причины missing fields.
  - `AIDD:READ_LOG` должен содержать только packs/excerpts (код/полные файлы — только при явной причине missing fields).
  **AC:** неполный вывод детектируется как WARN; read‑budget violations фиксируются; read‑order violations фиксируются; Status/`stage_result` совпадают; excessive/full‑read фиксируется; read_log только packs/excerpts; tests обновлены.
  **Deps:** -
  **Статус (audit 2026-02-05):** FAIL — AIDD:READ_LOG содержит >3 файлов и raw‑paths, без WARN.
  **Риск:** нарушения pack‑first проходят незамеченными.

- [ ] **W89.5-9** `tools/loop_run.py` (или эквивалент), `tools/set_active_feature.py`, `tests/*`:
  - после SHIP и при открытых итерациях loop‑runner обязан выбрать следующий work_item, обновить `aidd/docs/.active.json` (work_item/stage) и продолжить implement;
  - завершение loop допустимо только если открытых итераций нет.
  - если выбран следующий work_item — обязателен запуск implement и запись `stage.implement.result.json`; отсутствие файла → BUG + BLOCKED с понятным reason_code и runner_cmd.
  - `review_pack_stale` не должен блокировать loop-run: перегенерировать pack или повторить review с корректным evidence_links.
  **AC:** loop‑runner корректно продвигает active markers после SHIP; loop завершается только при отсутствии итераций; stage_result создаётся для следующего work_item или выдаётся BLOCKED с reason_code; review_pack_stale не блокирует loop-run; tests обновлены.
  **Deps:** -
  **Статус (audit 2026-02-05):** НЕ ПОДТВЕРЖДЕНО — loop‑run блокируется раньше (review_pack_missing).
  **Риск:** автоматический прогон не достигает SHIP/next work_item; stream jsonl пустой.

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

## Wave 91 — Skill‑first prompts (канон в skills, короткие entrypoints)

_Статус: новый, приоритет 1. Цель — вынести канон из команд/агентов в skills, сократить промпты и перевести stage entrypoints на skills._

- [x] **W91-0 (добавить)** Language decision record
  - зафиксировать в одном документе (например, `docs/skill-language.md` или `README.en.md`):
    - `skills/aidd-core`, `skills/aidd-loop`, `skills/<stage>` пишутся на **EN**;
    - user-facing README/шаблоны могут быть RU, без дублирования исполняемых алгоритмов.
  **AC:** есть единый источник истины по языку; правило применяется в W91-1/W91-3.
  **Deps:** —

- [x] **W91-1** `skills/aidd-core/**`, `skills/aidd-loop/**`, `skills/aidd-reference/**` (опц.)
  - создать `skills/aidd-core/SKILL.md`:
    - pack-first/read-budget как политика по умолчанию;
    - `AIDD:READ_LOG` как обязательный output;
    - output‑контракт (Status/Work item key/Artifacts updated/Tests/Blockers/Next actions);
    - DocOps policy (v1, stage‑scoped):
      - loop‑stages (implement/review/qa/status): **запрет** прямого Edit/Write для `aidd/docs/tasklist/**` и `aidd/reports/context/**` (опц. `aidd/docs/.active.json`); LLM пишет только actions/intents;
      - planning‑stages (idea/research/plan/tasks/spec): разрешён прямой Edit/Write для создания/крупных правок; структурные секции (progress/iterations/next3) — через DocOps или не трогать в planning;
    - добавить обязательное поле ответа `AIDD:ACTIONS_LOG: <path>` (обязателен для loop‑stages, `n/a` допустим для planning‑stages);
    - формат вопросов к пользователю;
    - запрет на правку `aidd/docs/.active.json` саб‑агентами;
  - создать `skills/aidd-loop/SKILL.md`:
    - loop discipline, REVISE/out-of-scope, test policy;
  - длинные справочники вынести в **non‑preloaded** `skills/aidd-reference/**` или docs;
  - supporting files только 1 уровень глубины (SKILL → DETAILS/REFERENCE, без цепочек), допускаются подпапки `scripts/`, `examples/`, `assets/` (опц.);
  - frontmatter:
    - `name` (совпадает с именем skill);
    - у preloaded skills `description` ≤ 1–2 строки;
    - `user-invocable: false` для core/loop/reference;
    - для core/loop **не** ставить `disable-model-invocation: true` (preload обеспечивает доступ).
  **AC:**
  - `skills/aidd-core` и `skills/aidd-loop` существуют;
  - core/loop содержат DocOps policy + `AIDD:ACTIONS_LOG` в контракте;
  - `SKILL.md` ≤ 250–300 строк;
  - общий размер директории preloaded‑skill ограничен (например ≤ 60KB или ≤ 400 строк суммарно);
  - supporting files не глубже 1 уровня;
  - reference вынесен отдельно и не preload’ится.
  **Deps:** —

- [x] **W91-2** `agents/*.md`
  - добавить preload skills:
    - минимум `feature-dev-aidd:aidd-core`;
    - для loop‑агентов ещё `feature-dev-aidd:aidd-loop` (только implement/review/qa);
  - удалить дубли канона из агентов, оставить только роль/стадия‑специфику;
  - оставить “якорь”: `Output follows aidd-core skill`.
  **AC:**
  - все агенты preload’ят core/loop по роли;
  - повторяющиеся блоки удалены;
  - добавлен smoke‑чек “skills реально подхватились” (через compiled‑prompt check или анализ frontmatter `skills:`).
  **Deps:** W91-1

- [x] **W91-7 (рекомендуется)** Language policy enforcement
  - добавить мини‑checklist “как писать EN skills” (коротко, imperative, без воды);
  - проверить, что core/loop/stage skills соответствуют EN‑политике из W91‑0.
  **AC:** политика языка соблюдается и зафиксирована в docs/linters.
  **Deps:** W91-0, W91-3

- [x] **W91-3.0** Frontmatter parity baseline (commands → skills)
  - сделать baseline‑отчёт (md+json), фиксирующий для каждого stage:
    - `allowed-tools`, `model`, `prompt_version`, `source_version`, `lang`, `argument-hint`;
    - связь “legacy command → stage skill”.
  - хранить как артефакт (например, `aidd/reports/migrations/commands_to_skills_frontmatter.{md,json}`).
  **AC:** baseline существует и используется для паритетной проверки frontmatter.
  **Deps:** W91-0

- [x] **W91-3** `skills/<stage>/**`
  - создать stage skills: `aidd-init`, `idea-new`, `researcher`, `plan-new`, `review-spec`, `spec-interview`, `tasks-new`, `implement`, `review`, `qa`, `status`;
  - “исполняемый алгоритм” в `SKILL.md` (коротко), детали в `DETAILS.md`/`CHECKLIST.md`;
  - frontmatter (минимальный стандарт):
    - `name` (совпадает с именем stage);
    - `description` 1–2 строки;
    - `argument-hint`;
    - `allowed-tools`, `model: inherit`, `prompt_version`, `source_version`, `lang` — паритет с legacy commands (skills = источник истины);
    - `disable-model-invocation: true` для side-effects (init/idea/research/plan/review-spec/spec-interview/tasks/implement/review/qa);
    - для `status` оставить `disable-model-invocation: false`;
    - `context: fork` + `agent: <role>` только для single‑executor стадий: `idea-new`, `researcher`, `tasks-new`, `implement`, `review`, `qa`; оркестраторы остаются в main context;
    - `user-invocable: true` для stage skills, `false` для core/loop/reference.
  - implement/review/qa обязаны ссылаться на `scripts/preflight.sh` и `scripts/postflight.sh`; для остальных стадий — recommended по мере миграции.
  - implement/review/qa обязаны содержать шаг “Fill actions.json”: заполнить `.../<stage>.actions.json` по шаблону и провалидировать schema перед postflight.
  **AC:**
  - каждый stage имеет `skills/<stage>/SKILL.md` ≤ 250–400 строк;
  - side-effect skills помечены `disable-model-invocation: true`;
  - `context: fork` выставлен для: `idea-new`, `researcher`, `tasks-new`, `implement`, `review`, `qa`;
  - нет больших канон‑дублей в stage skills (только ссылки “следуем aidd-core/aidd-loop”).
  **Deps:** W91-0, W91-1, W91-2, W91-3.0

- [x] **W91-3.1** `commands/`, `docs/legacy/commands/`
  - устранить источники дублей:
    - `commands/` либо удалён/переименован, либо очищен от stage entrypoints;
    - legacy команды (если нужны) перенести в `docs/legacy/commands/` (без автосканирования).
  **AC:** каждый `/feature-dev-aidd:<stage>` определяется ровно один раз (skill‑first); CI/линт ловит дубли имён между skills и commands.
  **Deps:** W91-3

- [x] **W91-4** `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
  - проверить `plugin.json`: если skills лежат в стандартной директории `skills/`, не добавлять лишнего; иначе явно указать пути;
  - обновить entrypoints так, чтобы источником правды были skills;
  - обновить версию/CHANGELOG при user‑facing изменениях; marketplace.json — при публикации/релизе.
  **AC:** plugin.json валиден; skills подхватываются; нет конфликтов/дублей; версии/CHANGELOG синхронизированы при релизе.
  **Deps:** W91-3.1

- [x] **W91-5** `tests/repo_tools/*`, `tools/prompt_template_sync.py`, `tests/test_gate_workflow.py`
  - обновить lint/regression под `skills/**`;
  - добавить guards:
    - `SKILL.md ≤ N lines`;
    - общий размер preloaded skill‑директории ≤ лимита;
    - supporting files ≤ 1 уровень глубины (разрешены `scripts/`, `examples/`, `assets/`);
    - `disable-model-invocation` корректен для side-effects; core/loop без `disable-model-invocation: true`;
    - обязательные frontmatter поля, включая `name`, `allowed-tools`, `model`, `prompt_version`, `source_version`, `lang`.
    - agent/skill parity guard:
      - собрать `agent_ids` из `agents/*.md` (`name:` фронтматтера);
      - если `context: fork` → `agent:` обязателен и входит в `agent_ids`;
      - `context: fork` разрешён только для whitelist стадий (idea-new, researcher, tasks-new, implement, review, qa).
  - добавить тест на отсутствие stage‑entrypoints в `commands/`.
  - зафиксировать entrypoints‑bundle как derived‑артефакт:
    - SoT: `.claude-plugin/plugin.json` + `skills/**/SKILL.md`;
    - генератор: `tools/entrypoints_bundle.py`;
    - `tools/entrypoints-bundle.txt` пересобирается и проверяется в CI (diff‑guard).
  **AC:** `ci-lint.sh` проходит; guards работают; тест “нет stage commands” проходит.
  **Deps:** W91-4

- [x] **W91-6** `templates/aidd/docs/prompting/conventions.md`, `templates/aidd/AGENTS.md`, `README*.md`, `aidd_test_flow_prompt_ralph_script.txt`
  - переписать доки в стиле “skill‑first”: вместо дублей — ссылки на `skills/aidd-core` и `skills/aidd-loop`;
  - smoke‑workflow: bootstrap (`/feature-dev-aidd:aidd-init`) и минимальный loop (tasks → implement → review → qa).
  **AC:** шаблоны/README отражают skill‑first; bootstrap + smoke проходят.
  **Deps:** W91-5

## Wave 92 — Skill‑local scripts + tool proximity

_Статус: новый, приоритет 2. Цель — приблизить исполняемую логику к skills без поломки runtime, сделать wrapper‑интерфейс единым и переносить stage‑специфичные скрипты через shims._

- [x] **W92-0 (добавить)** Wrapper contract (единый интерфейс)
  - определить стандарт вызова для wrapper’ов:
    - вход: `--ticket`, `--scope-key`, `--work-item-key`, `--stage` (или чтение из `.active.json`, но аргументы приоритетнее);
    - вход: `--actions <path>` (actions/intents файл);
    - canonical path для actions:
      - template: `aidd/reports/actions/<ticket>/<scope_key>/<stage>.actions.template.json`
      - actual: `aidd/reports/actions/<ticket>/<scope_key>/<stage>.actions.json`
      - apply log: `aidd/reports/actions/<ticket>/<scope_key>/<stage>.apply.jsonl` (или `.log`)
    - если `--actions` не задан → вычислить canonical path и вывести его в stdout (`actions_path=...`);
    - логи: `aidd/reports/logs/<stage>/<ticket>/<scope_key>/...`;
    - stderr: только важные summary/ошибки;
    - exit code: строго 0/!=0.
  - путь к assets: использовать `${CLAUDE_PLUGIN_ROOT}`; запрещены `../` вне корня плагина;
  - артефакты/логи пишутся в workspace (`aidd/reports/**`), не в plugin root.
  - прямые правки tasklist/context pack запрещены: только DocOps‑скрипты.
  - добавить `templates/aidd/reports/actions/.gitkeep` (+ опц. README).
  **AC:** есть короткий `skills/aidd-reference/wrapper_contract.md` (non-preloaded) + линтер это проверяет.
  **Deps:** W91-1

- [x] **W92-0.1 (добавить)** Actions format v0 (минимальный)
  - определить минимальный формат `aidd.actions.v0`:
    - `schema_version`, `stage`, `ticket`, `scope_key`, `work_item_key`, `actions: []`;
    - базовые types для DocOps (`tasklist_ops.*`, `context_pack_update`).
  - добавить лёгкий валидатор v0 в tools (без полной registry/readmap).
  **AC:** actions v0 валиден; W92‑1 может создавать `actions.template` без зависимости от W93 schemas.
  **Deps:** W91-1

- [x] **W92-1** `skills/<stage>/scripts/*`
  - инвентаризировать `tools/*.sh` и их вызовы (commands/agents/hooks/tests) → отчёт `aidd/reports/tools/tools-inventory.{md,json}` (script → consumers);
  - добавить генератор отчёта (например, `tools/tools-inventory.py` + `.sh` wrapper);
  - добавить `templates/aidd/reports/tools/.gitkeep` для каталога отчётов;
  - для stage‑локальных шагов создать wrapper‑скрипты в `skills/<stage>/scripts/` (preflight/postflight/bundle);
  - в `skills/<stage>/SKILL.md` ссылаться на wrapper’ы вместо длинных списков tool‑вызовов.
  **AC:**
  - у implement/review/qa есть wrapper’ы минимум: `preflight.sh`, `run.sh`, `postflight.sh`;
  - SKILL.md короче и ссылается на scripts;
  - preflight создаёт `.../<stage>.actions.template.json` (пустой, валидный по v0);
  - run.sh/skill‑шаг заполняет `.../<stage>.actions.json` из template (или оставляет валидно пустым) и валидирует schema;
  - postflight применяет actions через DocOps и обновляет документы;
  - postflight пишет apply log `.../<stage>.apply.jsonl`;
  - postflight идемпотентен (повторный запуск не дублирует записи/задачи);
  - wrapper’ы пишут большие выводы в `aidd/reports/**`;
  - wrapper’ы пишут лог в `aidd/reports/logs/<stage>/<ticket>/<scope_key>/wrapper.<name>.<timestamp>.log` и печатают в stdout только путь+summary.
  **Deps:** W91-3

- [x] **W92-2** `tools/*.sh`
  - определить переносимые скрипты по критериям:
    - используется только одним stage;
    - не вызывается из hooks/tests;
    - не является shared tooling по смыслу (оставлять общие инструменты в `tools/`).
  - перенесённым оставить shim в `tools/` (проксирование в новый путь) до полной миграции ссылок;
  - shim‑контракт:
    - `exec` 1:1;
    - сохраняет exit‑code;
    - deprecation‑notice в stderr;
  - обновить ссылки в skills/agents на `${CLAUDE_PLUGIN_ROOT}/skills/<stage>/scripts/...`.
  **AC:**
  - переносимые tool‑скрипты имеют shims;
  - нет разрыва совместимости;
  - миграция ссылок идёт поэтапно (можно катить небольшими PR).
  **Deps:** W92-1

- [x] **W92-3** `tests/repo_tools/*`
  - guards для `skills/<stage>/scripts/*`:
    - `.sh` обязаны иметь `set -euo pipefail`;
    - stdout ≤ 200 lines или ≤ 50KB; всё большее — только в `aidd/reports/**` с коротким tail;
    - stderr ≤ 50 lines (summary/errors);
    - каждый скрипт упомянут в `SKILL.md` или `DETAILS.md`;
    - запрет тяжёлых бинарей/данных в `skills/**`;
    - соответствие wrapper contract из W92-0.
    - `#!/usr/bin/env bash` + executable bit для `.sh`.
  **AC:** ci‑lint ловит нарушения; stage skills со scripts проходят guards.
  **Deps:** W92-0, W92-1

- [x] **W92-4** `hooks/hooks.json`, `tests/*`
  - правило: hooks/CI используют только `tools/*` (или shims), не `skills/**`;
  - проверить, что hooks/CI продолжают ссылаться на `tools/*` (или на shims) без изменения поведения;
  - регрессия: hooks не обращаются напрямую к `skills/**`;
  - регрессия shim‑совместимости (старый путь работает, новый тоже).
  **AC:** hooks работают без изменений; регрессии подтверждают проксирование.
  **Deps:** W92-2

- [x] **W92-5** docs
  - правило: “stage‑локальные скрипты живут в `skills/<stage>/scripts/`; shared tooling остаётся в `tools/`”;
  - формат wrapper‑скриптов и правила вывода в `aidd/reports/**`.
  **AC:** документация отражает структуру; нет конфликтов с W91.
  **Deps:** W92-3

- [x] **W92-6 (добавить)** DocOps toolkit v1 (механические операции)
  - реализовать детерминированные операции над AIDD md‑доками (shared tooling в `tools/`):
    - минимально для implement/review/qa: `tasklist_ops.set_iteration_done`, `tasklist_ops.append_progress_log`, `tasklist_ops.next3_recompute`;
    - `context_pack_ops.context_pack_update`;
    - расширения (handoff_add/frontmatter_set/md_patch) — позже отдельным шагом.
  - wrappers `postflight.sh` используют DocOps вместо прямого Edit;
  - операции валидируются (ошибка schema → stage BLOCKED).
  **AC:** implement/review/qa postflight обновляет tasklist/context pack без LLM Edit; операции идемпотентны.
  **Deps:** W92-1

## Wave 93 — Context discipline 2.0: preflight stage + read/write contracts + progressive disclosure + DAG‑готовность

_Статус: план. Цель — формализовать чтение/запись и контекст, сделать preflight обязательным и подготовить систему к DAG/параллелизму._

- [ ] **W93-0 (добавить)** Schemas: readmap/contract/preflight result
  - определить схемы:
    - `aidd.skill_contract.v1.json` (или YAML schema);
    - `aidd.readmap.v1.json`;
    - `aidd.stage_result.preflight.v1.json` (или расширение текущего stage_result).
    - `aidd.actions.v1.json`;
    - `aidd.writemap.v1.json`.
  - разместить схемы в `tools/schemas/aidd/` (канон); при необходимости создать каталог.
  - legacy schemas (v0) тоже живут в `tools/schemas/aidd/` (например `aidd.actions.v0.schema.json`); валидатор сообщает supported versions.
  - валидатор проверяет schema-version и required поля; CI падает на несовпадении.
  **AC:** схемы существуют; валидатор гоняется в CI.
  **Deps:** W91-3

- [ ] **W93-1** Skill Contract Registry (skill ↔ script ↔ reads/writes)
  - ввести machine‑readable контракт для каждого stage skill:
    - `skills/<stage>/CONTRACT.yaml` (или централизованный `aidd/config/skills.registry.yaml`);
  - поля (минимум):
    - `skill_id`, `stage`, `entrypoints` (wrapper scripts);
    - `reads.required`, `reads.optional` (предпочтительно block‑address: `path.md#AIDD:SECTION`);
    - `writes` (файлы/паттерны);
    - `writes.blocks` (block‑addresses);
    - `writes.via.docops_only: true|false`;
    - `outputs` (артефакты стадий);
    - `gates.before/after` (какие проверки обязательны);
    - `context_budget` (max files/max bytes);
    - `actions.schema: aidd.actions.v1`;
    - `actions.required: true|false`.
  - добавить валидатор `tools/skill_contract_validate.py` + CI‑guard.
  **AC:**
  - у implement/review/qa есть CONTRACT;
  - валидатор гоняется в CI;
  - contracts становятся источником правды для preflight + hooks.
  **Deps:** W93-0, W91-3, W92-1

- [ ] **W93-2** Block addressing + “slice tool” (чтение строго по блокам)
  - формализовать адресацию блоков:
    - `path.md#AIDD:SECTION_NAME` (для `## AIDD:` заголовков);
    - `path.md@handoff:<id>` (для marker‑блоков `<!-- handoff:* -->`);
  - сделать утилиту `tools/md_slice.py` или `tools/md_slice.sh`:
    - извлекает блок по адресу;
    - пишет результат в `aidd/reports/context/slices/...`;
    - возвращает короткий stdout (путь + краткий summary).
  - добавить `tools/md_patch.py` (write‑by‑block) для DocOps.
  - обновить `aidd-core` skill: “читать через slice tool, полный Read — только если slice недостаточен”.
  **AC:**
  - slice tool покрывает оба типа блоков;
  - implement/review используют slice как default;
  - есть тесты на корректность извлечения.
  **Deps:** W91-1

- [ ] **W93-3** Mandatory preflight перед implement/review/qa
  - расширить wrapper’ы `skills/implement/scripts/preflight.sh` (и аналогично review/qa), чтобы preflight:
    1) генерил/обновлял `loop.pack.md` (+ `review.latest.pack.md` если есть);
    2) генерил READ MAP: `aidd/reports/context/<ticket>/<scope_key>.readmap.{md,json}`:
       - required reads (packs + ключевые блоки);
       - optional reads;
       - бюджет (max_files/max_bytes);
       - “если не хватает — делай context-expand”;
    3) генерил WRITE MAP: `aidd/reports/context/<ticket>/<scope_key>.writemap.{md,json}`;
    4) генерил `.../<stage>.actions.template.json` (пустой, валидный, со списком допустимых action types);
    5) генерил “working set” (опционально);
    6) писал `stage.preflight.result.json` (отдельный stage_result).
  - изменить stage skills implement/review/qa: первый шаг = запуск preflight wrapper.
  **AC:**
  - preflight всегда создаёт readmap;
  - preflight всегда создаёт writemap + actions template;
  - implement/review/qa начинают с readmap + pack, а не “сканируют репо”;
  - preflight может упасть “раньше” с понятным BLOCKED.
  **Deps:** W92-0, W92-1, W92-0.1, W93-0, W93-1, W93-2

- [ ] **W93-4** Progressive disclosure: controlled context expansion
  - добавить механизм “расширить контекст” как явное действие:
    - либо отдельный skill `/feature-dev-aidd:context-expand` (с `disable-model-invocation: true`);
    - либо wrapper `skills/aidd-core/scripts/context_expand.sh`;
  - поведение:
    - принимает запрос: `path + reason_code + reason`;
    - дописывает в readmap и/или writemap;
    - по умолчанию расширяет только readmap; расширение writemap/boundaries — отдельный флаг/режим с audit trail;
    - регенерит pack.
  **AC:**
  - любое расширение контекста оставляет след: reason_code + запись в отчёт;
  - implement/review не делают “тихий full-read”, а требуют expansion step.
  **Deps:** W93-3

- [ ] **W93-5** Hard/Soft enforcement через hooks (по AIDD_HOOKS_MODE)
  - расширить guard, чтобы в implement/review/qa:
    - в `fast` режиме: warn/ask при чтении вне readmap/allowed_paths;
    - в `strict` режиме: deny чтение/правки вне readmap/allowed_paths.
  - расширить enforcement на **запись**:
    - `strict`: deny Edit/Write для `aidd/docs/tasklist/**` и `aidd/reports/context/**`, allow только `aidd/reports/actions/**` + DocOps;
    - `fast`: warn + ссылка на DocOps/context-expand write.
  - применение строгого enforcement только для loop‑стадий; planning‑стадии — allow по writemap (или отдельный режим).
  - allowlist по стадиям:
    - planning‑stages: PRD/Plan/Spec/Tasklist — allow по writemap/contract;
    - loop‑stages: прямой Edit/Write tasklist/context pack запрещён (только DocOps/actions).
  - источник истины: `readmap.json` + `writemap.json` + loop pack `allowed_paths`; `aidd/reports/**` и `aidd/reports/actions/**` всегда allow.
  **AC:**
  - в strict реально нельзя “случайно” читать левое;
  - в fast есть заметный warning + ссылка на context-expand.
  **Deps:** W92-6, W93-3, W93-4

- [ ] **W93-6 (опционально, но полезно)** DAG export для параллелизма и “нод”
  - сделать `tools/dag_export.py`:
    - строит DAG по work_item’ам/loop (узлы: preflight → implement → review → qa);
    - в каждый узел кладёт `scope_key`, `allowed_paths`, `readmap`, `writemap`;
    - эвристика конфликтов: пересечение `writemap.allowed_paths` (или loop pack `allowed_paths` до появления writemap) = “не параллелить”.
  - сохранять `aidd/reports/dag/<ticket>.{json,md}`.
  **AC:**
  - есть машинный DAG для ticket;
  - можно в будущем подключить оркестратор/параллельный раннер.
  **Deps:** W93-1, W93-3

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
