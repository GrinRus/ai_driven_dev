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