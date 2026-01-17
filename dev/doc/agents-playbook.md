# Playbook агентов и барьеров Claude Code

Документ помогает быстро провести фичу через цикл Claude Code, понять роли саб-агентов и поведение гейтов. Следуйте последовательности, чтобы избегать блокирующих хуков и расхождений в артефактах.

> Ticket — основной идентификатор фичи, сохраняется в `aidd/docs/.active_ticket`. При необходимости указывайте slug-hint (человекочитаемый алиас) — он хранится в `aidd/docs/.active_feature` и используется в шаблонах/логах.
> Текущая стадия фиксируется в `aidd/docs/.active_stage` (`idea/research/plan/review-plan/review-prd/tasklist/implement/review/qa`); команды обновляют маркер и позволяют возвращаться к любому этапу.
> Команды/агенты/хуки поставляются как плагин `feature-dev-aidd` (`.claude-plugin/plugin.json`, файлы в `commands/`, `agents/`, `hooks/`); workspace `.claude/` содержит только настройки/кеш. Marketplace для автоподключения лежит в корне (`.claude-plugin/marketplace.json`), `.claude/settings.json` включает плагин.
> Базовые правила — в `aidd/AGENTS.md` (после `/feature-dev-aidd:aidd-init`); порядок стадий — в `aidd/docs/sdlc-flow.md`, статусы — в `aidd/docs/status-machine.md`.
> Рабочий контекст обновляется `context-gc` и хранится в `aidd/reports/context/latest_working_set.md`.
> Требования к структуре промптов агентов и слэш-команд описаны в `dev/doc/prompt-playbook.md`. При редактировании файлов в `agents|commands` сверяйтесь с плейбуком, чтобы сохранить единый формат `Контекст → Входы → Автоматизация → Пошаговый план → Fail-fast → Формат ответа` и правило `Checkbox updated`.
> Hook events определены в `hooks/hooks.json`: PreToolUse (context GC для Bash/Read), UserPromptSubmit (prompt guard), Stop/SubagentStop (`gate-workflow`, `gate-tests`, `gate-qa`, `format-and-test`, `lint-deps`). Скрипты вызываются через `${CLAUDE_PLUGIN_ROOT}/hooks/*.sh`.
> Все команды и хуки ожидают структуру `./aidd/**` (workspace = `--target .`); при запуске из другого каталога появится явная ошибка «aidd/docs not found».

## Agent-first принципы

- Каждый агент сначала **использует данные репозитория** (backlog, PRD, research, reports, tests, конфиги) и только потом задаёт вопросы пользователю. Вопросы фиксируются формально («что проверено → чего не хватает → формат ответа»).
- Чтение по умолчанию: если есть `*.pack.yaml` — читать pack; иначе начинать с stage‑anchors и `AIDD:CONTEXT_PACK`.
- Snippet‑first: сначала `rg` → `sed`, полный `Read` — крайний случай.
- В промптах и документации явно указывайте, какие команды доступны (`rg`, `pytest`, `npm test`, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh`) и как агент должен логировать результаты (пути, вывод команд, ссылки на отчёты).
- Любое действие должно приводить к обновлению артефакта: PRD, research, план, tasklist, diff, отчёт. Агент всегда сообщает, где записан результат.
- Если агент не имеет нужных прав (например, нет Bash-доступа к `rg`), он обязан перечислить альтернативы (чтение JSON/папок) и ссылаться на проверенные файлы перед тем, как объявить блокер.

## Ролевая цепочка

| Шаг | Команда | Агент(ы) | Основной вход | Основной выход | Готовность |
| --- | --- | --- | --- | --- | --- |
| 1 | `/feature-dev-aidd:idea-new <ticket> [slug-hint]` | `analyst` | Свободная идея, вводные, ограничения | `aidd/docs/.active_ticket`, `aidd/docs/prd/<ticket>.prd.md` | PRD заполнен, статус READY/BLOCKED выставлен |
| 2 | `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket>` → `/feature-dev-aidd:researcher <ticket>` | `researcher` | PRD + AIDD:RESEARCH_HINTS, backlog, целевые модули | `aidd/docs/research/<ticket>.md`, `aidd/reports/research/<ticket>-context.json` | Status: reviewed, пути интеграции подтверждены |
| 3 | `/feature-dev-aidd:plan-new <ticket>` | `planner`, `validator` | PRD READY, отчёт Researcher, результаты `research-check` | `aidd/docs/plan/<ticket>.md`, протокол проверки | План покрывает модули из research, критичные риски закрыты |
| 4 | `/feature-dev-aidd:review-spec <ticket>` | `plan-reviewer` | План, PRD, Researcher | Раздел `## Plan Review` в плане | Status: READY, блокеры закрыты |
| 5 | `/feature-dev-aidd:review-spec <ticket>` | `prd-reviewer` | PRD, план, ADR, Researcher | Раздел `## PRD Review`, отчёт `aidd/reports/prd/<ticket>.json` | Status: READY, action items перенесены |
| 6 | `/feature-dev-aidd:tasks-new <ticket>` | — | Утверждённый план | Обновлённый `aidd/docs/tasklist/<ticket>.md` | Чеклисты привязаны к ticket (slug-hint) и этапам |
| 7 | `/feature-dev-aidd:implement <ticket>` | `implementer` | План, `aidd/docs/tasklist/<ticket>.md`, отчёт Researcher | Кодовые изменения + формат/тесты на Stop/SubagentStop при стадии `implement` | Гейты разрешают правки, тесты зелёные |
| 8 | `/feature-dev-aidd:review <ticket>` | `reviewer` | Готовая ветка и артефакты | Замечания в `aidd/docs/tasklist/<ticket>.md`, итоговый статус | Все блокеры сняты, чеклисты закрыты |
| 9 | `Claude: Run agent → qa` / `gate-qa.sh` | `qa` | Diff, `aidd/docs/tasklist/<ticket>.md`, результаты гейтов | JSON-отчёт `aidd/reports/qa/<ticket>.json`, статус READY/WARN/BLOCKED | Нет блокеров, warnings зафиксированы |

> Review-plan и review-prd выполняются одной командой `/feature-dev-aidd:review-spec <ticket>`.

## Агенты и ожидаемые результаты

### analyst — аналитика идеи
- **Вызов:** `/feature-dev-aidd:idea-new <ticket> [slug-hint]`
- **Вход:** slug-hint пользователя (`aidd/docs/.active_feature`) + имеющиеся данные из репозитория (backlog, ADR, `aidd/reports/research/*.json`, если уже запускали research).
- **Перед стартом:** убедитесь, что активный ticket задан; если research отсутствует, фиксируйте `## AIDD:RESEARCH_HINTS` и передавайте задачу `/feature-dev-aidd:researcher`.
- **Автошаблон:** `/feature-dev-aidd:idea-new` автоматически создаёт `aidd/docs/prd/<ticket>.prd.md` со статусом `Status: draft`. Агент заполняет PRD на основе найденных артефактов (поиск `rg <ticket>` по backlog/docs, чтение `aidd/reports/research/*.json` при наличии), фиксируя источник каждой гипотезы; статус READY ставится после ответов пользователя.
- **Процесс:** аналитик собирает факты из репозитория (цели, метрики, ограничения, reuse), фиксирует `## AIDD:RESEARCH_HINTS` (paths/keywords/notes) для researcher. Вопросы пользователю формулируются только после перечисления просмотренных файлов/команд и в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`, ответы фиксируются как `Ответ N: ...`.
- **Выход:** PRD `aidd/docs/prd/<ticket>.prd.md` с заполненными секциями (цели, сценарии, требования, риски), ссылками на источники (backlog, reports, ответы), блоком `## Диалог analyst` и `## AIDD:RESEARCH_HINTS`.
- **Готовность:** `Status: READY`, `## 10. Открытые вопросы` пуст или содержит только ссылки на план/тасклист, `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh --ticket <ticket>` проходит без ошибок. Если хотя бы один ответ отсутствует, PRD остаётся `Status: BLOCKED`.

### researcher — исследование кодовой базы
- **Вызов:** `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket> --auto --deep-code --call-graph [--reuse-only] [--paths/--keywords/--langs/--graph-langs/--note]`, затем агент `/feature-dev-aidd:researcher <ticket>`.
- **Вход:** PRD (включая `## AIDD:RESEARCH_HINTS`), slug-hint, `aidd/reports/research/<ticket>-targets.json`, `aidd/reports/research/<ticket>-context.json` (`code_index`, `reuse_candidates`, `call_graph` для поддерживаемых языков, `import_graph`), связанные ADR/PR, тестовые каталоги.
- **Процесс:** исследователь обновляет JSON-контекст, использует `code_index` и `call_graph`/`import_graph` (tree-sitter language pack для поддерживаемых языков; при отсутствии грамматики граф пуст с предупреждением), при необходимости дорасшифровывает связи в Claude Code, обходит каталоги с помощью `rg/find/python`, фиксирует сервисы, API, тесты, миграции. Call graph в контексте — focus (по умолчанию фильтр `<ticket>|<keywords>`, лимит 300 рёбер), полный граф сохраняется отдельно в `aidd/reports/research/<ticket>-call-graph-full.json`. Все находки сопровождаются ссылками на строки/команды; отсутствие тестов — отдельный риск. Вопросы пользователю формулируются только после перечисления просмотренных артефактов.
- **Выход:** `aidd/docs/research/<ticket>.md` со статусом `Status: reviewed` (или `pending` с baseline), заполненными секциями «где встроить», «что переиспользуем» (как/риски/тесты/контракты), «паттерны/анти-паттерны», графом вызовов/импортов (если применимо) и рекомендациями, импортированными в план/тасклист.
- **Готовность:** отчёт описывает точки интеграции, reuse и риски; action items перенесены в план/тасклист; `aidd/reports/research/<ticket>-context.json` свежий, baseline помечен текстом «Контекст пуст, требуется baseline» и список недостающих данных понятен.

### planner — план реализации
- **Вызов:** `/feature-dev-aidd:plan-new <ticket>`
- **Вход:** актуальный PRD и ответы на вопросы аналитика.
- **Выход:** `aidd/docs/plan/<ticket>.md` с декомпозицией на итерации, DoD и ссылками на модули/файлы.
- **Особенности:** используй вывод Researcher как опорный список модулей и reuse; сразу после генерации план проходит проверку агентом `validator`, открытые вопросы синхронизируются в PRD.

### validator — проверка плана
- **Вызов:** автоматически внутри `/feature-dev-aidd:plan-new`.
- **Вход:** черновой план.
- **Выход:** статус READY/BLOCKED/PENDING, список уточняющих вопросов и рисков.
- **Готовность:** все критичные вопросы закрыты или перенесены в backlog; рекомендации Researcher учтены, план можно отдавать на `/feature-dev-aidd:review-spec`.

### plan-reviewer — ревью плана
- **Вызов:** `/feature-dev-aidd:review-spec <ticket>` (этап `review-plan`)
- **Вход:** `aidd/docs/plan/<ticket>.md`, PRD, research, ADR (если есть).
- **Выход:** Раздел `## Plan Review` с `Status: READY|BLOCKED|PENDING`.
- **Особенности:** фиксируй исполняемость, корректность границ модулей, тестовую стратегию и риски; блокеры устраняются до PRD review и `/feature-dev-aidd:tasks-new`.

### prd-reviewer — контроль качества PRD
- **Вызов:** `/feature-dev-aidd:review-spec <ticket>` (этап `review-prd`)
- **Вход:** `aidd/docs/prd/<ticket>.prd.md`, `aidd/docs/plan/<ticket>.md`, актуальные ADR, открытые вопросы.
- **Выход:** Раздел `## PRD Review` с `Status: READY|BLOCKED|PENDING`, summary, findings и action items; отчёт `aidd/reports/prd/<ticket>.json`.
- **Особенности:** блокирующие замечания фиксируйте как `Status: BLOCKED` и переносите action items в `aidd/docs/tasklist/<ticket>.md`; проверяйте, что `aidd/docs/research/<ticket>.md` имеет `Status: reviewed`. Без `READY` гейт `gate-workflow` не даст менять код.

### tasks-new — чеклист команды
- **Команда:** `/feature-dev-aidd:tasks-new <ticket>`
- **Выход:** обновлённый `aidd/docs/tasklist/<ticket>.md` с задачами на аналитику, разработку, QA и релиз.
- **Готовность:** чеклисты отражают фактический план, каждая задача содержит критерий приёмки.

### implementer — реализация
- **Вызов:** `/feature-dev-aidd:implement <ticket>`
- **Вход:** утверждённый план, `aidd/docs/tasklist/<ticket>.md`, `aidd/docs/research/<ticket>.md`, PRD, актуальный diff.
- **Процесс:** агент выбирает следующий пункт из `AIDD:NEXT_3` (лимит: 1 чекбокс или 2 тесно связанных), начинает с `AIDD:CONTEXT_PACK` и working set, читает связанные файлы и реализует минимальный diff. Перед правками создаёт `aidd/.cache/test-policy.env` с профилем проверок. На Stop/SubagentStop запускается `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` **только при стадии `implement`** (управляется `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`, `AIDD_TEST_PROFILE`, `AIDD_TEST_TASKS`, `AIDD_TEST_FILTERS`, `AIDD_TEST_FORCE`). Все ручные команды (например, `pytest`, `npm test`, `go test`, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source implement --ticket <ticket>`) перечисляются в ответе вместе с результатом.
- **Тесты:** по умолчанию профиль `fast`; используйте `targeted` для узких прогонов и `full` для изменений общих конфигов/ядра. Не повторяйте прогон без изменения diff; для повторного запуска используйте `AIDD_TEST_FORCE=1` и объясните причину.
- **Коммуникация:** вопросы пользователю задаются только после того, как агент перечислил проверенные артефакты (план, research, код, тесты) и пояснил, какой информации не хватает.
- **Прогресс:** каждую итерацию переводите релевантные пункты `- [ ] → - [x]`, добавляйте строку `Checkbox updated: …`, фиксируйте дату/итерацию и запускайте `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source implement --ticket <ticket>` — команда отследит, появились ли новые `- [x]`. `gate-workflow` и `gate-tests` отображают статусы и блокируют push при нарушениях.

### reviewer — код-ревью
- **Вызов:** `/feature-dev-aidd:review <ticket>`
- **Вход:** готовая ветка, PRD, план, `aidd/docs/tasklist/<ticket>.md`.
- **Выход:** отчёт об обнаруженных проблемах и рекомендации; чеклисты обновлены состоянием READY/BLOCKED.
- **Готовность:** все блокирующие замечания устранены, финальный статус — READY.
- **Тесты:** используйте `${CLAUDE_PLUGIN_ROOT}/tools/reviewer-tests.sh --status required [--ticket <ticket>]`, чтобы запросить автотесты. После выполнения обновите маркер на `optional`, иначе `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` будет запускать тесты автоматически.
- **Прогресс:** убедитесь, что отмечены выполненные пункты `- [x]`, добавьте строку `Checkbox updated: …` с перечислением закрытых чекбоксов и при необходимости выполните `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source review --ticket <ticket>`.

### qa — финальная проверка качества
- **Вызов:** `/feature-dev-aidd:qa <ticket>` (обязательная стадия после `/feature-dev-aidd:review`), либо `${CLAUDE_PLUGIN_ROOT}/tools/qa.sh --ticket <ticket> --report aidd/reports/qa/<ticket>.json --gate` / `${CLAUDE_PLUGIN_ROOT}/hooks/gate-qa.sh`.
- **Вход:** активная фича, diff, результаты гейтов, раздел QA в `aidd/docs/tasklist/<ticket>.md`.
- **Выход:** структурированный отчёт (severity, scope, рекомендации), JSON `aidd/reports/qa/<ticket>.json`, обновлённый чеклист.
- **Особенности:** гейт `gate-qa.sh` блокирует релиз при `blocker`/`critical`, см. `dev/doc/qa-playbook.md` для чеклистов и переменных окружения.
- **Handoff:** после статуса READY/WARN вызовите `${CLAUDE_PLUGIN_ROOT}/tools/tasks-derive.sh --source qa --append --ticket <ticket>` — новые `- [ ]` в tasklist должны содержать ссылку на `aidd/reports/qa/<ticket>.json`.
- **Прогресс:** после каждой регрессии фиксируйте, какие чекбоксы закрыты (`Checkbox updated: …`), и запускайте `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source qa --ticket <ticket>`, чтобы хук `gate-workflow.sh` не блокировал правки.

## Работа с барьерами

- `gate-workflow.sh` активен на Stop/SubagentStop и блокирует `src/**`, пока не готовы PRD, план, review-plan, PRD review и `aidd/docs/tasklist/<ticket>.md`. Он также проверяет, что после изменений появились новые `- [x]` (гейт `tasklist_progress`); для handoff допускаются новые `- [ ]` с ссылкой на отчёт при вызове `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh --source handoff`. Если стадия задана, правки кода разрешены только на `implement/review/qa`.
- Дополнительные проверки настраиваются в `aidd/config/gates.json`:
  - `tests_required`: `disabled` / `soft` / `hard` — предупреждение или блокировка при отсутствии тестов.
- Сообщения гейтов содержат подсказки (какой файл создать, как отключить проверку).

## Автоформатирование и тесты

- Пресет `strict` запускает `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` на Stop/SubagentStop **и только при стадии `implement`**. Скрипт анализирует diff, форматирует код и выполняет выборочные задачи тест-раннера/CLI.
- Управляйте поведением через переменные окружения: `SKIP_AUTO_TESTS=1` — пауза, `FORMAT_ONLY=1` — форматирование без тестов, `TEST_SCOPE="task1,task2"` — задать конкретные задачи и выключить режим changed-only, `TEST_CHANGED_ONLY=0` — форсировать полный прогон, `STRICT_TESTS=1` — падать при первых ошибках. Для обхода stage check используйте `CLAUDE_SKIP_STAGE_CHECKS=1`.
- Дефолтный профиль можно задать через `AIDD_TEST_PROFILE_DEFAULT` (например, fast на SubagentStop и targeted на Stop); явная политика из `aidd/.cache/test-policy.env` имеет приоритет.
- Логи тестов пишутся в `aidd/.cache/logs/format-and-test.<timestamp>.log`; режим вывода: `AIDD_TEST_LOG=summary|full`, хвост при падении — `AIDD_TEST_LOG_TAIL_LINES`.
- Для ручного запуска выполните `bash "${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh"` (команда учитывает те же переменные) и исправьте замечания перед продолжением работы.

## Чеклист быстрого старта фичи

1. Создайте ветку (`git checkout -b feature/<TICKET>`) и запустите `/feature-dev-aidd:idea-new <ticket> [slug-hint]` — команда зафиксирует ticket в `aidd/docs/.active_ticket`, при необходимости сохранит slug-хинт в `aidd/docs/.active_feature` **и автоматически создаст PRD `aidd/docs/prd/<ticket>.prd.md` со статусом `Status: draft`, который нужно довести до READY.**
2. Выполните `/feature-dev-aidd:plan-new`, затем `/feature-dev-aidd:review-spec`, после чего запустите `/feature-dev-aidd:tasks-new`, пока артефакты не получат статус READY.
3. При необходимости включите дополнительные гейты (`aidd/config/gates.json`) и подготовьте связанные артефакты: миграции, OpenAPI, дополнительные тесты.
4. Реализуйте фичу через `/feature-dev-aidd:implement`, следя за сообщениями `gate-workflow` и выбранных гейтов; фиксируйте прогресс в `aidd/docs/tasklist/<ticket>.md`.
5. Запросите `/feature-dev-aidd:review`, когда чеклисты закрыты, автотесты зелёные и артефакты синхронизированы.

Используйте этот playbook как основу и дополняйте его корпоративными процессами (release notes, ADR, демо). Если нужны расширенные команды или агенты, добавляйте их напрямую в `commands/` и `agents/`.
