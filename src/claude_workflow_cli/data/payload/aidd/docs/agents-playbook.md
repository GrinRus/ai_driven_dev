# Playbook агентов и барьеров Claude Code

Документ помогает быстро провести фичу через цикл Claude Code, понять роли саб-агентов и поведение гейтов. Следуйте последовательности, чтобы избегать блокирующих хуков и расхождений в артефактах.

> Ticket — основной идентификатор фичи, сохраняется в `aidd/docs/.active_ticket`. При необходимости указывайте slug-hint (человекочитаемый алиас) — он хранится в `aidd/docs/.active_feature` и используется в шаблонах/логах.
> Текущая стадия фиксируется в `aidd/docs/.active_stage` (`idea/research/plan/review-plan/review-prd/tasklist/implement/review/qa`); команды обновляют маркер и позволяют возвращаться к любому этапу.
> Команды/агенты/хуки поставляются как плагин `feature-dev-aidd` (`aidd/.claude-plugin/plugin.json`, файлы в `aidd/{commands,agents,hooks}`); runtime `.claude/` содержит только настройки/кеш, EN‑локаль — в `aidd/prompts/en/**`. Marketplace для автоподключения лежит в корне (`.claude-plugin/marketplace.json`), root `.claude/settings.json` включает плагин.
> Базовые правила — в `aidd/AGENTS.md`; порядок стадий — в `aidd/docs/sdlc-flow.md`, статусы — в `aidd/docs/status-machine.md`.
> Требования к структуре промптов агентов и слэш-команд описаны в `aidd/docs/prompt-playbook.md`. При редактировании файлов в `aidd/agents|commands` и `aidd/prompts/en/agents|commands` сверяйтесь с плейбуком, чтобы сохранить единый формат `Контекст → Входы → Автоматизация → Пошаговый план → Fail-fast → Формат ответа` и правило `Checkbox updated`. EN локализации синхронизируются по правилам `aidd/docs/prompt-versioning.md`.
> Hook events определены в `aidd/hooks/hooks.json`: PreToolUse (context GC для Bash/Read), UserPromptSubmit (prompt guard), Stop/SubagentStop (`gate-workflow`, `gate-tests`, `gate-qa`, `format-and-test`, `lint-deps`). Скрипты вызываются через `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/*.sh`.
> Все команды и хуки ожидают структуру `./aidd/**` (workspace = `--target .`); при запуске из другого каталога появится явная ошибка «aidd/docs not found».

## Agent-first принципы

- Каждый агент сначала **использует данные репозитория** (backlog, PRD, research, reports, tests, конфиги) и только потом задаёт вопросы пользователю. Вопросы фиксируются формально («что проверено → чего не хватает → формат ответа»).
- В промптах и документации явно указывайте, какие команды доступны (`rg`, `pytest`, `npm test`, `claude-workflow progress`) и как агент должен логировать результаты (пути, вывод команд, ссылки на отчёты).
- Любое действие должно приводить к обновлению артефакта: PRD, research, план, tasklist, diff, отчёт. Агент всегда сообщает, где записан результат.
- Если агент не имеет нужных прав (например, нет Bash-доступа к `rg`), он обязан перечислить альтернативы (чтение JSON/папок) и ссылаться на проверенные файлы перед тем, как объявить блокер.

## Ролевая цепочка

| Шаг | Команда | Агент(ы) | Основной вход | Основной выход | Готовность |
| --- | --- | --- | --- | --- | --- |
| 1 | `/idea-new <ticket> [slug-hint]` | `analyst` | Свободная идея, вводные, ограничения | `aidd/docs/.active_ticket`, `aidd/docs/prd/<ticket>.prd.md` | PRD заполнен, статус READY/BLOCKED выставлен |
| 2 | `claude-workflow research --ticket <ticket>` → `/researcher <ticket>` (по требованию) | `researcher` | PRD, backlog, целевые модули | `aidd/docs/research/<ticket>.md`, `reports/research/<ticket>-context.json` | Status: reviewed, пути интеграции подтверждены |
| 3 | `/plan-new <ticket>` | `planner`, `validator` | PRD, отчёт Researcher, ответы на вопросы | `aidd/docs/plan/<ticket>.md`, протокол проверки | План покрывает модули из research, критичные риски закрыты |
| 4 | `/review-plan <ticket>` | `plan-reviewer` | План, PRD, Researcher | Раздел `## Plan Review` в плане | Status: READY, блокеры закрыты |
| 5 | `/review-prd <ticket>` | `prd-reviewer` | PRD, план, ADR, Researcher | Раздел `## PRD Review`, отчёт `reports/prd/<ticket>.json` | Status: READY, action items перенесены |
| 6 | `/tasks-new <ticket>` | — | Утверждённый план | Обновлённый `aidd/docs/tasklist/<ticket>.md` | Чеклисты привязаны к ticket (slug-hint) и этапам |
| 7 | `/implement <ticket>` | `implementer` | План, `aidd/docs/tasklist/<ticket>.md`, отчёт Researcher | Кодовые изменения + формат/тесты на Stop/SubagentStop при стадии `implement` | Гейты разрешают правки, тесты зелёные |
| 8 | `/review <ticket>` | `reviewer` | Готовая ветка и артефакты | Замечания в `aidd/docs/tasklist/<ticket>.md`, итоговый статус | Все блокеры сняты, чеклисты закрыты |
| 9 | `Claude: Run agent → qa` / `gate-qa.sh` | `qa` | Diff, `aidd/docs/tasklist/<ticket>.md`, результаты гейтов | JSON-отчёт `reports/qa/<ticket>.json`, статус READY/WARN/BLOCKED | Нет блокеров, warnings зафиксированы |

## Агенты и ожидаемые результаты

### analyst — аналитика идеи
- **Вызов:** `/idea-new <ticket> [slug-hint]`
- **Вход:** slug-hint пользователя (`aidd/docs/.active_feature`) + имеющиеся данные из репозитория (backlog, ADR, `reports/research/*.json`, если уже запускали research).
- **Перед стартом:** убедитесь, что активный ticket задан; если research отсутствует или устарел, инициируйте `/researcher` или `claude-workflow research --auto` и дождитесь baseline/обновления.
- **Автошаблон:** `/idea-new` автоматически создаёт `aidd/docs/prd/<ticket>.prd.md` со статусом `Status: draft`. Агент заполняет PRD на основе найденных артефактов (поиск `rg <ticket>` по backlog/docs, чтение `reports/research/*.json`), фиксируя источник каждой гипотезы; статус READY ставится только при свежем `docs/research/<ticket>.md: Status reviewed` (кроме baseline-пустых проектов).
- **Процесс:** аналитик собирает факты из репозитория (цели, метрики, ограничения, reuse), при нехватке контекста запускает research и возвращается к PRD. Вопросы пользователю формулируются только после перечисления просмотренных файлов/команд и в формате `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default`, ответы фиксируются как `Ответ N: ...`.
- **Выход:** PRD `aidd/docs/prd/<ticket>.prd.md` с заполненными секциями (цели, сценарии, требования, риски), ссылками на источники (backlog, research, reports, ответы) и актуальным блоком `## Диалог analyst`.
- **Готовность:** `Status: READY`, `## 10. Открытые вопросы` пуст или содержит только ссылки на план/тасклист, `claude-workflow analyst-check --ticket <ticket>` проходит без ошибок. Если хотя бы один ответ отсутствует, PRD остаётся `Status: BLOCKED`.

### researcher — исследование кодовой базы
- **Вызов:** `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph [--reuse-only] [--paths/--keywords/--langs/--graph-langs/--note]`, затем агент `/researcher <ticket>`.
- **Вход:** PRD, slug-hint, `reports/research/<ticket>-targets.json`, `reports/research/<ticket>-context.json` (`code_index`, `reuse_candidates`, `call_graph` для поддерживаемых языков, `import_graph`), связанные ADR/PR, тестовые каталоги.
- **Процесс:** исследователь обновляет JSON-контекст, использует `code_index` и `call_graph`/`import_graph` (tree-sitter language pack для поддерживаемых языков; при отсутствии грамматики граф пуст с предупреждением), при необходимости дорасшифровывает связи в Claude Code, обходит каталоги с помощью `rg/find/python`, фиксирует сервисы, API, тесты, миграции. Call graph в контексте — focus (по умолчанию фильтр `<ticket>|<keywords>`, лимит 300 рёбер), полный граф сохраняется отдельно в `reports/research/<ticket>-call-graph-full.json`. Все находки сопровождаются ссылками на строки/команды; отсутствие тестов — отдельный риск. Вопросы пользователю формулируются только после перечисления просмотренных артефактов.
- **Выход:** `aidd/docs/research/<ticket>.md` со статусом `Status: reviewed` (или `pending` с baseline), заполненными секциями «где встроить», «что переиспользуем» (как/риски/тесты/контракты), «паттерны/анти-паттерны», графом вызовов/импортов (если применимо) и рекомендациями, импортированными в план/тасклист.
- **Готовность:** отчёт описывает точки интеграции, reuse и риски; action items перенесены в план/тасклист; `reports/research/<ticket>-context.json` свежий, baseline помечен текстом «Контекст пуст, требуется baseline» и список недостающих данных понятен.

### planner — план реализации
- **Вызов:** `/plan-new <ticket>`
- **Вход:** актуальный PRD и ответы на вопросы аналитика.
- **Выход:** `aidd/docs/plan/<ticket>.md` с декомпозицией на итерации, DoD и ссылками на модули/файлы.
- **Особенности:** используй вывод Researcher как опорный список модулей и reuse; сразу после генерации план проходит проверку агентом `validator`, открытые вопросы синхронизируются в PRD.

### validator — проверка плана
- **Вызов:** автоматически внутри `/plan-new`.
- **Вход:** черновой план.
- **Выход:** статус READY/BLOCKED/PENDING, список уточняющих вопросов и рисков.
- **Готовность:** все критичные вопросы закрыты или перенесены в backlog; рекомендации Researcher учтены, план можно отдавать на review-plan.

### plan-reviewer — ревью плана
- **Вызов:** `/review-plan <ticket>`
- **Вход:** `aidd/docs/plan/<ticket>.md`, PRD, research, ADR (если есть).
- **Выход:** Раздел `## Plan Review` с `Status: READY|BLOCKED|PENDING`.
- **Особенности:** фиксируй исполняемость, корректность границ модулей, тестовую стратегию и риски; блокеры устраняются до `review-prd` и `tasks-new`.

### prd-reviewer — контроль качества PRD
- **Вызов:** `/review-prd <ticket>`
- **Вход:** `aidd/docs/prd/<ticket>.prd.md`, `aidd/docs/plan/<ticket>.md`, актуальные ADR, открытые вопросы.
- **Выход:** Раздел `## PRD Review` с `Status: READY|BLOCKED|PENDING`, summary, findings и action items; отчёт `reports/prd/<ticket>.json`.
- **Особенности:** блокирующие замечания фиксируйте как `Status: BLOCKED` и переносите action items в `aidd/docs/tasklist/<ticket>.md`; проверяйте, что `aidd/docs/research/<ticket>.md` имеет `Status: reviewed`. Без `READY` гейт `gate-workflow` не даст менять код.

### tasks-new — чеклист команды
- **Команда:** `/tasks-new <ticket>`
- **Выход:** обновлённый `aidd/docs/tasklist/<ticket>.md` с задачами на аналитику, разработку, QA и релиз.
- **Готовность:** чеклисты отражают фактический план, каждая задача содержит критерий приёмки.

### implementer — реализация
- **Вызов:** `/implement <ticket>`
- **Вход:** утверждённый план, `aidd/docs/tasklist/<ticket>.md`, `aidd/docs/research/<ticket>.md`, PRD, актуальный diff.
- **Процесс:** агент выбирает следующий пункт из `Next 3`, читает связанные файлы и реализует минимальный diff. На Stop/SubagentStop запускается `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh` **только при стадии `implement`** (управляется `SKIP_AUTO_TESTS`, `FORMAT_ONLY`, `TEST_SCOPE`). Все ручные команды (например, `pytest`, `npm test`, `go test`, `claude-workflow progress --source implement --ticket <ticket>`) перечисляются в ответе вместе с результатом.
- **Коммуникация:** вопросы пользователю задаются только после того, как агент перечислил проверенные артефакты (план, research, код, тесты) и пояснил, какой информации не хватает.
- **Прогресс:** каждую итерацию переводите релевантные пункты `- [ ] → - [x]`, добавляйте строку `Checkbox updated: …`, фиксируйте дату/итерацию и запускайте `claude-workflow progress --source implement --ticket <ticket>` — команда отследит, появились ли новые `- [x]`. `gate-workflow` и `gate-tests` отображают статусы и блокируют push при нарушениях.

### reviewer — код-ревью
- **Вызов:** `/review <ticket>`
- **Вход:** готовая ветка, PRD, план, `aidd/docs/tasklist/<ticket>.md`.
- **Выход:** отчёт об обнаруженных проблемах и рекомендации; чеклисты обновлены состоянием READY/BLOCKED.
- **Готовность:** все блокирующие замечания устранены, финальный статус — READY.
- **Тесты:** используйте `claude-workflow reviewer-tests --status required [--ticket <ticket>]`, чтобы запросить автотесты. После выполнения обновите маркер на `optional`, иначе `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh` будет запускать тесты автоматически.
- **Прогресс:** убедитесь, что отмечены выполненные пункты `- [x]`, добавьте строку `Checkbox updated: …` с перечислением закрытых чекбоксов и при необходимости выполните `claude-workflow progress --source review --ticket <ticket>`.

### qa — финальная проверка качества
- **Вызов:** `/qa <ticket>` (обязательная стадия после `/review`), либо `claude-workflow qa --ticket <ticket> --report reports/qa/<ticket>.json --gate` / `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/gate-qa.sh`.
- **Вход:** активная фича, diff, результаты гейтов, раздел QA в `aidd/docs/tasklist/<ticket>.md`.
- **Выход:** структурированный отчёт (severity, scope, рекомендации), JSON `reports/qa/<ticket>.json`, обновлённый чеклист.
- **Особенности:** гейт `gate-qa.sh` блокирует релиз при `blocker`/`critical`, см. `aidd/docs/qa-playbook.md` для чеклистов и переменных окружения.
- **Handoff:** после статуса READY/WARN вызовите `claude-workflow tasks-derive --source qa --append --ticket <ticket>` — новые `- [ ]` в tasklist должны содержать ссылку на `reports/qa/<ticket>.json`.
- **Прогресс:** после каждой регрессии фиксируйте, какие чекбоксы закрыты (`Checkbox updated: …`), и запускайте `claude-workflow progress --source qa --ticket <ticket>`, чтобы хук `gate-workflow.sh` не блокировал правки.

## Работа с барьерами

- `gate-workflow.sh` активен на Stop/SubagentStop и блокирует `src/**`, пока не готовы PRD, план, review-plan, PRD review и `aidd/docs/tasklist/<ticket>.md`. Он также проверяет, что после изменений появились новые `- [x]` (гейт `tasklist_progress`); для handoff допускаются новые `- [ ]` с ссылкой на отчёт при вызове `claude-workflow progress --source handoff`. Если стадия задана, правки кода разрешены только на `implement/review/qa`.
- Дополнительные проверки настраиваются в `config/gates.json`:
  - `tests_required`: `disabled` / `soft` / `hard` — предупреждение или блокировка при отсутствии тестов.
- Сообщения гейтов содержат подсказки (какой файл создать, как отключить проверку).

## Автоформатирование и тесты

- Пресет `strict` запускает `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh` на Stop/SubagentStop **и только при стадии `implement`**. Скрипт анализирует diff, форматирует код и выполняет выборочные задачи тест-раннера/CLI.
- Управляйте поведением через переменные окружения: `SKIP_AUTO_TESTS=1` — пауза, `FORMAT_ONLY=1` — форматирование без тестов, `TEST_SCOPE="task1,task2"` — задать конкретные задачи и выключить режим changed-only, `TEST_CHANGED_ONLY=0` — форсировать полный прогон, `STRICT_TESTS=1` — падать при первых ошибках. Для обхода stage check используйте `CLAUDE_SKIP_STAGE_CHECKS=1`.
- Для ручного запуска выполните `bash "${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh"` (команда учитывает те же переменные) и исправьте замечания перед продолжением работы.

## Чеклист быстрого старта фичи

1. Создайте ветку (`git checkout -b feature/<TICKET>`) и запустите `/idea-new <ticket> [slug-hint]` — команда зафиксирует ticket в `aidd/docs/.active_ticket`, при необходимости сохранит slug-хинт в `aidd/docs/.active_feature` **и автоматически создаст PRD `aidd/docs/prd/<ticket>.prd.md` со статусом `Status: draft`, который нужно довести до READY.**
2. Выполните `/plan-new`, затем `/review-plan` и `/review-prd`, после чего запустите `/tasks-new`, пока артефакты не получат статус READY.
3. При необходимости включите дополнительные гейты (`config/gates.json`) и подготовьте связанные артефакты: миграции, OpenAPI, дополнительные тесты.
4. Реализуйте фичу через `/implement`, следя за сообщениями `gate-workflow` и выбранных гейтов; фиксируйте прогресс в `aidd/docs/tasklist/<ticket>.md`.
5. Запросите `/review`, когда чеклисты закрыты, автотесты зелёные и артефакты синхронизированы.

Используйте этот playbook как основу и дополняйте его корпоративными процессами (release notes, ADR, демо). Если нужны расширенные команды или агенты, примените `claude-workflow-extensions.patch`.
