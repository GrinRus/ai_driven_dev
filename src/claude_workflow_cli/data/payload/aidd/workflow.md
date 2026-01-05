# Workflow Claude Code

Документ описывает целевой процесс работы команды после запуска `init-claude-workflow.sh`. Цикл строится вокруг идеи и проходит семь этапов: **идея → research → план → PRD review → задачи → реализация → ревью**. На каждом шаге задействованы специализированные саб-агенты Claude Code и защитные хуки, которые помогают удерживать кодовую базу в рабочем состоянии.

> **Плагин AIDD.** Команды/агенты/хуки живут в `aidd/{commands,agents,hooks}` с манифестом `aidd/.claude-plugin/plugin.json`; runtime `.claude/` в workspace содержит только настройки/кеш. Marketplace для автоподключения — корневой `.claude-plugin/marketplace.json`, root `.claude/settings.json` включает `feature-dev-aidd`. Запускайте Claude из корня: плагин подхватится автоматически.
> Ticket — основной идентификатор фичи (`aidd/docs/.active_ticket`), slug-hint при необходимости сохраняется в `aidd/docs/.active_feature` и используется в шаблонах и логах.
> Текущая стадия фиксируется в `aidd/docs/.active_stage` (`idea/research/plan/tasklist/implement/review/qa`); команды обновляют маркер и допускают откат на любой этап.
> Payload обновляйте через CLI: `claude-workflow init --target .` (bootstrap), `claude-workflow preset <name>`, `claude-workflow sync|upgrade` для подтяжки шаблонов и `claude-workflow smoke` для быстрой проверки гейтов.
> **Важно:** `.claude/`, `.claude-plugin/` и содержимое `aidd/` (docs/templates/scripts/tools/commands/agents/hooks) — это развернутый snapshot. Все правки вносятся в `src/claude_workflow_cli/data/payload`, затем синхронизируются через `scripts/sync-payload.sh --direction=to-root|from-root`. Перед отправкой PR запустите `python3 tools/check_payload_sync.py` или `pre-commit run payload-sync-check`, чтобы убедиться в отсутствии расхождений.
## Обзор этапов

| Этап | Команда | Саб-агент | Основные артефакты |
| --- | --- | --- | --- |
| Аналитика идеи | `/idea-new <ticket> [slug-hint]` | `analyst` | `aidd/docs/prd/<ticket>.prd.md`, активная фича |
| Research | `claude-workflow research --ticket <ticket>` → `/researcher <ticket>` | `researcher` | `aidd/docs/research/<ticket>.md`, `reports/research/<ticket>-targets.json` |
| Планирование | `/plan-new <ticket>` | `planner`, `validator` | `aidd/docs/plan/<ticket>.md`, уточнённые вопросы |
| PRD review | `/review-prd <ticket>` | `prd-reviewer` | `aidd/docs/prd/<ticket>.prd.md`, отчёт `reports/prd/<ticket>.json` |
| Тасклист | `/tasks-new <ticket>` | — | `aidd/docs/tasklist/<ticket>.md` (обновлённые чеклисты) |
| Реализация | `/implement <ticket>` | `implementer` | кодовые изменения, актуальные тесты |
| Ревью | `/review <ticket>` | `reviewer` | замечания в `aidd/docs/tasklist/<ticket>.md`, итоговый статус |
| QA | `/qa <ticket>` | `qa` | `aidd/docs/tasklist/<ticket>.md` (QA блок), `reports/qa/<ticket>.json` |

На каждом шаге действует правило **agent-first**: агент обязан собрать максимум информации из репозитория (PRD, research, backlog, reports, тесты) и запустить разрешённые команды (`rg`, `claude-workflow progress`, `./gradlew test`, etc.) прежде чем обращаться к пользователю. Любой вопрос сопровождается перечислением изученных артефактов и форматом ответа.

## Подробности по шагам

### 1. Идея (`/idea-new`)
- Устанавливает активную фичу (`aidd/docs/.active_ticket`).
- Сразу запускайте `claude-workflow research --ticket <ticket> --auto` — CLI соберёт цели, сгенерирует `reports/research/<ticket>-targets.json` и подготовит `aidd/docs/research/<ticket>.md`; добавляйте ручные наблюдения через `--note "..."` или `--note @memo.md`.
- Автоматически создаёт черновик PRD по шаблону (`aidd/docs/prd/<ticket>.prd.md`, `Status: draft`), собирает вводные, риски и метрики.
- Саб-агент **analyst** сначала опирается на slug-hint (`aidd/docs/.active_feature`), PRD/research шаблоны и отчёты (`reports/research/*.json`), заполняет все разделы PRD по найденным данным, а вопросы пользователю формулирует только для пробелов, которые нельзя закрыть репозиторием.
- Каждая пара «Вопрос N»/«Ответ N» фиксируется в разделе `## Диалог analyst` вместе с перечислением проверенных артефактов; итоговый статус переводится в READY только после закрытия всех блокеров, незакрытые вопросы отражаются в `## 10. Открытые вопросы`.
- После диалога запускайте `claude-workflow analyst-check --ticket <ticket>` — команда проверит структуру вопросов/ответов и статус. При ошибке вернитесь к агенту и дополните информацию.

- CLI-команда `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph [--reuse-only] [--paths/--keywords/--langs/--graph-langs/--graph-filter/--graph-limit/--note]` собирает контекст: пути из `config/conventions.json`, `code_index` (символы/импорты/тесты), `reuse_candidates` и `call_graph`/`import_graph` (только Java/Kotlin через tree-sitter при наличии). По умолчанию call graph фильтруется по `<ticket>|<keywords>` и ограничивается 100 рёбрами (focus) в контексте; полный граф сохраняется в `reports/research/<ticket>-call-graph-full.json`. Результат сохраняется в `reports/research/<ticket>-targets.json` и `<ticket>-context.json`.
- Саб-агент **researcher** использует `code_index`/`reuse_candidates` и `call_graph`/`import_graph`, при необходимости дорасшифровывает связи в Claude Code, дополняет `rg "<ticket|feature>"`, `find`, `python`-скриптами, чтобы выявить интеграционные точки, тесты, миграции и долги. Все выводы оформляются в `aidd/docs/research/<ticket>.md` со ссылками на файлы/строки, команды и call graph; при отсутствии данных фиксируется baseline «Контекст пуст, требуется baseline» с перечислением уже просмотренных путей.
- Статус в отчёте должен стать `Status: reviewed`, критичные действия переносятся в план и `aidd/docs/tasklist/<ticket>.md`.
- При запуске с `--auto` Researcher отмечает нулевые совпадения (новые проекты), добавляет в шаблон блок «Контекст пуст, требуется baseline» и предлагает рекомендации (`profile.recommendations`) на основе `config/conventions.json`; такие отчёты можно временно оставлять в `Status: pending`, baseline фиксируется в `aidd/docs/research/<ticket>.md`.

### 3. План (`/plan-new`)
- Саб-агент **planner** формирует пошаговый план реализации по PRD: секция «Architecture & Patterns» (границы/паттерны KISS/YAGNI/DRY/SOLID, по умолчанию service layer + adapters/ports), reuse-точки из Researcher, итерации/DoD/риски.
- Саб-агент **validator** проверяет полноту; найденные вопросы возвращаются продукту.
- Все открытые вопросы синхронизируются между PRD и планом.

### 4. PRD Review (`/review-prd`)
- Саб-агент **prd-reviewer** проверяет полноту PRD, метрики, риски и соответствие ADR.
- Результат фиксируется в разделе `## PRD Review` (статус, summary, findings, action items) и в отчёте `reports/prd/<ticket>.json`.
- Блокирующие action items и открытые вопросы синхронизируются с планом и `aidd/docs/tasklist/<ticket>.md`.

### 5. Тасклист (`/tasks-new`)
- Преобразует план в чеклисты в `aidd/docs/tasklist/<ticket>.md`.
- Структурирует задачи по этапам (аналитика, разработка, QA, релиз).
- Добавляет критерии приёмки и зависимости.

### 6. Реализация (`/implement`)
- Саб-агент **implementer** следует шагам плана, учитывает выводы `aidd/docs/research/<ticket>.md` и PRD и вносит изменения малыми итерациями, опираясь на данные репозитория.
- В конце итерации (Stop/SubagentStop) запускается `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh` **только на стадии implement**. Управление через `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`; все ручные команды (`./gradlew test`, `gradle lint`, `claude-workflow progress --source implement --ticket <ticket>`) перечисляйте в ответе с кратким результатом.
- Каждая итерация должна завершаться фиксацией прогресса в `aidd/docs/tasklist/<ticket>.md`: переведите релевантные пункты `- [ ] → - [x]`, обновите строку `Checkbox updated: …`, приложите ссылку на diff/команду и запустите `claude-workflow progress --source implement --ticket <ticket>`. Если утилита сообщает, что новых `- [x]` нет, вернитесь к чеклисту прежде чем завершать команду.
- Если включены дополнительные гейты (`config/gates.json`), следите за сообщениями `gate-workflow.sh` (включая PRD review), `gate-qa.sh`, `gate-tests.sh`, `lint-deps.sh`.
- После отчётов QA/Review/Research добавляйте handoff-задачи командой `claude-workflow tasks-derive --source <qa|review|research> --append --ticket <ticket>` (новые `- [ ]` должны ссылаться на `reports/<source>/...`); при необходимости подтвердите прогресс `claude-workflow progress --source handoff --ticket <ticket>`.

### 7. Ревью (`/review`)
- Саб-агент **reviewer** проводит код-ревью и синхронизирует замечания в `aidd/docs/tasklist/<ticket>.md`.
- Reviewer сверяет, что выполненные пункты отмечены `- [x]`, обновляет строку `Checkbox updated: …` и при необходимости запускает `claude-workflow progress --source review --ticket <ticket>`, чтобы убедиться, что прогресс зафиксирован.
- Для запуска автотестов reviewer помечает маркер `reports/reviewer/<ticket>.json` командой `claude-workflow reviewer-tests --status required` (slug берётся из `aidd/docs/.active_ticket`). После успешного прогона обновите статус на `optional`, чтобы отключить авто‑запуск.
- При блокирующих проблемах фича возвращается на стадию реализации; при минорных — формируется список рекомендаций.

### 8. QA (`/qa`)
- Обязательная стадия перед релизом: запустите `/qa <ticket>` или `claude-workflow qa --ticket <ticket> --report reports/qa/<ticket>.json --gate`, чтобы сформировать отчёт и статус READY/WARN/BLOCKED.
- Саб-агент **qa** сопоставляет diff с чеклистом `aidd/docs/tasklist/<ticket>.md`, фиксирует найденные проблемы и рекомендации; гейт `gate-qa.sh` блокирует merge при blocker/critical или отсутствии отчёта.
- После статуса READY/WARN добавьте handoff-задачи из `reports/qa/<ticket>.json` через `claude-workflow tasks-derive --source qa --append --ticket <ticket>`, чтобы исполнитель видел все находки.
- Обновите QA-раздел tasklist (новые `- [x]`, дата/итерация, ссылки на логи) и выполните `claude-workflow progress --source qa --ticket <ticket>`.

## Автоматизация и гейты

- Хуки (`gate-*`, `format-and-test.sh`, `lint-deps.sh`) описаны в `hooks/hooks.json` и вызывают `${CLAUDE_PLUGIN_ROOT}/hooks/*`; `.claude/settings.json` хранит только permissions/automation и включает плагин.
- `aidd/hooks/hooks.json` определяет лёгкие PreToolUse-guards (Bash/Read) и UserPromptSubmit guard, а тяжёлые гейты запускает на Stop/SubagentStop: `gate-workflow`, `gate-tests`, `gate-qa`, `format-and-test`, `lint-deps`. Это снижает нагрузку и запускает проверки после завершения итерации.
- Матчинг стадий и гейтов: `format-and-test`, `gate-tests`, `lint-deps` работают только при `aidd/docs/.active_stage=implement`, `gate-qa` — только при `qa`, `gate-workflow` блокирует правки кода вне `implement/review/qa` (если стадия задана). Для разового обхода используйте `CLAUDE_SKIP_STAGE_CHECKS=1` или задайте `CLAUDE_ACTIVE_STAGE`.

### Ревизия hook-событий (Wave 58)

| Событие | Хуки | Назначение | Статус |
| --- | --- | --- | --- |
| `SessionStart` | `scripts/context_gc/sessionstart_inject.py` | Добавить working set в контекст сессии | нужно |
| `PreCompact` | `scripts/context_gc/precompact_snapshot.py` | Снимок контекста перед компактом | нужно |
| `PreToolUse` | `scripts/context_gc/pretooluse_guard.py` (Bash/Read) | Лёгкие guard'ы: wrap output, size/read, safety | условно (только лёгкие проверки) |
| `UserPromptSubmit` | `scripts/context_gc/userprompt_guard.py` | Контроль промптов перед отправкой | условно |
| `Stop`/`SubagentStop` | `gate-workflow`, `gate-tests`, `gate-qa`, `format-and-test`, `lint-deps` | Тяжёлые проверки после завершения итерации | нужно |
| `PostToolUse` | — | Убрано, чтобы не запускать тяжёлые гейты на каждый шаг | лишнее |

- `config/gates.json` управляет дополнительными проверками:
  - дополнительные гейты конфигурируются в `config/gates.json` (см. `tests_required`, `qa`).
  - `prd_review` — контролирует раздел `## PRD Review`: разрешённые ветки, статус, блокирующие уровни и отчёт в `reports/prd/<ticket>.json`.
  - `researcher` — проверяет наличие `aidd/docs/research/<ticket>.md`, статус `Status: reviewed`, свежесть `reports/research/<ticket>-context.json` и заполненность `reports/research/<ticket>-targets.json`.
  - `analyst` — следит за блоком `## Диалог analyst`, наличием ответов `Ответ N` и запретом статуса READY при незакрытых вопросах; используется командой `claude-workflow analyst-check` и хуком `gate-workflow.sh`.
  - `qa` — запускает `scripts/qa-agent.py`, блокируя фичу при критичных/блокирующих находках.
  - `tests_required` — режим `disabled|soft|hard` для обязательных тестов.
  - `deps_allowlist` — включает проверку зависимостей через `scripts/lint-deps.sh`.
  - `feature_ticket_source` — путь к файлу с активным ticket (по умолчанию `aidd/docs/.active_ticket`); `feature_slug_hint_source` управляет slug-хинтом (`aidd/docs/.active_feature`).
  - `tasklist_progress` — гарантирует, что при изменениях в коде появляются новые `- [x]` в `aidd/docs/tasklist/<ticket>.md`. Гейт активен для `/implement`, `/qa`, `/review` и хука `gate-workflow.sh`; при технических задачах можно настроить `skip_branches` или временно выставить `CLAUDE_SKIP_TASKLIST_PROGRESS=1`.
- `SKIP_AUTO_TESTS=1` временно отключает форматирование и выборочные тесты.
- `STRICT_TESTS=1` заставляет `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh` завершаться ошибкой при падении тестов.

## Роли и ответственность команды

- **Product/Analyst** — поддерживает PRD, отвечает на вопросы planner/validator.
- **Researcher** — исследует кодовую базу, фиксирует reuse/риски, поддерживает `aidd/docs/research/<ticket>.md` и контекст для команды.
- **Tech Lead/Architect** — утверждает план, следит за гейтами и архитектурными решениями.
- **Разработчики** — реализуют по плану, поддерживают тесты и документацию в актуальном состоянии.
- **QA** — помогает с чеклистами в `aidd/docs/tasklist/<ticket>.md`, расширяет тестовое покрытие и сценарии ручной проверки, по итогам каждого цикла запускает `claude-workflow progress --source qa --ticket <ticket>` и фиксирует строку `Checkbox updated: …` в отчёте.
- **PRD reviewer** — утверждает готовность PRD, закрывает блокирующие вопросы до начала разработки.
- **Reviewer** — финализирует фичу, проверяет, что все чеклисты в `aidd/docs/tasklist/<ticket>.md` закрыты.

Следуйте этому циклу, чтобы команда оставалась синхронизированной, а артефакты — актуальными.
