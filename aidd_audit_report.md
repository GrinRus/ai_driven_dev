# AIDDIDD Audit Report (2026-02-08)

## 1. Executive summary
- Репозиторий находится в активной миграции на skill-first runtime: `skills/*/scripts/*` и `skills/*/runtime/*` уже основной путь исполнения.
- Главный SoT-конфликт: dev-документация объявляет `templates/aidd/**` единственным источником шаблонов, но runtime bootstrap копирует ключевые шаблоны из `skills/*/templates/*`.
- Второй SoT-конфликт: документация продолжает описывать runtime поверхность с `tools/` и `docs/`, но в рабочем дереве эти директории отсутствуют.
- CI smoke проходит стабильно, но `ci-lint` падает из-за prompt-lint policy/baseline drift (missing policy doc + migration baseline).
- Валидация stage names расходится между stage lexicon, `set_active_stage`, `context_map_validate` и planning guard.
- Практический эффект stage drift: `set-active-stage.sh spec` и `set-active-stage.sh status` завершаются `rc=2`, хотя `context_map_validate` принимает `spec|status|tasks`.
- `hooks/hooks.json` включает полноценный stop-пайплайн (`gate-workflow`, `gate-tests`, `gate-qa`, `format-and-test`, `lint-deps`), но `gate-prd-review.sh` не подключён как hook.
- Инвентарь runtime scripts показывает 115 tracked entrypoints, из них 51 path отсутствует в FS (в основном legacy `tools/*.sh` + старый `context_expand.sh`).
- Stage wrappers в `skills/*/scripts/*.sh` синтаксически корректны (`bash -n`: 44/44), python-runtime скрипты компилируются (`py_compile`: 20/20).
- В skill-модели есть явный контроль `user-invocable`/`disable-model-invocation`, но least-privilege неоднороден: у implement/review/qa очень широкий `allowed-tools`.
- В subagents все preload skills объявлены явно (implicit inheritance не используется), но почти все агенты работают с `permissionMode: default` и без `disallowedTools`.
- Templates слой в `templates/aidd` сейчас mostly skeletal (22 файла, 16 из них `.gitkeep`), что усиливает риск документированного vs фактического SoT.

### Skill/Subagent compliance highlights
- Все `skills/*/SKILL.md` имеют frontmatter delimiters (`bad 0` при проверке).
- Все skill names валидны и совпадают с directory names (`errors 0` при проверке name/description rules).
- Все `context: fork` skills содержат явные `## Steps` с actionable инструкциями.
- Все `agents/*.md` имеют явный `skills:` preload list; missing preload skills не обнаружено.
- `memory`, `maxTurns`, `disallowedTools` в subagents не используются (это и плюс к предсказуемости, и минус к security hardening).

## 2. Repository map & runtime surface

### 2.1 Directory map
| Dir | Role | runtime/dev | Example entrypoints |
|---|---|---|---|
| `agents/` | Subagent prompts | runtime | `agents/implementer.md`, `agents/reviewer.md` |
| `skills/` | Skill prompts + wrappers + runtime modules | runtime | `skills/implement/scripts/preflight.sh`, `skills/aidd-core/runtime/gate_workflow.py` |
| `hooks/` | Hook entrypoints + hook libs | runtime | `hooks/gate-workflow.sh`, `hooks/format-and-test.sh` |
| `.claude-plugin/` | Plugin manifest/marketplace metadata | runtime packaging | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` |
| `templates/aidd/` | Workspace skeleton/config | runtime seed (partial) | `templates/aidd/config/gates.json` |
| `tests/` | Unit + repo tooling guards | dev | `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh` |
| `aidd_runtime/` | Python import package root | runtime | `aidd_runtime/__init__.py` |

### 2.2 Runtime SoT surfaces (as documented vs executed)
- Documented dev SoT:
  - `AGENTS.md:21` — quote: "`templates/aidd/**` — источник истины для workspace-шаблонов".
  - `AGENTS.md:24` — quote: "обновите `templates/aidd/**`, `AGENTS.md`".
- Executed runtime bootstrap SoT:
  - `skills/aidd-init/runtime/init.py:12` defines `SKILL_TEMPLATE_SEEDS`.
  - `skills/aidd-init/runtime/init.py:13` quote: `("skills/aidd-core/templates/workspace-agents.md", "AGENTS.md")`.
  - `skills/aidd-init/runtime/init.py:20` quote: `("skills/tasks-new/templates/tasklist.template.md", "docs/tasklist/template.md")`.
- Hook wiring SoT:
  - `hooks/hooks.json:51` Stop pipeline runs `gate-workflow`, `gate-tests`, `gate-qa`, `format-and-test`, `lint-deps`.
- Packaging SoT:
  - `.claude-plugin/plugin.json:24` lists all shipped skills.
  - `.claude-plugin/plugin.json:11` lists all shipped agents.

## 3. Canonical flow & stage lexicon

### 3.1 Canonical public flow (documented)
- `AGENTS.md:78` — quote: "`idea → research → plan → review-spec → tasklist → implement → review → qa`".
- `README.md:3` includes optional `spec-interview` between `review-spec` and `tasklist`.
- `skills/aidd-core/templates/stage-lexicon.md:22` defines `review-spec` umbrella -> `review-plan` then `review-prd`.

### 3.2 Runtime stage validation (implemented)
- `skills/aidd-core/runtime/set_active_stage.py:10-22` valid stages include `review-spec`, `review-plan`, `review-prd`, `spec-interview`, but **not** `status`, `spec`, `tasks`.
- `skills/aidd-core/runtime/context_map_validate.py:17-32` valid stages include `spec`, `tasks`, `status`.
- `hooks/context_gc/pretooluse_guard.py:150` planning stages include `spec` and `tasks`.

### 3.3 Divergences
| Divergence | Evidence | Runtime behavior by fact | Canonical decision |
|---|---|---|---|
| `status` documented but rejected by `set-active-stage` | `skills/aidd-core/templates/stage-lexicon.md:15` includes `status`; `skills/aidd-core/runtime/set_active_stage.py:10-22` omits it | `set-active-stage.sh status` -> `invalid stage ...` `rc=2` | Add `status` to `set_active_stage.VALID_STAGES` or remove from lexicon/docs; prefer adding for consistency |
| `spec`/`tasks` accepted in validators but absent in lexicon | `context_map_validate.py:29` has `spec`, `:28` has `tasks`; `stage-lexicon.md` has no `spec`/`tasks` stage | `context_map_validate` returns `OK` for `stage="spec"|"tasks"` | Decide explicit alias policy: either canonical aliases (`spec->spec-interview`, `tasks->tasklist`) or remove aliases from validators |
| `spec-interview` skill asks to set stage `spec` | `skills/spec-interview/SKILL.md:28` quote: "Set active stage `spec`" | `set-active-stage.sh spec` -> `invalid stage ...` `rc=2` | Make skill step use `spec-interview` (or allow `spec` alias in setter with normalization) |
| Template stage enum contains `release` not supported by runtime | `skills/tasks-new/templates/tasklist.template.md:27` includes `release`; `set_active_stage.py:10-22` has no `release` | potential stale placeholder; runtime won’t accept stage | Remove `release` from template or extend runtime lexicon if truly needed |

## 4. Skills inventory & quality (Claude Code aligned)

### 4.1 Inventory

| Skill | name | user-invocable | disable-model | allowed-tools | risk tools (Write/Edit/Bash) | context | agent | size (lines/bytes) | supporting files |
|---|---|---:|---:|---:|---:|---|---|---|---:|
| `skills/aidd-core/SKILL.md` | `aidd-core` | `False` | `None` | 0 | 0 | `-` | `-` | 91/4303 | 126 |
| `skills/aidd-init/SKILL.md` | `aidd-init` | `True` | `True` | 3 | 2 | `-` | `-` | 26/835 | 2 |
| `skills/aidd-loop/SKILL.md` | `aidd-loop` | `False` | `None` | 0 | 0 | `-` | `-` | 30/1478 | 20 |
| `skills/aidd-rlm/SKILL.md` | `aidd-rlm` | `False` | `None` | 7 | 7 | `-` | `-` | 38/1817 | 0 |
| `skills/idea-new/SKILL.md` | `idea-new` | `True` | `True` | 10 | 8 | `fork` | `analyst` | 40/1447 | 3 |
| `skills/implement/SKILL.md` | `implement` | `True` | `True` | 37 | 35 | `fork` | `implementer` | 64/2886 | 4 |
| `skills/plan-new/SKILL.md` | `plan-new` | `True` | `True` | 11 | 9 | `-` | `-` | 38/1332 | 3 |
| `skills/qa/SKILL.md` | `qa` | `True` | `True` | 26 | 24 | `fork` | `qa` | 52/2316 | 7 |
| `skills/researcher/SKILL.md` | `researcher` | `True` | `True` | 17 | 15 | `fork` | `researcher` | 48/2135 | 21 |
| `skills/review/SKILL.md` | `review` | `True` | `True` | 22 | 20 | `fork` | `reviewer` | 51/2842 | 14 |
| `skills/review-spec/SKILL.md` | `review-spec` | `True` | `True` | 12 | 10 | `-` | `-` | 36/1281 | 2 |
| `skills/spec-interview/SKILL.md` | `spec-interview` | `True` | `True` | 11 | 8 | `-` | `-` | 38/1254 | 1 |
| `skills/status/SKILL.md` | `status` | `True` | `False` | 4 | 3 | `-` | `-` | 26/916 | 5 |
| `skills/tasks-new/SKILL.md` | `tasks-new` | `True` | `True` | 12 | 10 | `fork` | `tasklist-refiner` | 42/1440 | 1 |

### 4.2 Correctness checks
- Frontmatter markers: `bad 0` (script check).
- Name rule + dir alignment + max length + non-empty description: `errors 0` across 14 skills.
- `context: fork` usage found in 6 skills (`idea-new`, `implement`, `qa`, `researcher`, `review`, `tasks-new`).
- Frontmatter flags are used intentionally:
  - `skills/spec-interview/SKILL.md:21` — `disable-model-invocation: true`.
  - `skills/status/SKILL.md:14` — `disable-model-invocation: false`.

### 4.3 Best-practice checks
- Description specificity heuristic (`Use when ...` trigger phrase): absent in all 14 skills (heuristic output).
- Conciseness flag (`>80 lines` or `>6KB`): only `skills/aidd-core/SKILL.md` (91 lines) flagged.
- Workflow/checklist presence: all complex stage skills (tools>=10 or fork) have `## Steps`; shared policy skills (`aidd-core`, `aidd-loop`, `aidd-rlm`) use policy format instead.

## 5. Subagents inventory & quality

### 5.1 Inventory
| Agent | description (short) | permissionMode | tools include Write | tools include Bash | maxTurns | memory | preloaded skills | preload size (lines/bytes) |
|---|---|---|---:|---:|---|---|---|---|
| `agents/analyst.md` | Сбор исходной идеи → анализ контекста → PRD draft + вопросы пользователю (READY после ответов). | `default` | `True` | `True` | `-` | `-` | feature-dev-aidd:aidd-core, feature-dev-aidd:aidd-rlm | 129/6151 |
| `agents/implementer.md` | Реализация по плану/tasklist малыми итерациями и управляемыми проверками. | `default` | `True` | `True` | `-` | `-` | feature-dev-aidd:aidd-core, feature-dev-aidd:aidd-rlm, feature-dev-aidd:aidd-loop | 159/7632 |
| `agents/plan-reviewer.md` | Ревью плана реализации: исполняемость, риски и тестовая стратегия перед PRD review. | `default` | `True` | `True` | `-` | `-` | feature-dev-aidd:aidd-core, feature-dev-aidd:aidd-rlm | 129/6151 |
| `agents/planner.md` | План реализации по PRD и research. Итерации-milestones без execution-деталей. | `default` | `True` | `True` | `-` | `-` | feature-dev-aidd:aidd-core, feature-dev-aidd:aidd-rlm | 129/6151 |
| `agents/prd-reviewer.md` | Структурное ревью PRD после review-plan. Проверка полноты, рисков и метрик. | `default` | `True` | `True` | `-` | `-` | feature-dev-aidd:aidd-core, feature-dev-aidd:aidd-rlm | 129/6151 |
| `agents/qa.md` | Финальная QA-проверка с отчётом по severity и traceability к PRD. | `default` | `False` | `True` | `-` | `-` | feature-dev-aidd:aidd-core, feature-dev-aidd:aidd-rlm, feature-dev-aidd:aidd-loop | 159/7632 |
| `agents/researcher.md` | Исследует кодовую базу перед внедрением фичи: точки интеграции, reuse, риски. | `default` | `True` | `True` | `-` | `-` | feature-dev-aidd:aidd-core, feature-dev-aidd:aidd-rlm | 129/6151 |
| `agents/reviewer.md` | Код-ревью по плану/PRD. Выявление рисков и блокеров без лишнего рефакторинга. | `default` | `False` | `True` | `-` | `-` | feature-dev-aidd:aidd-core, feature-dev-aidd:aidd-rlm, feature-dev-aidd:aidd-loop | 159/7632 |
| `agents/spec-interview-writer.md` | Build spec.yaml from interview log (tasklist обновляется через /feature-dev-aidd:tasks-new). | `default` | `True` | `True` | `-` | `-` | feature-dev-aidd:aidd-core, feature-dev-aidd:aidd-rlm | 129/6151 |
| `agents/tasklist-refiner.md` | Синтез подробного tasklist из plan/PRD/spec без интервью (no AskUserQuestionTool). | `default` | `True` | `True` | `-` | `-` | feature-dev-aidd:aidd-core, feature-dev-aidd:aidd-rlm | 129/6151 |
| `agents/validator.md` | Валидация исполняемости плана по PRD/Research; формирование вопросов. | `default` | `False` | `True` | `-` | `-` | feature-dev-aidd:aidd-core, feature-dev-aidd:aidd-rlm | 129/6151 |

### 5.2 Best-practice checks
- Single responsibility: в целом соблюдается (роли специализированы по стадиям).
- Tool hygiene:
  - `agents/implementer.md:7` — очень широкий tools set (включая git + test runners + hook call).
  - `rg -n '^disallowedTools:|^maxTurns:|^memory:' agents/*.md` -> no matches.
- Preload size:
  - `implementer`, `reviewer`, `qa`: 159 lines / 7632 bytes preload each (heavy vs остальные 129/6151).
- Implicit inheritance risk:
  - Все агенты имеют явный `skills:` список; missing skill paths не обнаружены.

## 6. Skills ↔ Agents interplay (двунаправленная модель)

### 6.1 Path (1): Skill запускает subagent (`context: fork` + `agent:`)
- Evidence:
  - `skills/idea-new/SKILL.md:22-23` — `context: fork`, `agent: analyst`.
  - `skills/implement/SKILL.md:49-50` — `context: fork`, `agent: implementer`.
  - `skills/review/SKILL.md:34-35` — `context: fork`, `agent: reviewer`.
- Actionability check:
  - `skills/idea-new/SKILL.md:28` has `## Steps`.
  - `skills/implement/SKILL.md:55` has mandatory preflight/postflight sequence.

### 6.2 Path (2): Subagent preload skills (`skills:` in agent frontmatter)
- Evidence:
  - `agents/implementer.md:8-11` preloads `aidd-core`, `aidd-rlm`, `aidd-loop`.
  - `agents/reviewer.md:8-11` same preload set for loop role.
- Correctness:
  - All preload skill references resolve to existing `skills/<name>/SKILL.md`.

### 6.3 Duplication / consolidation opportunities
- Same core policy is repeated in both command skills and agents:
  - `skills/idea-new/SKILL.md:26` — "Follow `feature-dev-aidd:aidd-core`".
  - `agents/analyst.md:16` — "Output follows aidd-core skill".
- Recommendation: keep policy only in shared skills; keep agents максимально thin to role-specific deltas.

## 7. Runtime scripts audit (.sh/.py) + dev/test leakage

### 7.1 Inventory and classification
- `git ls-files` runtime scripts: **115** (`skills/**/scripts`, `hooks/**`, `tools/**`).
- Classification:

| Category | Count |
|---|---:|
| hook library | 9 |
| hook pipeline | 11 |
| shared core wrapper | 15 |
| shared loop wrapper | 4 |
| stage-local wrapper | 26 |
| shim/deprecated/legacy path | 50 |

- Missing tracked paths in current FS: **51** (dominantly `tools/*.sh`, plus `skills/aidd-core/scripts/context_expand.sh`).

### 7.2 Type checks
- Python-shebang `.sh`: 11 files (all `hooks/*.sh`), allowlisted in `tests/repo_tools/python-shebang-allowlist.txt:5-15`.
- Bash syntax: `bash -n` passed for 44 bash-shebang `.sh` files.
- Python compile: `py_compile` passed for 20 files (`.py` + python-shebang `.sh`).

### 7.3 Leakage / dead artifacts
- Leakage scan in runtime paths for `dev|debug|scratch|tmp|playground|poc|bench`: no matches.
- Unclear artifact:
  - `hooks/gate-prd-review.sh` exists but not wired in `hooks/hooks.json`.
- Migration residue (high signal):
  - `git ls-files | rg '^tools/'` -> 50 tracked paths, while `find tools` -> 0 files.

## 8. Hooks/gates & permissions

### 8.1 Hook wiring
- `hooks/hooks.json:15` SessionStart wired.
- `hooks/hooks.json:27` PreToolUse wired.
- `hooks/hooks.json:51-84` Stop pipeline includes `gate-workflow`, `gate-tests`, `gate-qa`, `format-and-test`, `lint-deps`.
- `hooks/hooks.json:88-121` SubagentStop has equivalent guard pipeline.

### 8.2 Placeholder/unwired hooks
- `hooks/gate-prd-review.sh` present but not referenced in `hooks/hooks.json`.
- Runtime still enforces PRD review via `gate_workflow.py` internal call:
  - `skills/aidd-core/runtime/gate_workflow.py:258` defines `_run_prd_review_gate(...)`.
  - `skills/aidd-core/runtime/gate_workflow.py:677` executes it in main gate path.

### 8.3 "Give Claude a way to verify"
- Hook-level verification:
  - `hooks/gate-tests.sh:401-404` stage-aware tests gate (`implement` bypass, review/qa enforced).
  - `hooks/format-and-test.sh:870-872` only runs for `implement|review|qa`.
- Repo-level verification:
  - `tests/repo_tools/ci-lint.sh` orchestrates lint+guards+pytest.
  - `tests/repo_tools/smoke-workflow.sh` E2E workflow smoke.

### 8.4 Permission surface
- Skills: significant Write/Edit/Bash capability in stage skills (`implement` 35/37 risky tools).
- Subagents: all `permissionMode: default`; no `disallowedTools`, `maxTurns`, or `memory` constraints configured.

## 9. Templates & docs (skills-first + stage docs)

### 9.1 Inventory
- `templates/aidd` files: 22 total, from them `.gitkeep`: 16.
- Key stage templates live in skill dirs and are copied by init seeds:
  - `skills/idea-new/templates/prd.template.md`
  - `skills/plan-new/templates/plan.template.md`
  - `skills/researcher/templates/research.template.md`
  - `skills/spec-interview/templates/spec.template.yaml`
  - `skills/tasks-new/templates/tasklist.template.md`

### 9.2 Conflicts
- Documented SoT says `templates/aidd/**` is canonical, but executable init copies critical templates from `skills/*/templates/*`.
- `docs/` directory is absent in repo root, yet prompt lint policy requires `docs/skill-language.md`.
- Legacy command path drift:
  - `tests/repo_tools/shim-regression.sh` no longer exists; renamed to `tests/repo_tools/runtime-path-regression.sh`.

### 9.3 Recommended stage doc layout
- Keep `templates/aidd/` for skeleton/config only.
- Keep per-stage content templates under `skills/<stage>/templates/`.
- Maintain single stage lexicon doc and consume it in both runtime validators and templates.
- Add an explicit artifact contract table generated from `CONTRACT.yaml` where present.

## 10. CI/CD + Quality gates + Security

### 10.1 CI jobs and enforcement
- `.github/workflows/ci.yml` defines 3 jobs:
  - `lint-and-test` (runs `tests/repo_tools/ci-lint.sh` + QA gate bootstrap).
  - `smoke-workflow` (path-filtered execution).
  - `dependency-review` (PR only, `fail-on-severity: high`).
- Runtime change filter still includes `tools/**` and `templates/aidd/**`, although runtime migrated mostly to `skills/**`.

### 10.2 Executed checks (this audit)
- `tests/repo_tools/ci-lint.sh` -> **exit 1** due prompt-lint drift; pytest inside ci-lint passed: `516 passed, 2 skipped`.
- `tests/repo_tools/smoke-workflow.sh` -> **exit 0**, smoke scenario passed.
- `python3 -m pytest -q tests` -> **516 passed, 2 skipped**.
- `bash tests/repo_tools/runtime-path-regression.sh` -> **exit 0**.

### 10.3 Security/process gaps
- Positive: dependency review is present in CI.
- Gaps: no dedicated SAST/secret scanning/SBOM job in `.github/workflows` (single workflow file only).
- Enforcement/documentation drift: documented policy paths and lint baselines not aligned with current repo layout.

## 11. Findings table

| ID | Category | Severity | Evidence (file:line + quote <=25 words) | Impact | Recommendation | Effort | Risk | Confidence |
|---|---|---|---|---|---|---|---|---|
| F-001 | Templates/SoT | High | `AGENTS.md:21` "`templates/aidd/**` — источник истины"; `skills/aidd-init/runtime/init.py:13` copies `skills/aidd-core/templates/workspace-agents.md` | Wrong file edits won’t affect runtime bootstrap | Declare single canonical template source and update docs + init accordingly | M | Med | 0.95 |
| F-002 | Docs/Flow | High | `AGENTS.md:7` mentions `tools/`; `README.md:200` mentions `tools/`; command `ls -ld docs tools` -> "No such file" | Onboarding confusion, broken references | Remove/replace stale root-path references; document current layout only | S | Low | 0.97 |
| F-003 | CI/Quality | High | `tests/repo_tools/lint-prompts.py:103-105` expects `docs/skill-language.md` + baseline JSON; `ci-lint` output: missing both | CI red by policy drift, blocks release | Restore required policy/baseline artifacts or update lint policy roots | M | Med | 0.96 |
| F-004 | Lexicon/Flow | High | `stage-lexicon.md:15` has `status`; `set_active_stage.py:10-22` lacks it; `context_map_validate.py:29-31` allows `spec/status/tasks` | Stage handling inconsistent across runtime components | Unify stage enum in one module and import everywhere | M | Med | 0.95 |
| F-005 | Skills | Med | `skills/spec-interview/SKILL.md:28` "Set active stage `spec`"; command `set-active-stage.sh spec` -> invalid stage rc=2 | Spec interview flow can fail at stage set | Change to `spec-interview` or add normalized alias in setter | S | Low | 0.97 |
| F-006 | Templates | Med | `skills/tasks-new/templates/tasklist.template.md:27` includes `release`; no `release` in `set_active_stage.VALID_STAGES` | Template suggests unsupported stage value | Remove `release` placeholder or implement full release stage support | S | Low | 0.92 |
| F-007 | Hooks | Med | `hooks/gate-prd-review.sh` exists; `hooks/hooks.json` has no `gate-prd-review` command | Dead/untracked hook path increases maintenance debt | Either wire it explicitly or remove file and keep only `gate-workflow` path | S | Low | 0.93 |
| F-008 | Subagents/Permissions | Med | `agents/*:permissionMode=default`; no `disallowedTools|maxTurns|memory`; `agents/implementer.md:7` very broad tools | Higher blast radius for subagent mistakes | Tighten tool allowlists and add denylist/maxTurns per role | M | Med | 0.9 |
| F-009 | Skills/Permissions | Med | `skills/implement/SKILL.md:8-45` 37 tools (35 risky); similar pattern for review/qa | Excessive privilege vs least-privilege best practice | Split high-risk ops into narrower wrappers; reduce generic Bash scopes | M | Med | 0.9 |
| F-010 | Skills quality | Low | Heuristic output: all skills flagged `no-use-when-trigger` | Lower auto-selection precision in Claude skill routing | Add concise trigger phrase (`Use when ...`) to each description/body | S | Low | 0.78 |
| F-011 | Scripts/Migration | High | `git ls-files '^tools/'` -> 50; `find tools` -> 0; missing tracked paths total 51 | Migration state inconsistent; toolchain behavior may vary by checkout/index state | Finalize rename/removal wave; keep index and FS consistent | M | Med | 0.94 |
| F-012 | CI/Security | Low | `.github/workflows` contains only `ci.yml`; security job limited to dependency-review | Limited security depth (no SAST/secrets/SBOM) | Add dedicated security jobs and artifact outputs | M | Med | 0.82 |

## Appendix

### A) Commands executed (key)
```bash
pwd
git rev-parse --show-toplevel
git status --short
git rev-parse --abbrev-ref HEAD
git log --oneline -n 20
find . -maxdepth 2 -type d -not -path './.git*' | sort
git ls-files | awk -F/ '{print $1}' | sort | uniq -c | sort -nr
rg -n "review-spec|review-plan|review-prd|spec-interview|VALID_STAGES|set-active-stage" -S README.md README.en.md AGENTS.md skills hooks agents
python3 tests/repo_tools/lint-prompts.py --root .
python3 tests/repo_tools/skill-scripts-guard.py
git ls-files | rg '^(skills/.+/scripts/|tools/|hooks/).*\.(sh|py)$' > /tmp/aidd_runtime_scripts.txt
bash -n <bash-shebang scripts>
python3 -m py_compile <python files>
rg -n "context:\s*fork" -S skills
nl -ba hooks/hooks.json | sed -n '1,260p'
find templates/aidd -type f | sort
tests/repo_tools/ci-lint.sh
tests/repo_tools/smoke-workflow.sh
python3 -m pytest -q tests
bash tests/repo_tools/runtime-path-regression.sh
```

### B) Full lists

#### Skills (`skills/**/SKILL.md`)
- `skills/aidd-core/SKILL.md`
- `skills/aidd-init/SKILL.md`
- `skills/aidd-loop/SKILL.md`
- `skills/aidd-rlm/SKILL.md`
- `skills/idea-new/SKILL.md`
- `skills/implement/SKILL.md`
- `skills/plan-new/SKILL.md`
- `skills/qa/SKILL.md`
- `skills/researcher/SKILL.md`
- `skills/review-spec/SKILL.md`
- `skills/review/SKILL.md`
- `skills/spec-interview/SKILL.md`
- `skills/status/SKILL.md`
- `skills/tasks-new/SKILL.md`

#### Agents (`agents/*.md`)
- `agents/analyst.md`
- `agents/implementer.md`
- `agents/plan-reviewer.md`
- `agents/planner.md`
- `agents/prd-reviewer.md`
- `agents/qa.md`
- `agents/researcher.md`
- `agents/reviewer.md`
- `agents/spec-interview-writer.md`
- `agents/tasklist-refiner.md`
- `agents/validator.md`

#### Runtime scripts (full tracked list)
```text
hooks/__init__.py
hooks/context-gc-precompact.sh
hooks/context-gc-pretooluse.sh
hooks/context-gc-sessionstart.sh
hooks/context-gc-stop.sh
hooks/context-gc-userprompt.sh
hooks/context_gc/__init__.py
hooks/context_gc/precompact_snapshot.py
hooks/context_gc/pretooluse_guard.py
hooks/context_gc/sessionstart_inject.py
hooks/context_gc/stop_update.py
hooks/context_gc/userprompt_guard.py
hooks/context_gc/working_set_builder.py
hooks/format-and-test.sh
hooks/gate-prd-review.sh
hooks/gate-qa.sh
hooks/gate-tests.sh
hooks/gate-workflow.sh
hooks/hooklib.py
hooks/lint-deps.sh
skills/aidd-core/scripts/actions-validate.sh
skills/aidd-core/scripts/context-map-validate.sh
skills/aidd-core/scripts/context_expand.sh
skills/aidd-core/scripts/diff-boundary-check.sh
skills/aidd-core/scripts/md-patch.sh
skills/aidd-core/scripts/md-slice.sh
skills/aidd-core/scripts/prd-check.sh
skills/aidd-core/scripts/progress.sh
skills/aidd-core/scripts/rlm-slice.sh
skills/aidd-core/scripts/set-active-feature.sh
skills/aidd-core/scripts/set-active-stage.sh
skills/aidd-core/scripts/stage-result.sh
skills/aidd-core/scripts/status-summary.sh
skills/aidd-core/scripts/tasklist-check.sh
skills/aidd-core/scripts/tasklist-normalize.sh
skills/aidd-loop/scripts/loop-pack.sh
skills/aidd-loop/scripts/output-contract.sh
skills/aidd-loop/scripts/preflight-prepare.sh
skills/aidd-loop/scripts/preflight-result-validate.sh
skills/idea-new/scripts/analyst-check.sh
skills/implement/scripts/postflight.sh
skills/implement/scripts/preflight.sh
skills/implement/scripts/run.sh
skills/plan-new/scripts/research-check.sh
skills/qa/scripts/postflight.sh
skills/qa/scripts/preflight.sh
skills/qa/scripts/qa.sh
skills/qa/scripts/run.sh
skills/researcher/scripts/reports-pack.sh
skills/researcher/scripts/research.sh
skills/researcher/scripts/rlm-finalize.sh
skills/researcher/scripts/rlm-jsonl-compact.sh
skills/researcher/scripts/rlm-links-build.sh
skills/researcher/scripts/rlm-nodes-build.sh
skills/researcher/scripts/rlm-verify.sh
skills/review-spec/scripts/prd-review.sh
skills/review/scripts/context-pack.sh
skills/review/scripts/postflight.sh
skills/review/scripts/preflight.sh
skills/review/scripts/review-pack.sh
skills/review/scripts/review-report.sh
skills/review/scripts/reviewer-tests.sh
skills/review/scripts/run.sh
skills/status/scripts/index-sync.sh
skills/status/scripts/status.sh
tools/actions-apply.sh
tools/actions-validate.sh
tools/analyst-check.sh
tools/context-expand.sh
tools/context-map-validate.sh
tools/context-pack.sh
tools/dag-export.sh
tools/diff-boundary-check.sh
tools/doctor.sh
tools/identifiers.sh
tools/index-sync.sh
tools/init.sh
tools/loop-pack.sh
tools/loop-run.sh
tools/loop-step.sh
tools/md-patch.sh
tools/md-slice.sh
tools/output-contract.sh
tools/plan-review-gate.sh
tools/prd-check.sh
tools/prd-review-gate.sh
tools/prd-review.sh
tools/preflight-prepare.sh
tools/preflight-result-validate.sh
tools/progress.sh
tools/qa.sh
tools/reports-pack.sh
tools/research-check.sh
tools/research.sh
tools/researcher-context.sh
tools/review-pack.sh
tools/review-report.sh
tools/reviewer-tests.sh
tools/rlm-finalize.sh
tools/rlm-jsonl-compact.sh
tools/rlm-links-build.sh
tools/rlm-nodes-build.sh
tools/rlm-slice.sh
tools/rlm-verify.sh
tools/set-active-feature.sh
tools/set-active-stage.sh
tools/skill-contract-validate.sh
tools/stage-result.sh
tools/status-summary.sh
tools/status.sh
tools/tasklist-check.sh
tools/tasklist-normalize.sh
tools/tasks-derive.sh
tools/tests-log.sh
tools/tools-inventory.sh
```
#### Python-shebang `.sh`
- `hooks/context-gc-precompact.sh`
- `hooks/context-gc-pretooluse.sh`
- `hooks/context-gc-sessionstart.sh`
- `hooks/context-gc-stop.sh`
- `hooks/context-gc-userprompt.sh`
- `hooks/format-and-test.sh`
- `hooks/gate-prd-review.sh`
- `hooks/gate-qa.sh`
- `hooks/gate-tests.sh`
- `hooks/gate-workflow.sh`
- `hooks/lint-deps.sh`

#### Deprecated/legacy shim signals (full grep list)
```text
README.en.md:44:- Canonical runtime API lives in `skills/*/scripts/*` and hooks. `tools/*.sh` are retired.
README.en.md:46:- Every redirect wrapper must emit a warning and `exec` the canonical path to preserve exit codes.
README.en.md:122:| `tests/repo_tools/ci-lint.sh` | CI linters + unit tests (repo-only) |
README.en.md:123:| `tests/repo_tools/smoke-workflow.sh` | E2E smoke for repo maintainers |
README.en.md:133:- `tools/*.sh` are removed from runtime API; use canonical wrappers under `skills/*/scripts/*`.
README.en.md:227:- Repo checks (maintainer only): `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.
README.md:37:- Canonical runtime API lives in `skills/*/scripts/*` and hooks. `tools/*.sh` are retired.
README.md:109:| `tests/repo_tools/ci-lint.sh` | CI/линтеры и юнит-тесты (repo-only) |
README.md:110:| `tests/repo_tools/smoke-workflow.sh` | E2E smoke для проверок в репозитории |
README.md:120:- `tools/*.sh` удалены из runtime API; используйте canonical wrappers в `skills/*/scripts/*`.
README.md:215:- Репозиторные проверки (maintainer only): `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.
AGENTS.md:37:- Полный линт + unit‑тесты: `tests/repo_tools/ci-lint.sh`.
AGENTS.md:38:- E2E smoke: `tests/repo_tools/smoke-workflow.sh`.
AGENTS.md:46:- Для `tests/repo_tools/ci-lint.sh`: `shellcheck`, `markdownlint`, `yamllint` (иначе warn/skip).
AGENTS.md:58:- `tools/*.sh` отсутствуют в runtime API; используйте canonical wrappers в `skills/*/scripts/*`.
AGENTS.md:64:4. Не вводите новые `tools/*.sh`: stage/shared wrappers размещайте только в `skills/*/scripts/*`.
AGENTS.md:161:- Прогнать `tests/repo_tools/ci-lint.sh` и `tests/repo_tools/smoke-workflow.sh`.
tests/repo_tools/smoke-workflow.sh:3:# This script is executed directly via tests/repo_tools/smoke-workflow.sh.
tests/repo_tools/runtime-path-regression.sh:15:  err "tools/*.sh must be removed after tools-free shell cutover"
tests/repo_tools/runtime-path-regression.sh:38:  err "found stale tools/*.sh references; see /tmp/aidd-tools-shell-refs.txt"
tests/repo_tools/lint-prompts.py:51:    "${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh": "${CLAUDE_PLUGIN_ROOT}/skills/idea-new/scripts/analyst-check.sh",
tests/repo_tools/lint-prompts.py:52:    "${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh": "${CLAUDE_PLUGIN_ROOT}/skills/plan-new/scripts/research-check.sh",
tests/repo_tools/lint-prompts.py:53:    "${CLAUDE_PLUGIN_ROOT}/tools/prd-review.sh": "${CLAUDE_PLUGIN_ROOT}/skills/review-spec/scripts/prd-review.sh",
tests/repo_tools/lint-prompts.py:54:    "${CLAUDE_PLUGIN_ROOT}/tools/reports-pack.sh": "${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/reports-pack.sh",
tests/repo_tools/lint-prompts.py:55:    "${CLAUDE_PLUGIN_ROOT}/tools/rlm-nodes-build.sh": "${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-nodes-build.sh",
tests/repo_tools/lint-prompts.py:56:    "${CLAUDE_PLUGIN_ROOT}/tools/rlm-verify.sh": "${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-verify.sh",
tests/repo_tools/lint-prompts.py:57:    "${CLAUDE_PLUGIN_ROOT}/tools/rlm-links-build.sh": "${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-links-build.sh",
tests/repo_tools/lint-prompts.py:58:    "${CLAUDE_PLUGIN_ROOT}/tools/rlm-jsonl-compact.sh": "${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-jsonl-compact.sh",
tests/repo_tools/lint-prompts.py:59:    "${CLAUDE_PLUGIN_ROOT}/tools/rlm-finalize.sh": "${CLAUDE_PLUGIN_ROOT}/skills/researcher/scripts/rlm-finalize.sh",
tests/repo_tools/lint-prompts.py:60:    "${CLAUDE_PLUGIN_ROOT}/tools/qa.sh": "${CLAUDE_PLUGIN_ROOT}/skills/qa/scripts/qa.sh",
tests/repo_tools/lint-prompts.py:61:    "${CLAUDE_PLUGIN_ROOT}/tools/status.sh": "${CLAUDE_PLUGIN_ROOT}/skills/status/scripts/status.sh",
tests/repo_tools/lint-prompts.py:62:    "${CLAUDE_PLUGIN_ROOT}/tools/index-sync.sh": "${CLAUDE_PLUGIN_ROOT}/skills/status/scripts/index-sync.sh",
tests/repo_tools/bash-runtime-guard.py:13:RUNTIME_GLOBS = ("tools/*.sh", "hooks/*.sh")
tests/repo_tools/ci-lint.sh:101:  if [[ ! -f "tests/repo_tools/prompt-regression.sh" ]]; then
tests/repo_tools/ci-lint.sh:102:    warn "tests/repo_tools/prompt-regression.sh missing; skipping"
tests/repo_tools/ci-lint.sh:106:  if ! bash tests/repo_tools/prompt-regression.sh; then
tests/repo_tools/ci-lint.sh:113:  if [[ ! -f "tests/repo_tools/loop-regression.sh" ]]; then
tests/repo_tools/ci-lint.sh:114:    warn "tests/repo_tools/loop-regression.sh missing; skipping"
tests/repo_tools/ci-lint.sh:118:  if ! bash tests/repo_tools/loop-regression.sh; then
tests/repo_tools/ci-lint.sh:125:  if [[ ! -f "tests/repo_tools/output-contract-regression.sh" ]]; then
tests/repo_tools/ci-lint.sh:126:    warn "tests/repo_tools/output-contract-regression.sh missing; skipping"
tests/repo_tools/ci-lint.sh:130:  if ! bash tests/repo_tools/output-contract-regression.sh; then
tests/repo_tools/ci-lint.sh:193:  if [[ ! -f "tests/repo_tools/schema-guards.sh" ]]; then
tests/repo_tools/ci-lint.sh:194:    warn "tests/repo_tools/schema-guards.sh missing; skipping"
tests/repo_tools/ci-lint.sh:198:  if ! bash tests/repo_tools/schema-guards.sh; then
tests/repo_tools/ci-lint.sh:205:  if [[ ! -f "tests/repo_tools/runtime-path-regression.sh" ]]; then
tests/repo_tools/ci-lint.sh:206:    warn "tests/repo_tools/runtime-path-regression.sh missing; skipping"
tests/repo_tools/ci-lint.sh:210:  if ! bash tests/repo_tools/runtime-path-regression.sh; then
skills/aidd-loop/reference.md:14:- Do not reference `tools/*.sh` runtime entrypoints.
skills/aidd-rlm/SKILL.md:32:- RLM redirect wrappers remain fallback paths during the migration window.
skills/aidd-rlm/SKILL.md:33:- If a redirect wrapper is used, prefer canonical skill paths in new prompts.
skills/aidd-core/templates/stage-lexicon.md:44:- `tools/*.sh` допускаются только как redirect wrappers на время migration window.
```
### C) Unused/unclear artifacts list
- `hooks/gate-prd-review.sh` exists but unwired in `hooks/hooks.json`.
- Missing legacy command path: `tests/repo_tools/shim-regression.sh` (renamed to `tests/repo_tools/runtime-path-regression.sh`).
- Tracked-but-missing runtime paths (51 total), including all legacy `tools/*.sh` and old `skills/aidd-core/scripts/context_expand.sh`.
