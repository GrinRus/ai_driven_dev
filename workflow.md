# Workflow Claude Code

Документ описывает целевой процесс работы команды после запуска `init-claude-workflow.sh`. Цикл строится вокруг идеи и проходит семь этапов: **идея → research → план → PRD review → задачи → реализация → ревью**. На каждом шаге задействованы специализированные саб-агенты Claude Code и защитные хуки, которые помогают удерживать кодовую базу в рабочем состоянии.

> Ticket — основной идентификатор фичи (`docs/.active_ticket`), slug-hint при необходимости сохраняется в `docs/.active_feature` и используется в шаблонах и логах.
>
> **Важно:** `.claude/`, `docs/`, `templates/` и скрипты в корне — это развернутый snapshot. Все правки вносятся в `src/claude_workflow_cli/data/payload`, затем синхронизируются через `scripts/sync-payload.sh --direction=to-root|from-root`. Перед отправкой PR запустите `python3 tools/check_payload_sync.py` или `pre-commit run payload-sync-check`, чтобы убедиться в отсутствии расхождений.

## Обзор этапов

| Этап | Команда | Саб-агент | Основные артефакты |
| --- | --- | --- | --- |
| Аналитика идеи | `/idea-new <ticket> [slug-hint]` | `analyst` | `docs/prd/<ticket>.prd.md`, активная фича |
| Research | `claude-workflow research --ticket <ticket>` → `/researcher <ticket>` | `researcher` | `docs/research/<ticket>.md`, `reports/research/<ticket>-targets.json` |
| Планирование | `/plan-new <ticket>` | `planner`, `validator` | `docs/plan/<ticket>.md`, уточнённые вопросы |
| PRD review | `/review-prd <ticket>` | `prd-reviewer` | `docs/prd/<ticket>.prd.md`, отчёт `reports/prd/<ticket>.json` |
| Тасклист | `/tasks-new <ticket>` | — | `docs/tasklist/<ticket>.md` (обновлённые чеклисты) |
| Реализация | `/implement <ticket>` | `implementer` | кодовые изменения, актуальные тесты |
| Ревью | `/review <ticket>` | `reviewer` | замечания в `docs/tasklist/<ticket>.md`, итоговый статус |
| QA | `/qa <ticket>` | `qa` | `docs/tasklist/<ticket>.md` (QA блок), `reports/qa/<ticket>.json` |

На каждом шаге действует правило **agent-first**: агент обязан собрать максимум информации из репозитория (PRD, research, backlog, reports, тесты) и запустить разрешённые команды (`rg`, `claude-workflow progress`, `./gradlew test`, etc.) прежде чем обращаться к пользователю. Любой вопрос сопровождается перечислением изученных артефактов и форматом ответа.

## Подробности по шагам

### 1. Идея (`/idea-new`)
- Устанавливает активную фичу (`docs/.active_ticket`).
- Сразу запускайте `claude-workflow research --ticket <ticket> --auto` — CLI соберёт цели, сгенерирует `reports/research/<ticket>-targets.json` и подготовит `docs/research/<ticket>.md`; добавляйте ручные наблюдения через `--note "..."` или `--note @memo.md`.
- Автоматически создаёт черновик PRD по шаблону (`docs/prd/<ticket>.prd.md`, `Status: draft`), собирает вводные, риски и метрики.
- Саб-агент **analyst** сначала опирается на slug-hint (`docs/.active_feature`), PRD/research шаблоны и отчёты (`reports/research/*.json`), заполняет все разделы PRD по найденным данным, а вопросы пользователю формулирует только для пробелов, которые нельзя закрыть репозиторием.
- Каждая пара «Вопрос N»/«Ответ N» фиксируется в разделе `## Диалог analyst` вместе с перечислением проверенных артефактов; итоговый статус переводится в READY только после закрытия всех блокеров, незакрытые вопросы отражаются в `## 10. Открытые вопросы`.
- После диалога запускайте `claude-workflow analyst-check --ticket <ticket>` — команда проверит структуру вопросов/ответов и статус. При ошибке вернитесь к агенту и дополните информацию.

- CLI-команда `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph [--reuse-only] [--paths/--keywords/--langs/--graph-langs/--graph-filter/--graph-limit/--note]` собирает контекст: пути из `config/conventions.json`, `code_index` (символы/импорты/тесты), `reuse_candidates` и `call_graph`/`import_graph` (только Java/Kotlin через tree-sitter при наличии). По умолчанию call graph фильтруется по `<ticket>|<keywords>` и ограничивается 300 рёбрами (focus) в контексте; полный граф сохраняется в `reports/research/<ticket>-call-graph-full.json`. Результат сохраняется в `reports/research/<ticket>-targets.json` и `<ticket>-context.json`.
- Саб-агент **researcher** использует `code_index`/`reuse_candidates` и `call_graph`/`import_graph`, при необходимости дорасшифровывает связи в Claude Code, дополняет `rg "<ticket|feature>"`, `find`, `python`-скриптами, чтобы выявить интеграционные точки, тесты, миграции и долги. Все выводы оформляются в `docs/research/<ticket>.md` со ссылками на файлы/строки, команды и call graph; при отсутствии данных фиксируется baseline «Контекст пуст, требуется baseline» с перечислением уже просмотренных путей.
- Статус в отчёте должен стать `Status: reviewed`, критичные действия переносятся в план и `docs/tasklist/<ticket>.md`.
- При запуске с `--auto` Researcher отмечает нулевые совпадения (новые проекты), добавляет в шаблон блок «Контекст пуст, требуется baseline» и предлагает рекомендации (`profile.recommendations`) на основе `config/conventions.json`; такие отчёты можно временно оставлять в `Status: pending`, baseline фиксируется в `docs/research/<ticket>.md`.

### 3. План (`/plan-new`)
- Саб-агент **planner** формирует пошаговый план реализации по PRD: секция «Architecture & Patterns» (границы/паттерны KISS/YAGNI/DRY/SOLID, по умолчанию service layer + adapters/ports), reuse-точки из Researcher, итерации/DoD/риски.
- Саб-агент **validator** проверяет полноту; найденные вопросы возвращаются продукту.
- Все открытые вопросы синхронизируются между PRD и планом.

### 4. PRD Review (`/review-prd`)
- Саб-агент **prd-reviewer** проверяет полноту PRD, метрики, риски и соответствие ADR.
- Результат фиксируется в разделе `## PRD Review` (статус, summary, findings, action items) и в отчёте `reports/prd/<ticket>.json`.
- Блокирующие action items и открытые вопросы синхронизируются с планом и `docs/tasklist/<ticket>.md`.

### 5. Тасклист (`/tasks-new`)
- Преобразует план в чеклисты в `docs/tasklist/<ticket>.md`.
- Структурирует задачи по этапам (аналитика, разработка, QA, релиз).
- Добавляет критерии приёмки и зависимости.

### 6. Реализация (`/implement`)
- Саб-агент **implementer** следует шагам плана, учитывает выводы `docs/research/<ticket>.md` и PRD и вносит изменения малыми итерациями, опираясь на данные репозитория.
- После каждой правки автоматически запускается `.claude/hooks/format-and-test.sh` (управляется `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `STRICT_TESTS`). Любые ручные команды (`./gradlew test`, `gradle lint`, `claude-workflow progress --source implement --ticket <ticket>`) нужно перечислять в ответе с кратким результатом.
- Каждая итерация должна завершаться фиксацией прогресса в `docs/tasklist/<ticket>.md`: переведите релевантные пункты `- [ ] → - [x]`, обновите строку `Checkbox updated: …`, приложите ссылку на diff/команду и запустите `claude-workflow progress --source implement --ticket <ticket>`. Если утилита сообщает, что новых `- [x]` нет, вернитесь к чеклисту прежде чем завершать команду.
- Если включены дополнительные гейты (`config/gates.json`), следите за сообщениями `gate-workflow.sh`, `gate-prd-review.sh`, `gate-qa.sh`, `gate-tests.sh`, `gate-api-contract.sh` и `gate-db-migration.sh`.
- После отчётов QA/Review/Research добавляйте handoff-задачи командой `claude-workflow tasks-derive --source <qa|review|research> --append --ticket <ticket>` (новые `- [ ]` должны ссылаться на `reports/<source>/...`); при необходимости подтвердите прогресс `claude-workflow progress --source handoff --ticket <ticket>`.

### 7. Ревью (`/review`)
- Саб-агент **reviewer** проводит код-ревью и синхронизирует замечания в `docs/tasklist/<ticket>.md`.
- Reviewer сверяет, что выполненные пункты отмечены `- [x]`, обновляет строку `Checkbox updated: …` и при необходимости запускает `claude-workflow progress --source review --ticket <ticket>`, чтобы убедиться, что прогресс зафиксирован.
- Для запуска автотестов reviewer помечает маркер `reports/reviewer/<ticket>.json` командой `claude-workflow reviewer-tests --status required` (slug берётся из `docs/.active_ticket`). После успешного прогона обновите статус на `optional`, чтобы отключить авто‑запуск.
- При блокирующих проблемах фича возвращается на стадию реализации; при минорных — формируется список рекомендаций.

### 8. QA (`/qa`)
- Обязательная стадия перед релизом: запустите `/qa <ticket>` или `claude-workflow qa --ticket <ticket> --report reports/qa/<ticket>.json --gate`, чтобы сформировать отчёт и статус READY/WARN/BLOCKED.
- Саб-агент **qa** сопоставляет diff с чеклистом `docs/tasklist/<ticket>.md`, фиксирует найденные проблемы и рекомендации; гейт `gate-qa.sh` блокирует merge при blocker/critical или отсутствии отчёта.
- После статуса READY/WARN добавьте handoff-задачи из `reports/qa/<ticket>.json` через `claude-workflow tasks-derive --source qa --append --ticket <ticket>`, чтобы исполнитель видел все находки.
- Обновите QA-раздел tasklist (новые `- [x]`, дата/итерация, ссылки на логи) и выполните `claude-workflow progress --source qa --ticket <ticket>`.

## Автоматизация и гейты

- Пресет `strict` в `.claude/settings.json` включает pre-хуки (`gate-workflow.sh`, `gate-prd-review.sh`, `gate-api-contract.sh`, `gate-db-migration.sh`, `gate-qa.sh`, `gate-tests.sh`) и пост-хуки `.claude/hooks/format-and-test.sh` вместе с `.claude/hooks/lint-deps.sh`.
- `config/gates.json` управляет дополнительными проверками:
  - `api_contract` — при `true` ожидает наличие `docs/api/<ticket>.yaml` для контроллеров.
  - `db_migration` — при `true` требует новую миграцию в `src/main/resources/**/db/migration/`.
  - `prd_review` — контролирует раздел `## PRD Review`: разрешённые ветки, статус, блокирующие уровни и отчёт в `reports/prd/<ticket>.json`.
  - `researcher` — проверяет наличие `docs/research/<ticket>.md`, статус `Status: reviewed`, свежесть `reports/research/<ticket>-context.json` и заполненность `reports/research/<ticket>-targets.json`.
  - `analyst` — следит за блоком `## Диалог analyst`, наличием ответов `Ответ N` и запретом статуса READY при незакрытых вопросах; используется командой `claude-workflow analyst-check` и хуком `gate-workflow.sh`.
  - `qa` — запускает `scripts/qa-agent.py`, блокируя фичу при критичных/блокирующих находках.
  - `tests_required` — режим `disabled|soft|hard` для обязательных тестов.
  - `deps_allowlist` — включает проверку зависимостей через `scripts/lint-deps.sh`.
  - `feature_ticket_source` — путь к файлу с активным ticket (по умолчанию `docs/.active_ticket`); `feature_slug_hint_source` управляет slug-хинтом (`docs/.active_feature`).
  - `tasklist_progress` — гарантирует, что при изменениях в коде появляются новые `- [x]` в `docs/tasklist/<ticket>.md`. Гейт активен для `/implement`, `/qa`, `/review` и хука `gate-workflow.sh`; при технических задачах можно настроить `skip_branches` или временно выставить `CLAUDE_SKIP_TASKLIST_PROGRESS=1`.
- `SKIP_AUTO_TESTS=1` временно отключает форматирование и выборочные тесты.
- `STRICT_TESTS=1` заставляет `.claude/hooks/format-and-test.sh` завершаться ошибкой при падении тестов.

## Роли и ответственность команды

- **Product/Analyst** — поддерживает PRD, отвечает на вопросы planner/validator.
- **Researcher** — исследует кодовую базу, фиксирует reuse/риски, поддерживает `docs/research/<ticket>.md` и контекст для команды.
- **Tech Lead/Architect** — утверждает план, следит за гейтами и архитектурными решениями.
- **Разработчики** — реализуют по плану, поддерживают тесты и документацию в актуальном состоянии.
- **QA** — помогает с чеклистами в `docs/tasklist/<ticket>.md`, расширяет тестовое покрытие и сценарии ручной проверки, по итогам каждого цикла запускает `claude-workflow progress --source qa --ticket <ticket>` и фиксирует строку `Checkbox updated: …` в отчёте.
- **PRD reviewer** — утверждает готовность PRD, закрывает блокирующие вопросы до начала разработки.
- **Reviewer** — финализирует фичу, проверяет, что все чеклисты в `docs/tasklist/<ticket>.md` закрыты.

Следуйте этому циклу, чтобы команда оставалась синхронизированной, а артефакты — актуальными.
