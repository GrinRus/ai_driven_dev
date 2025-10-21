# Workflow Claude Code

Документ описывает целевой процесс работы команды после запуска `init-claude-workflow.sh`. Цикл строится вокруг идеи и проходит семь этапов: **идея → research → план → PRD review → задачи → реализация → ревью**. На каждом шаге задействованы специализированные саб-агенты Claude Code и защитные хуки, которые помогают удерживать кодовую базу в рабочем состоянии.

## Обзор этапов

| Этап | Команда | Саб-агент | Основные артефакты |
| --- | --- | --- | --- |
| Аналитика идеи | `/idea-new <slug> [TICKET]` | `analyst` | `docs/prd/<slug>.prd.md`, активная фича |
| Research | `claude-workflow research --feature <slug>` → `/researcher <slug>` | `researcher` | `docs/research/<slug>.md`, `reports/research/<slug>-targets.json` |
| Планирование | `/plan-new <slug>` | `planner`, `validator` | `docs/plan/<slug>.md`, уточнённые вопросы |
| PRD review | `/review-prd <slug>` | `prd-reviewer` | `docs/prd/<slug>.prd.md`, отчёт `reports/prd/<slug>.json` |
| Тасклист | `/tasks-new <slug>` | — | `docs/tasklist/<slug>.md` (обновлённые чеклисты) |
| Реализация | `/implement <slug>` | `implementer` | кодовые изменения, актуальные тесты |
| Ревью | `/review <slug>` | `reviewer` | замечания в `docs/tasklist/<slug>.md`, итоговый статус |

## Подробности по шагам

### 1. Идея (`/idea-new`)
- Устанавливает активную фичу (`docs/.active_feature`).
- Создаёт PRD по шаблону (`docs/prd/<slug>.prd.md`), собирает вводные, риски и метрики.
- Саб-агент **analyst** стартует с `Вопрос 1`, ждёт `Ответ 1` и продолжает цикл уточнений, пока не закроет блокирующие неопределённости.
- Каждая пара «Вопрос N»/«Ответ N» фиксируется в разделе `## Диалог analyst`, итоговый статус переводится в READY только после полного комплекта ответов; незакрытые вопросы отражаются в `## 10. Открытые вопросы`.
- После диалога запускайте `claude-workflow analyst-check --feature <slug>` — команда проверит формат вопросов/ответов и статус. При ошибке вернитесь к агенту и дополните информацию.

### 2. Research (`claude-workflow research` + `/researcher`)
- CLI-команда `claude-workflow research --feature <slug>` собирает контекст: пути из `config/conventions.json`, существующие модули и документацию. Результат сохраняется в `reports/research/<slug>-targets.json` и `<slug>-context.json`.
- Саб-агент **researcher** оформляет отчёт в `docs/research/<slug>.md`: куда встраивать изменения, что переиспользовать, какие риски учесть; добавьте ссылку на этот отчёт в PRD и `docs/tasklist/<slug>.md`, чтобы команда видела актуальные рекомендации.
- Статус в отчёте должен стать `Status: reviewed`, критичные действия переносятся в план и `docs/tasklist/<slug>.md`.

### 3. План (`/plan-new`)
- Саб-агент **planner** формирует пошаговый план реализации по PRD.
- Саб-агент **validator** проверяет полноту; найденные вопросы возвращаются продукту.
- Все открытые вопросы синхронизируются между PRD и планом.

### 4. PRD Review (`/review-prd`)
- Саб-агент **prd-reviewer** проверяет полноту PRD, метрики, риски и соответствие ADR.
- Результат фиксируется в разделе `## PRD Review` (статус, summary, findings, action items) и в отчёте `reports/prd/<slug>.json`.
- Блокирующие action items и открытые вопросы синхронизируются с планом и `docs/tasklist/<slug>.md`.

### 5. Тасклист (`/tasks-new`)
- Преобразует план в чеклисты в `docs/tasklist/<slug>.md`.
- Структурирует задачи по этапам (аналитика, разработка, QA, релиз).
- Добавляет критерии приёмки и зависимости.

### 6. Реализация (`/implement`)
- Саб-агент **implementer** следует шагам плана и вносит изменения малыми итерациями.
- После каждой правки автоматически запускается `.claude/hooks/format-and-test.sh` (отключаемо через `SKIP_AUTO_TESTS=1`).
- Если включены дополнительные гейты (`config/gates.json`), следите за сообщениями `gate-workflow.sh`, `gate-prd-review.sh`, `gate-qa.sh`, `gate-tests.sh`, `gate-api-contract.sh` и `gate-db-migration.sh`.

### 7. Ревью (`/review`)
- Саб-агент **reviewer** проводит код-ревью и синхронизирует замечания в `docs/tasklist/<slug>.md`.
- При блокирующих проблемах фича возвращается на стадию реализации; при минорных — формируется список рекомендаций.

## Автоматизация и гейты

- Пресет `strict` в `.claude/settings.json` включает pre-хуки (`gate-workflow.sh`, `gate-prd-review.sh`, `gate-api-contract.sh`, `gate-db-migration.sh`, `gate-qa.sh`, `gate-tests.sh`) и пост-хуки `.claude/hooks/format-and-test.sh` вместе с `.claude/hooks/lint-deps.sh`.
- `config/gates.json` управляет дополнительными проверками:
  - `api_contract` — при `true` ожидает наличие `docs/api/<slug>.yaml` для контроллеров.
  - `db_migration` — при `true` требует новую миграцию в `src/main/resources/**/db/migration/`.
  - `prd_review` — контролирует раздел `## PRD Review`: разрешённые ветки, статус, блокирующие уровни и отчёт в `reports/prd/<slug>.json`.
  - `researcher` — проверяет наличие `docs/research/<slug>.md`, статус `Status: reviewed`, свежесть `reports/research/<slug>-context.json` и заполненность `reports/research/<slug>-targets.json`.
  - `analyst` — следит за блоком `## Диалог analyst`, наличием ответов `Ответ N` и запретом статуса READY при незакрытых вопросах; используется командой `claude-workflow analyst-check` и хуком `gate-workflow.sh`.
  - `qa` — запускает `scripts/qa-agent.py`, блокируя фичу при критичных/блокирующих находках.
  - `tests_required` — режим `disabled|soft|hard` для обязательных тестов.
  - `deps_allowlist` — включает проверку зависимостей через `scripts/lint-deps.sh`.
  - `feature_slug_source` — путь к файлу с активной фичей (по умолчанию `docs/.active_feature`).
- `SKIP_AUTO_TESTS=1` временно отключает форматирование и выборочные тесты.
- `STRICT_TESTS=1` заставляет `.claude/hooks/format-and-test.sh` завершаться ошибкой при падении тестов.

## Роли и ответственность команды

- **Product/Analyst** — поддерживает PRD, отвечает на вопросы planner/validator.
- **Researcher** — исследует кодовую базу, фиксирует reuse/риски, поддерживает `docs/research/<slug>.md` и контекст для команды.
- **Tech Lead/Architect** — утверждает план, следит за гейтами и архитектурными решениями.
- **Разработчики** — реализуют по плану, поддерживают тесты и документацию в актуальном состоянии.
- **QA** — помогает с чеклистами в `docs/tasklist/<slug>.md`, расширяет тестовое покрытие и сценарии ручной проверки.
- **PRD reviewer** — утверждает готовность PRD, закрывает блокирующие вопросы до начала разработки.
- **Reviewer** — финализирует фичу, проверяет, что все чеклисты в `docs/tasklist/<slug>.md` закрыты.

Следуйте этому циклу, чтобы команда оставалась синхронизированной, а артефакты — актуальными.
