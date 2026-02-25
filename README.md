# AIDD Claude Code + OpenCode Plugin - Language-agnostic Workflow Template

> Готовый плагин для Claude Code и OpenCode: слэш-команды, агенты, хуки и шаблоны для процесса idea → research → plan → review-spec → spec-interview (опционально) → tasklist → implement → review → qa.

## Оглавление
- [Что это](#что-это)
- [Быстрый старт](#быстрый-старт)
- [Подключение OpenCode](#подключение-opencode)
- [Глобальная установка OpenCode](#глобальная-установка-opencode)
- [Скрипты и проверки](#скрипты-и-проверки)
- [Слэш-команды](#слэш-команды)
- [Предпосылки](#предпосылки)
- [Диагностика путей](#диагностика-путей)
- [Документация](#документация)
- [Примеры](#примеры)
- [Вклад](#вклад)
- [Лицензия](#лицензия)

## Что это
AIDD — это AI-Driven Development: LLM работает не как «один большой мозг», а как команда ролей внутри привычного SDLC. Плагин для Claude Code/OpenCode помогает уйти от вайб-коддинга: фиксирует артефакты (PRD/plan/tasklist/отчёты), проводит через quality‑гейты и добавляет агентов, слэш‑команды, хуки и структуру `aidd/`.

Ключевые возможности:
- Слэш-команды и агенты для цепочки idea → research → plan → review-spec → spec-interview (опционально) → tasklist → implement → review → qa.
- Skill-first промпты: shared topology разделена между `skills/aidd-core`, `skills/aidd-policy`, `skills/aidd-docio`, `skills/aidd-flow-state`, `skills/aidd-observability`, `skills/aidd-loop`, `skills/aidd-rlm`, `skills/aidd-stage-research` (EN); stage entrypoints определяются stage skill-файлами.
- Research обязателен перед планированием: `research-check` требует статус `reviewed`.
- Гейты PRD/Plan Review/QA и безопасные хуки (stage-aware).
- Rolling context pack (pack-first): `aidd/reports/context/<ticket>.pack.md`.
- Hooks mode: по умолчанию `AIDD_HOOKS_MODE=fast`, строгий режим — `AIDD_HOOKS_MODE=strict`.
- Автоформат + тест‑политика по стадиям: `implement` — без тестов, `review` — targeted, `qa` — full.
- Loop mode implement↔review: loop pack/review pack, diff boundary guard, loop-step/loop-run.
- Dual runtime loop orchestration: `--runner-platform auto|claude|opencode` + `AIDD_LOOP_RUNNER_PLATFORM`.
- Единый формат ответов `AIDD:ANSWERS` + Q-идентификаторы в `AIDD:OPEN_QUESTIONS` (план ссылается на `PRD QN` без дублирования).
- Конвенции веток и коммитов через `aidd/config/conventions.json`.

## SKILL-first runtime path policy
- Stage/shared runtime entrypoints (canonical): `python3 skills/*/runtime/*.py` (Python-only canon с 2026-02-09).
- Runtime wrappers в `skills/*/scripts/*.sh` удалены.
- Hooks могут использовать shell entrypoints как platform glue (`hooks/*`).
- `tools/*` используется только для import stubs и repo-only tooling.
- Canonical runtime API lives in `skills/*/runtime/*.py`; `tools/*.sh` are retired.
- Начиная с 2026-02-09, новые интеграции должны вызывать Python entrypoints (`skills/*/runtime/*.py`) с `PYTHONPATH=${CLAUDE_PLUGIN_ROOT}`.
- Breaking cleanup (2026-02-21): удалены deprecated `skills/aidd-core/runtime/researcher_context.py`, alias `--answers` в `spec-interview`, alias `--refresh` в `review/context_pack`, а также deprecated `reports_pack` context-pack API.
- Крупные runtime entrypoints (`loop_*`, `tasklist_check`, `tasks_derive`, `reports_pack`, `qa`) переведены на thin facades с вынесенной реализацией в `runtime/*_parts/core.py`.
- Rollback criteria: если cutover ломает `tests/repo_tools/ci-lint.sh` или `tests/repo_tools/smoke-workflow.sh`, допускается временный wrapper fallback для конкретного entrypoint с обязательным follow-up task.
- Stage lexicon: public stage `review-spec` работает как umbrella для internal `review-plan` и `review-prd`.

## SKILL authoring contract
- Кросс-агентный канон: `docs/agent-skill-best-practices.md`.
- Языковые/lint правила: `docs/skill-language.md` + `tests/repo_tools/lint-prompts.py`.
- Для user-invocable stage skills обязателен раздел `## Command contracts` (interface-only карточки: `When to run`, `Inputs`, `Outputs`, `Failure mode`, `Next action`).
- Детали реализации не дублируются в `SKILL.md`; deep guidance уходит в supporting files.
- `## Additional resources` описывает progressive disclosure через явные `when:` + `why:` для каждого ресурса.

## Быстрый старт

### 1. Подключите marketplace и установите плагин

```text
/plugin marketplace add GrinRus/ai_driven_dev
/plugin install feature-dev-aidd@aidd-local
```

### 2. Инициализируйте workspace

```text
/feature-dev-aidd:aidd-init
```

`/feature-dev-aidd:aidd-init` создаёт `./aidd`, `.claude/settings.json` (дефолты `automation.tests`), `opencode.json` + `.opencode.json` (compat) и `.opencode/{commands,agents}` (из `skills/*/SKILL.md` и `agents/*.md`). Для обновления/детекта под стек используйте:

```text
/feature-dev-aidd:aidd-init --detect-build-tools
```

## Подключение OpenCode

Если хотите запускать AIDD через OpenCode (dual-runtime), сделайте это один раз:

```bash
export CLAUDE_PLUGIN_ROOT="/absolute/path/to/ai_driven_dev"

cd "$CLAUDE_PLUGIN_ROOT/platform/opencode-plugin"
npm install --no-audit --no-fund --no-package-lock
npm run build

cd "/path/to/your/workspace"
CLAUDE_PLUGIN_ROOT="$CLAUDE_PLUGIN_ROOT" \
PYTHONPATH="$CLAUDE_PLUGIN_ROOT" \
python3 "$CLAUDE_PLUGIN_ROOT/skills/aidd-init/runtime/init.py"
```

Что это делает:
- Собирает TS plugin bridge в `platform/opencode-plugin/dist/index.js`.
- Генерирует в workspace `opencode.json` (`.opencode.json` как compat) и `.opencode/{commands,agents}`.

Проверка:

```bash
cat opencode.json
ls .opencode/commands | head
ls .opencode/agents | head
```

После этого запускайте `opencode` из корня workspace, где лежит `opencode.json` (или `.opencode.json` в compat-сценариях).

## Глобальная установка OpenCode

Если хотите, чтобы AIDD-команды/агенты OpenCode были доступны во всех проектах на машине:

```bash
export AIDD_PLUGIN_ROOT="/absolute/path/to/ai_driven_dev"
export CLAUDE_PLUGIN_ROOT="$AIDD_PLUGIN_ROOT"

cd "$AIDD_PLUGIN_ROOT/platform/opencode-plugin"
npm install --no-audit --no-fund --no-package-lock
npm run build

mkdir -p "$HOME/.config/opencode/plugins" "$HOME/.config/opencode/commands" "$HOME/.config/opencode/agents"
cat > "$HOME/.config/opencode/plugins/feature-dev-aidd-opencode-bridge.mjs" <<EOF
process.env.AIDD_PLUGIN_ROOT = "$AIDD_PLUGIN_ROOT";
process.env.CLAUDE_PLUGIN_ROOT = "$AIDD_PLUGIN_ROOT";
export { default } from "$AIDD_PLUGIN_ROOT/platform/opencode-plugin/dist/index.js";
EOF

python3 - <<'PY'
import json
import os
import shutil
from pathlib import Path

root = Path(os.environ["AIDD_PLUGIN_ROOT"]).resolve()
cfg = Path.home() / ".config" / "opencode"
commands = cfg / "commands"
agents = cfg / "agents"
commands.mkdir(parents=True, exist_ok=True)
agents.mkdir(parents=True, exist_ok=True)

manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
for entry in manifest.get("skills", []):
    src = root / str(entry).lstrip("./")
    if src.is_dir():
        src = src / "SKILL.md"
    if src.is_file():
        shutil.copy2(src, commands / f"{src.parent.name}.md")

for entry in manifest.get("agents", []):
    src = root / str(entry).lstrip("./")
    if src.is_file():
        shutil.copy2(src, agents / src.name)
PY
```

Почему именно так:
- OpenCode глобально читает `~/.config/opencode/{plugins,commands,agents}`.
- Loader в `plugins/` фиксирует `AIDD_PLUGIN_ROOT`, поэтому bridge корректно находит `hooks/opencode_bridge.py` из любого `cwd`.
- Не копируйте `dist/*.js` в отдельную папку без `AIDD_PLUGIN_ROOT`: иначе пути к Python hooks будут некорректны.

### 3. Запустите фичу в Claude Code

```text
/feature-dev-aidd:idea-new STORE-123 "Checkout: скидки, купоны, защита от double-charge"
/feature-dev-aidd:researcher STORE-123
/feature-dev-aidd:plan-new STORE-123
/feature-dev-aidd:review-spec STORE-123
/feature-dev-aidd:spec-interview STORE-123
/feature-dev-aidd:tasks-new STORE-123
/feature-dev-aidd:implement STORE-123
/feature-dev-aidd:review STORE-123
/feature-dev-aidd:qa STORE-123
```

Примечания:
- Вопросы могут появляться после `/feature-dev-aidd:idea-new`, `/feature-dev-aidd:review-spec` и `/feature-dev-aidd:spec-interview` (если запускаете).
- `slug_hint` формируется автоматически внутри `/feature-dev-aidd:idea-new` из `note` (LLM summary → slug token); вручную передавать его не нужно.
- Ответы давайте в `AIDD:ANSWERS` (формат `Answer N`), а фиксацию/синхронизацию должен выполнить тот же агент/команда, которые задали вопросы.

### Обновление workspace
- `/feature-dev-aidd:aidd-init` без `--force` добавляет новые артефакты и не перезаписывает существующие.
- Для обновления шаблонов используйте `--force` или перенесите изменения вручную.
- Source of truth: stage content templates находятся в `skills/*/templates/*`; `templates/aidd/**` хранит только bootstrap config/placeholders.
- Root `AGENTS.md` — dev‑гайд репозитория; пользовательский канон процесса — `aidd/AGENTS.md` (копируется из `skills/aidd-core/templates/workspace-agents.md`).

## Скрипты и проверки

> Ниже перечислены canonical Python-команды runtime API.

| Команда | Назначение |
| --- | --- |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-init/runtime/init.py` | Создать `./aidd` из шаблонов (без перезаписи) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py` | Диагностика окружения, путей и наличия `aidd/` |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket <ticket>` | Сгенерировать RLM-only research артефакты |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/plan-new/runtime/research_check.py --ticket <ticket>` | Проверить статус Research `reviewed` |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/idea-new/runtime/analyst_check.py --ticket <ticket>` | Проверить PRD `READY` и синхронизацию вопросов/ответов |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/progress_cli.py --source <stage> --ticket <ticket>` | Подтвердить прогресс tasklist |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_pack.py --ticket <ticket> --stage implement\|review` | Сформировать loop pack для текущего work_item |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_report.py --ticket <ticket> --findings-file <path> --status warn` | Сформировать review report |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/review_pack.py --ticket <ticket>` | Сформировать review pack (тонкий feedback) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/review/runtime/reviewer_tests.py --ticket <ticket> --status required\|optional` | Обновить reviewer marker для тестовой политики |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/diff_boundary_check.py --ticket <ticket>` | Проверить diff против allowed_paths (loop-pack) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket <ticket>` | Один шаг loop (implement↔review) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket <ticket> --max-iterations 5` | Авто-loop до завершения всех открытых итераций |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/qa/runtime/qa.py --ticket <ticket> --report aidd/reports/qa/<ticket>.json --gate` | Сформировать QA отчёт и гейт |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasklist_check.py --ticket <ticket>` | Проверить tasklist по канону |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/tasks_derive.py --source <qa\|research\|review> --append --ticket <ticket>` | Добавить handoff-задачи |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/status.py --ticket <ticket> [--refresh]` | Краткий статус тикета |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-flow-state/runtime/status_summary.py --ticket <ticket> --stage <implement\|review\|qa>` | Финальный статус из stage_result (single source) |
| `python3 ${CLAUDE_PLUGIN_ROOT}/skills/status/runtime/index_sync.py --ticket <ticket>` | Обновить индекс тикета |
| `tests/repo_tools/ci-lint.sh` | CI/линтеры и юнит-тесты (repo-only) |
| `tests/repo_tools/smoke-workflow.sh` | E2E smoke для проверок в репозитории |

`tests/repo_tools/` — repo-only утилиты для CI/линтинга; в плагин не входят.

`review` runtime commands are canonical at `skills/review/runtime/*`.

CI required-check parity:
- Required: `lint-and-test`, `smoke-workflow`, `dependency-review`.
- Security rollout: `security-secret-scan` + `security-sast` работают как advisory, пока `AIDD_SECURITY_ENFORCE!=1`; при `AIDD_SECURITY_ENFORCE=1` становятся required.

### Shared Ownership Map
- `skills/aidd-core/runtime/*` — shared core runtime API (canonical).
- `skills/aidd-docio/runtime/*` — shared DocIO runtime API (`md_*`, `actions_*`, `context_*`).
- `skills/aidd-flow-state/runtime/*` — shared flow/state runtime API (`set-active-*`, `progress*`, `tasklist*`, `stage_result`, `status_summary`, `prd_check`, `tasks_derive`).
- `skills/aidd-observability/runtime/*` — shared observability runtime API (`doctor`, `tools_inventory`, `tests_log`, `dag_export`, `identifiers`).
- `skills/aidd-loop/runtime/*` — shared loop runtime API (canonical).
- `skills/<stage>/runtime/*` — stage-local runtime API (single owner per stage).
- `tools/*.sh` удалены из runtime API.

## Слэш-команды

| Команда | Назначение | Аргументы |
| --- | --- | --- |
| `/feature-dev-aidd:aidd-init` | Инициализировать workspace (`./aidd`) | `[--force] [--detect-build-tools]` |
| `/feature-dev-aidd:idea-new` | Создать PRD draft и вопросы | `<TICKET> [note...]` |
| `/feature-dev-aidd:researcher` | Собрать контекст и отчёт Researcher | `<TICKET> [note...] [--paths ... --keywords ... --note ...]` |
| `/feature-dev-aidd:plan-new` | План + валидация | `<TICKET> [note...]` |
| `/feature-dev-aidd:review-spec` | Review plan + PRD | `<TICKET> [note...]` |
| `/feature-dev-aidd:spec-interview` | Spec interview (опционально) | `<TICKET> [note...]` |
| `/feature-dev-aidd:tasks-new` | Сформировать tasklist | `<TICKET> [note...]` |
| `/feature-dev-aidd:implement` | Итеративная реализация | `<TICKET> [note...] [test=fast\|targeted\|full\|none] [tests=<filters>] [tasks=<task1,task2>]` |
| `/feature-dev-aidd:review` | Код-ревью и задачи | `<TICKET> [note...]` |
| `/feature-dev-aidd:qa` | Финальная QA-проверка | `<TICKET> [note...]` |
| `/feature-dev-aidd:status` | Статус тикета и артефакты | `[<TICKET>]` |

## Research RLM

RLM evidence используется как основной источник интеграций/рисков/связей (pack-first + slice on demand).

Troubleshooting пустого контекста:
- Уточните `--paths`/`--keywords` (указывайте реальный код, не только `aidd/`).
- Если `rlm_status=pending`, выполните agent‑flow по worklist и пересоберите RLM pack.

Migration policy (legacy -> RLM-only):
- Legacy pre-RLM research context/targets artifacts не участвуют в runtime/gates.
- Для старых workspace-артефактов пересоберите research:
  `python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket <ticket> --auto`.
- Если `rlm_status=pending`, выполните handoff на shared owner:
  `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_finalize.py --ticket <ticket>`.
- Для readiness в `plan/review/qa` нужен минимальный RLM набор:
  `rlm-targets`, `rlm-manifest`, `rlm.worklist.pack`, `rlm.nodes`, `rlm.links`, `rlm.pack`.

RLM artifacts (pack-first):
- Pack summary: `aidd/reports/research/<ticket>-rlm.pack.json`.
- Slice-инструмент: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py --ticket <ticket> --query "<token>" [--paths path1,path2] [--lang kt,java]`.
- Бюджет RLM pack: `config/conventions.json` → `rlm.pack_budget` (`max_chars`, `max_lines`, top-N limits).

## Loop mode (implement↔review)

Loop = 1 work_item → implement → review → (revise)* → ship.
Если после SHIP есть открытые итерации в `AIDD:NEXT_3`/`AIDD:ITERATIONS_FULL`, loop-run выбирает следующий work_item, обновляет `aidd/docs/.active.json` (work_item/stage) и продолжает implement.

Ключевые артефакты:
- `aidd/reports/loops/<ticket>/<scope_key>.loop.pack.md` — тонкий контекст итерации.
- `aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md` — краткий feedback с verdict.

Команды:
- Manual: `/feature-dev-aidd:implement <ticket>` → `/feature-dev-aidd:review <ticket>`.
- Loop CLI: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket <ticket>` (fresh sessions).
- OpenCode loop CLI: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket <ticket> --runner-platform opencode --runner "opencode"`.
- One-shot: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket <ticket> --max-iterations 5`.
- Scope guard: `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/runtime/diff_boundary_check.py --ticket <ticket>`.
- Stream (optional): `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_step.py --ticket <ticket> --stream=text|tools|raw`,
   `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/runtime/loop_run.py --ticket <ticket> --stream`.

Пример запуска из корня проекта:
```bash
CLAUDE_PLUGIN_ROOT="/path/to/ai_driven_dev" PYTHONPATH="$CLAUDE_PLUGIN_ROOT" python3 "$CLAUDE_PLUGIN_ROOT/skills/aidd-loop/runtime/loop_run.py" --ticket ABC-123 --max-iterations 5
```

Примечание:
- Ralph plugin использует stop-hook в той же сессии (completion promise). AIDD loop-mode — fresh sessions.
- Для max-iterations используйте формат с пробелом: `--max-iterations 5` (без `=`).
- Если `CLAUDE_PLUGIN_ROOT`/`AIDD_PLUGIN_DIR` не задан, loop-скрипты пытаются auto-detect по пути скрипта и печатают WARN; при недоступности авто‑детекта — BLOCKED.
- Platform override: `AIDD_LOOP_RUNNER_PLATFORM=auto|claude|opencode` (CLI: `--runner-platform`).
- Stream логи: `aidd/reports/loops/<ticket>/cli.loop-*.stream.log` (human) и `aidd/reports/loops/<ticket>/cli.loop-*.stream.jsonl` (raw).
- Loop run log: `aidd/reports/loops/<ticket>/loop.run.log`.
- Настройки cadence/tests хранятся в `.claude/settings.json` в корне workspace (без `aidd/.claude`).

Правила:
- Loop pack first, без больших вставок логов/диффов (ссылки на `aidd/reports/**`).
- Review не расширяет scope: новое → `AIDD:OUT_OF_SCOPE_BACKLOG` или новый work_item.
- Review pack обязателен; при наличии review report + loop pack допускается авто‑пересборка.
- Финальный Status в командах implement/review/qa должен совпадать со `stage_result`.
- Allowed paths берутся из `Expected paths` итерации (`AIDD:ITERATIONS_FULL`).
- Loop-mode тесты следуют stage policy: `implement` — без тестов, `review` — targeted, `qa` — full.
- Tests evidence: `tests_log` со `status=skipped` + `reason_code` считается evidence при `tests_required=soft` (для `hard` → BLOCKED).

## Предпосылки
- `bash`, `git`, `python3`.
- Claude Code с доступом к plugin marketplace.
- Для OpenCode runtime/checks: `opencode` CLI, `node`, `npm`.
- Инструменты сборки/тестов вашего стека (по желанию).
- MCP интеграции опциональны: `.mcp.json` не входит в плагин по умолчанию.

Поддерживаются macOS/Linux. Для Windows используйте WSL или Git Bash.

## Диагностика путей
- Плагин живёт в корне репозитория (директории `agents/`, `skills/`, `hooks/`, `tools/`).
- Рабочие артефакты разворачиваются в `./aidd` после `/feature-dev-aidd:aidd-init`.
- Если команды или хуки не находят workspace, запустите `/feature-dev-aidd:aidd-init` или укажите `CLAUDE_PLUGIN_ROOT`.
- Для быстрой проверки окружения используйте `python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-observability/runtime/doctor.py`.

## Документация
- Канон ответа и pack-first: `aidd/AGENTS.md` + `skills/aidd-policy/SKILL.md`.
- Пользовательский гайд (runtime): `aidd/AGENTS.md`; dev‑гайд репозитория: `AGENTS.md`.
- Skill-first topology: `skills/aidd-core`, `skills/aidd-policy`, `skills/aidd-docio`, `skills/aidd-flow-state`, `skills/aidd-observability`, `skills/aidd-loop`, `skills/aidd-rlm`, `skills/aidd-stage-research` (EN).
- Английская версия: `README.en.md`.

## Примеры
Демо‑проекты и вспомогательные скрипты не поставляются — репозиторий остаётся language‑agnostic. При необходимости держите демо‑проекты вне плагина и описывайте их в документации вашего workspace.

## Dev-only проверки
- Репозиторные проверки (maintainer only): `tests/repo_tools/ci-lint.sh`, `tests/repo_tools/smoke-workflow.sh`.

## Вклад
Правила вкладов: `CONTRIBUTING.md`.

## Лицензия
MIT, подробнее: `LICENSE`.
