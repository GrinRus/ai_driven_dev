# AGENTS (Repo development guide)

> INTERNAL/DEV-ONLY: maintainer guide for repository development and release process.

Owner: feature-dev-aidd
Last reviewed: 2026-04-12
Status: active

Этот файл — единая dev‑документация репозитория. Все dev‑правила и шаблоны живут здесь.
User‑гайд для workspace находится в `skills/aidd-core/templates/workspace-agents.md` (копируется в `aidd/AGENTS.md` при init).

## Репозиторий и структура
- Runtime (плагин): `agents/`, `skills/`, `hooks/`, `.claude-plugin/`.
- Workspace bootstrap‑шаблоны: `templates/aidd/` (config/placeholders only; копируются в `./aidd` через `/feature-dev-aidd:aidd-init`).
- Тесты: `tests/`.
- Repo tools: `tests/repo_tools/`.
- Stage runtime entrypoints (canonical): `skills/<stage>/runtime/*.py` (Python-only canon с 2026-02-09).
- Canonical Python runtime живёт в `skills/*/runtime/*`; shell entrypoints допустимы только для hooks/platform glue.
- `tools/*.py` используется только для repo-only tooling/import stubs (если каталог присутствует).
- Backlog: `docs/backlog.md`.
- User‑артефакты: `aidd/**` (`docs/`, `reports/`, `config/`, `.cache/`).
- Derived‑артефакты: `aidd/docs/index/`, `aidd/reports/events/`, `aidd/.cache/`.
- Примеры: демо‑проекты и helper‑скрипты не поставляются — держите их вне плагина и документируйте в workspace.

## Repo tools lifecycle
- `tests/repo_tools/**` делится на `required` (CI/runtime contract), `advisory` (optional diagnostics) и `experimental`.
- `experimental` tooling не считается поддерживаемым surface, пока не появилось в CI, release docs или в явном operator flow.
- Если `experimental` script не получил owner decision за один planning cycle, default policy = archive-candidate, а не бессрочное хранение в активном контуре.
- Архивировать предпочтительнее, чем держать orphaned repo-only utilities в корневом active surface.

## Owner review required before deletion
- `aidd_runtime/**` и другие compatibility bridges.
- Любые `legacy|compat|fallback|shadow` ветки в hooks/runtime/prompts.
- Draft RFCs и roadmap docs (`docs/*-rfc.md`) без явного replacement path.
- Experimental repo tools, которые не подключены к CI, но могут использоваться ad-hoc локально.
- Generated prompt/report outputs, пока CI и release guards ещё читают их напрямую.

## Источник истины (dev vs user)
- Stage content templates (`prd/plan/research/tasklist/spec/loop/context-pack`) — источник истины в `skills/*/templates/*`.
- `templates/aidd/**` — bootstrap source только для config/placeholders/infra-директорий; не хранит stage content templates.
- `aidd/**` появляется в workspace после `/feature-dev-aidd:aidd-init` и не хранится в repo (кроме шаблонов).
- `AGENTS.md` (корень) — dev‑гайд для репозитория; `skills/aidd-core/templates/workspace-agents.md` — user‑гайд для проектов.
- При изменении stage content: обновите `skills/*/templates/*` + `skills/aidd-init/runtime/init.py` seed map; `templates/aidd/**` меняйте только для bootstrap config/placeholders.
- Workspace‑конфиги: `aidd/config/{gates.json,conventions.json,context_gc.json,allowed-deps.txt}` (источник — `templates/aidd/config/`).
- Artifact truth policy lives in `aidd/config/gates.json -> artifact_truth`; default rollout is `soft`.
- Hook wiring: `hooks/hooks.json` — обновляйте при добавлении/удалении хуков.
- Permissions/cadence: `.claude/settings.json` в корне workspace (без `aidd/.claude`).

## Архитектура путей (plugin cache vs workspace)
- Плагин копируется в cache Claude Code: записи в `${CLAUDE_PLUGIN_ROOT}` недопустимы.
- Рабочий root всегда workspace (`./aidd`); только туда пишем `docs/`, `reports/`, `config/`.
- `${CLAUDE_PLUGIN_ROOT}` используется только для чтения ресурсов плагина (hooks/tools/templates).
- CWD хуков не гарантирован; корень проекта вычисляется из payload (cwd/workspace), без опоры на plugin root.
- Wrapper output policy: stdout ≤ 200 lines или ≤ 50KB; stderr ≤ 50 lines; большие выводы пишем в `aidd/reports/**` с кратким summary в stdout.

## Python-only canon (Wave 97)
- Canonical runtime API: `python3 skills/*/runtime/*.py` (с `PYTHONPATH=$CLAUDE_PLUGIN_ROOT` when needed).
- Runtime wrappers в `skills/*/scripts/*.sh` удалены; новые runtime-ссылки на них запрещены.
- Rollback criteria: если migration ломает `tests/repo_tools/ci-lint.sh` или `tests/repo_tools/smoke-workflow.sh` в mainline, допускается временный возврат на wrapper-path для затронутого entrypoint с обязательным follow-up task.

## SKILL authoring policy (cross-agent)
- Source of truth: `docs/agent-skill-best-practices.md` for structure and `docs/skill-language.md` for lint-enforced rules.
- Policy target: compact `SKILL.md` + progressive disclosure via supporting files.
- Shared and stage skills must keep `## Command contracts` with interface cards only: `When to run`, `Inputs`, `Outputs`, `Failure mode`, `Next action`.
- Shared and stage skills must keep `## Additional resources` with `when:` / `why:` markers.
- Stage skills must use explicit `Run subagent` orchestration; `context` and `agent` frontmatter stay forbidden.
- Implementation walkthroughs belong in `references/*`, `templates/*`, or runtime docstrings, not in `SKILL.md`.

## Быстрые проверки (repo‑only)
- Полный линт + unit‑тесты: `tests/repo_tools/ci-lint.sh`.
- E2E smoke: `tests/repo_tools/smoke-workflow.sh`.
- CI policy: workflow `smoke-workflow` запускается всегда и выполняет auto-skip, если не менялись runtime-пути (`skills/**`, `hooks/**`, `agents/**`, `templates/aidd/**`, `.claude-plugin/**`).
- Runtime module guard: `tests/repo_tools/runtime-module-guard.py` (`>600` lines = WARN, `>900` = ERROR), waivers — `tests/repo_tools/runtime-module-guard-waivers.txt`.
- Required-check parity: `lint-and-test`, `smoke-workflow`, `dependency-review`; security checks `security-secret-scan` и `security-sast` идут staged rollout (advisory пока `AIDD_SECURITY_ENFORCE!=1`, required при `AIDD_SECURITY_ENFORCE=1`).
- Дополнительно (если нужно): `python3 -m pytest -q tests`.
- Диагностика окружения: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py`.
- Bootstrap шаблонов (workspace): `/feature-dev-aidd:aidd-init`.

## Минимальные зависимости
- `python3`, `rg`, `git` обязательны.
- Для `tests/repo_tools/ci-lint.sh`: `shellcheck`, `markdownlint`, `yamllint` (иначе warn/skip).

## Локальный запуск entrypoints
- Stage/shared runtime entrypoints (canonical): `CLAUDE_PLUGIN_ROOT=$PWD PYTHONPATH=$PWD python3 skills/<skill>/runtime/<command>.py ...`
- Deferred-core freeze (wave-1) сохраняется как compatibility surface до завершения cutover.
- Хуки: `CLAUDE_PLUGIN_ROOT=$PWD hooks/<hook>.sh ...`

## Shared Ownership Map
- `skills/aidd-core/runtime/*`: shared core runtime API (canonical).
- `skills/aidd-docio/runtime/*`: shared DocIO runtime API (`md_*`, `actions_*`, `context_*`).
- `skills/aidd-flow-state/runtime/*`: shared flow/state runtime API (`set-active-*`, `progress*`, `tasklist*`, `stage_result`, `status_summary`, `prd_check`, `tasks_derive`).
- `skills/aidd-observability/runtime/*`: shared observability runtime API (`doctor`, `tools_inventory`, `tests_log`, `dag_export`, `identifiers`).
- `skills/aidd-policy/SKILL.md` + `skills/aidd-policy/references/*`: shared policy contract (output/question/read/safety).
- `skills/aidd-loop/runtime/*`: shared loop orchestration runtime API (canonical).
- `skills/<stage>/runtime/*`: stage-local runtime API owned by one stage.
- `tools/*.sh` отсутствуют в runtime API.

## Как добавлять entrypoints (skill-first)
1. Stage runtime entrypoint: `skills/<stage>/runtime/<command>.py` (canonical Python path).
2. Shared runtime entrypoints: `skills/aidd-core/runtime/*`, `skills/aidd-docio/runtime/*`, `skills/aidd-flow-state/runtime/*`, `skills/aidd-observability/runtime/*` и `skills/aidd-loop/runtime/*`.
3. Shell wrapper допускается только для hooks/platform-required glue.
4. Не вводите новые `tools/*.sh` и не добавляйте runtime wrappers в `skills/*/scripts/*`.
5. Документация/помпты: обновите `skills/<stage>/SKILL.md` и/или `agents/*.md`, включая `## Command contracts` и `## Additional resources` (with `when/why`). Архив historical команд хранится в каталоге командной документации.
6. Хуки: если entrypoint участвует в workflow, добавьте вызов в `hooks/hooks.json`.
7. Шаблоны: stage content размещайте в `skills/*/templates/*`; `templates/aidd/**` используйте только для bootstrap config/placeholders, затем проверьте `/feature-dev-aidd:aidd-init`.
8. Тесты: unit в `tests/`, repo tooling/CI helpers — в `tests/repo_tools/`.
9. Prompt‑версии: после правок в `skills/`/`agents/` обновите `prompt_version` и прогоните `tests/repo_tools/prompt-version` + `tests/repo_tools/lint-prompts.py`.
10. Метаданные: при user‑facing изменениях обновите `CHANGELOG.md` и версии в `.claude-plugin/plugin.json` + `.claude-plugin/marketplace.json` (если требуется).

Контракт исполнения:
- Subagents (`agents/*.md`) не вызывают shell wrappers напрямую.
- Runtime orchestration должна ссылаться на Python entrypoints (`skills/*/runtime/*.py`).
- Stage orchestration owner: `skills/<stage>/SKILL.md` (через `Run subagent` + stage command routing) является единственным источником orchestration-правил.
- В `agents/*.md` запрещены self-links вида `/feature-dev-aidd:<own-stage>` в `description` и body; агент описывает только роль/scope/handoff.
- Cross-stage handoff ссылки в `agents/*.md` допустимы (например, на следующий stage), если это не self-link.

## Workflow (кратко)
Публичные стадии: `idea → research → plan → review-spec → tasklist → implement → review → qa`.
`review-spec` — umbrella stage с внутренними подстадиями `review-plan` и `review-prd` (см. `skills/aidd-core/templates/stage-lexicon.md`).
Loop policy: `OUT_OF_SCOPE|NO_BOUNDARIES_DEFINED` → WARN + handoff, `FORBIDDEN` → BLOCKED.

Ключевые команды:
- Идея: `/feature-dev-aidd:idea-new <ticket> [note...]` → PRD + `analyst` (`slug_hint` формируется внутри команды из note).
- Research: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket <ticket> --auto` → `/feature-dev-aidd:researcher <ticket>` (RLM targets/manifest/worklist + pack).
- План: `/feature-dev-aidd:plan-new <ticket>`.
- Review‑spec (plan + PRD): `/feature-dev-aidd:review-spec <ticket>`.
- Тасклист: `/feature-dev-aidd:tasks-new <ticket>`.
- Реализация: `/feature-dev-aidd:implement <ticket>` (гейтит `gate-workflow`, auto `format-and-test`).
- Ревью: `/feature-dev-aidd:review <ticket>`.
- QA: `/feature-dev-aidd:qa <ticket>` → отчёт `aidd/reports/qa/<ticket>.json`.

Agent‑first правило: сначала читаем артефакты (`aidd/docs/**`, `aidd/reports/**`), запускаем разрешённые команды (`rg`, `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress_cli.py`, тесты), затем задаём вопросы пользователю.

## RLM в Research
- Evidence: `aidd/reports/research/<ticket>-rlm.pack.json` и `rlm-slice` pack.
- Pipeline: `rlm-targets.json` → `rlm-manifest.json` → `rlm.worklist.pack.json` → агент пишет `rlm.nodes.jsonl` + `rlm.links.jsonl` → `*-rlm.pack.json`.
- On-demand: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py --ticket <ticket> --query "<token>"`.
- Troubleshooting пустого контекста:
  - Уточните `--paths`/`--keywords` (указывайте реальный код, не только `aidd/`).
  - Если `rlm_status=pending` — выполните agent‑flow по worklist и пересоберите pack.

## Migration policy (legacy -> RLM-only)
- Legacy pre-RLM research context/targets artifacts не используются в runtime/gates и могут считаться историческими.
- Для старого workspace состояния пересоберите research canonical командой:
  `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket <ticket> --auto`.
- Если после research `rlm_status=pending`, handoff на shared owner:
  `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py --ticket <ticket>`.
- Гейты стадий `plan/review/qa` требуют минимальный набор RLM evidence:
  `rlm-targets`, `rlm-manifest`, `rlm.worklist.pack`, `rlm.nodes`, `rlm.links`, `rlm.pack`.

## Evidence Read Policy (RLM-first)
- Primary evidence: `aidd/reports/research/<ticket>-rlm.pack.json` (pack-first summary).
- Slice on demand: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py --ticket <ticket> --query "<token>"`.
- Use raw `rg` only for spot-checks.
- JSONL‑streams (`*-rlm.nodes.jsonl`, `*-rlm.links.jsonl`) читаются фрагментами, не целиком.

## Кастомизация (минимум)
- `.claude/settings.json`: permissions и automation/tests cadence (`on_stop|checkpoint|manual`).
- `aidd/config/gates.json`:
  - `prd_review`, `plan_review`, `researcher`, `analyst`
  - `tests_required` (`disabled|soft|hard`), `tests_gate`
  - `deps_allowlist`
  - `qa.debounce_minutes`
  - `qa.tests.discover` (allow_paths/max_files/max_bytes)
  - `tasklist_progress`
- Важные env:
  - `SKIP_AUTO_TESTS`, `SKIP_FORMAT`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`
- Stage-chain orchestration для loop stages обязательна (`preflight -> run -> postflight -> stage_result`), debug bypass не поддерживается.
- `AIDD_TEST_PROFILE`, `AIDD_TEST_PROFILE_DEFAULT`, `AIDD_TEST_TASKS`, `AIDD_TEST_FILTERS`, `AIDD_TEST_FORCE`
- `AIDD_TEST_LOG`, `AIDD_TEST_LOG_TAIL_LINES`, `AIDD_TEST_CHECKPOINT`
- `AIDD_HOOKS_MODE` (`fast` по умолчанию, `strict` для полного набора стоп‑хуков)

## Prompt versioning
- Semver: `MAJOR.MINOR.PATCH`.
- `source_version` always equals `prompt_version` for the canonical EN prompt corpus.
- Skills/agents хранят версии в frontmatter; stage‑skills должны совпадать с baseline.
- Preload matrix v2 (lint-enforced): `aidd-policy` для всех agents, `aidd-rlm` только для `analyst|planner|plan-reviewer|prd-reviewer|researcher|reviewer|tasklist-refiner|validator`, `aidd-stage-research` обязательно для `researcher`, `aidd-loop` только для `implementer|reviewer|qa`. Waivers — `AGENT_PRELOAD_WAIVERS` в `tests/repo_tools/lint-prompts.py`.
- Инструменты:
  - `python3 tests/repo_tools/prompt-version bump --root <workflow-root> --prompts <name> --kind agent|command --lang en --part <major|minor|patch>` (agents + stage skills only)
  - `python3 tests/repo_tools/lint-prompts.py --root <workflow-root>`

## Reports format (MVP)
- Naming:
  - Context pack (rolling): `aidd/reports/context/<ticket>.pack.md`
  - RLM targets: `aidd/reports/research/<ticket>-rlm-targets.json`
  - RLM manifest: `aidd/reports/research/<ticket>-rlm-manifest.json`
  - RLM nodes/links: `aidd/reports/research/<ticket>-rlm.nodes.jsonl`, `*-rlm.links.jsonl`
  - RLM pack: `aidd/reports/research/<ticket>-rlm.pack.json`
  - QA: `aidd/reports/qa/<ticket>.json` + pack
  - PRD review gate artifact: `aidd/reports/prd/<ticket>.json` + pack
  - Reviewer marker: `aidd/reports/reviewer/<ticket>/<scope_key>.json`
  - Tests log: `aidd/reports/tests/<ticket>/<scope_key>.jsonl`
- Pack‑only: читаем `*.pack.json` как источник; JSON хранится как raw‑артефакт и не используется для чтения.
- Tasklist front‑matter uses `ExpectedReports:` only for planned downstream outputs; derived index field `reports` must list only реально существующие files in `aidd/reports/**`.
- Для PRD readiness/recovery source-of-truth — структурный report payload (`status`/`recommended_status`), narrative вывод stage считается вспомогательным.
- Header (минимум): `schema`, `pack_version`, `type`, `kind`, `ticket`, `slug|slug_hint`, `generated_at`, `status`, `summary` (если есть), `tests_summary` (QA), `source_path`.
- Determinism: стабильная сериализация, stable‑truncation, стабильные `id`.
- Columnar формат: `cols` + `rows`.
- Budgets (пример):
  - RLM pack: total <= 12000 chars, entrypoints<=20, hotspots<=20
  - QA pack: findings<=20, tests_executed<=10
  - PRD pack: findings<=20, action_items<=10
- Патчи (опционально): RFC6902 в `aidd/reports/<type>/<ticket>.patch.json`.
- Pack‑only/field filters: `AIDD_PACK_ONLY`, `AIDD_PACK_ALLOW_FIELDS`, `AIDD_PACK_STRIP_FIELDS`.
- Pack‑env: `AIDD_PACK_LIMITS`, `AIDD_PACK_ENFORCE_BUDGET`.

## Release checklist (сжато)
- Обновить `README.md`/`README.en.md`, `AGENTS.md`, `CHANGELOG.md` и при необходимости release notes.
- Закрыть задачи в `docs/backlog.md` и создать следующую волну при необходимости.
- Прогнать `tests/repo_tools/ci-lint.sh` и `tests/repo_tools/smoke-workflow.sh`.
- Для flow-stability релизов дополнительно прогнать matrix: `python3 -m pytest -q tests/repo_tools/test_e2e_prompt_contract.py tests/repo_tools/test_e2e_quality_prompt_contract.py tests/repo_tools/test_aidd_audit_runner.py`.
- Проверить prompt‑versioning/prompt‑lint и убедиться, что dev‑only артефакты не попали в дистрибутив.

## Prompt templates
- Canonical user baseline: `skills/aidd-core/templates/workspace-agents.md`.
- Shared policy source: `skills/aidd-policy/SKILL.md` + `skills/aidd-policy/references/*`.
- Shared runtime topology: `skills/aidd-core`, `skills/aidd-docio`, `skills/aidd-flow-state`, `skills/aidd-observability`, `skills/aidd-loop`, `skills/aidd-rlm`, `skills/aidd-stage-research`.
- Prompt skeletons and lint-required sections live in `docs/skill-language.md`; do not duplicate full templates here.
- Keep `AGENTS.md` as policy index. Move long examples and deep prompt detail into canonical templates, supporting files, or runtime docs.
