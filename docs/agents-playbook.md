# Playbook агентов и барьеров Claude Code

Документ помогает быстро провести фичу через цикл Claude Code, понять роли саб-агентов и поведение гейтов. Следуйте последовательности, чтобы избегать блокирующих хуков и расхождений в артефактах.

> Ticket — основной идентификатор фичи, сохраняется в `docs/.active_ticket`. При необходимости указывайте slug-hint (человекочитаемый алиас) — он хранится в `docs/.active_feature` и используется в шаблонах/логах.

## Ролевая цепочка

| Шаг | Команда | Агент(ы) | Основной вход | Основной выход | Готовность |
| --- | --- | --- | --- | --- | --- |
| 1 | `/idea-new <ticket> [slug-hint]` | `analyst` | Свободная идея, вводные, ограничения | `docs/.active_ticket`, `docs/prd/<ticket>.prd.md` | PRD заполнен, статус READY/BLOCKED выставлен |
| 2 | `claude-workflow research --ticket <ticket>` → `/researcher <ticket>` | `researcher` | PRD, backlog, целевые модули | `docs/research/<ticket>.md`, `reports/research/<ticket>-context.json` | Status: reviewed, пути интеграции подтверждены |
| 3 | `/plan-new <ticket>` | `planner`, `validator` | PRD, отчёт Researcher, ответы на вопросы | `docs/plan/<ticket>.md`, протокол проверки | План покрывает модули из research, критичные риски закрыты |
| 4 | `/review-prd <ticket>` | `prd-reviewer` | PRD, план, ADR, Researcher | Раздел `## PRD Review`, отчёт `reports/prd/<ticket>.json` | Status: approved, action items перенесены |
| 5 | `/tasks-new <ticket>` | — | Утверждённый план | Обновлённый `docs/tasklist/<ticket>.md` | Чеклисты привязаны к ticket (slug-hint) и этапам |
| 6 | `/implement <ticket>` | `implementer` | План, `docs/tasklist/<ticket>.md`, отчёт Researcher | Кодовые изменения + авто запуск `.claude/hooks/format-and-test.sh` | Гейты разрешают правки, тесты зелёные |
| 7 | `/review <ticket>` | `reviewer` | Готовая ветка и артефакты | Замечания в `docs/tasklist/<ticket>.md`, итоговый статус | Все блокеры сняты, чеклисты закрыты |
| 8 | `Claude: Run agent → qa` / `gate-qa.sh` | `qa` | Diff, `docs/tasklist/<ticket>.md`, результаты гейтов | JSON-отчёт `reports/qa/<ticket>.json`, статус READY/WARN/BLOCKED | Нет блокеров, warnings зафиксированы |

> Дополнительные агенты (`contract-checker`, `db-migrator`) вызываются вручную через палитру `Claude: Run agent …`, когда включены соответствующие гейты или требуется ручная проверка. Рядом с ними нет отдельных слэш-команд.

## Агенты и ожидаемые результаты

### analyst — аналитика идеи
- **Вызов:** `/idea-new <ticket> [slug-hint]`
- **Вход:** свободное описание задачи, бизнес-контекст, ограничения.
- **Перед стартом:** убедитесь, что `claude-workflow research --ticket <ticket> --auto` собрал контекст и `docs/research/<ticket>.md` создан (при необходимости добавьте `--note` для ручных наблюдений).
- **Процесс:** агент стартует с `Вопрос 1`, ждёт ответ `Ответ 1` и продолжает цикл, пока не закроет все блокирующие неопределённости. Каждая пара «Вопрос N»/«Ответ N» фиксируется в разделе `## Диалог analyst`, статусы обновляются на каждом раунде.
- **Выход:** PRD `docs/prd/<ticket>.prd.md` с заполненным блоком `## Диалог analyst`, актуальным `Status: READY|BLOCKED`, целями, сценариями, рисками и открытыми вопросами.
- **Готовность:** `Status: READY`, отсутствуют незакрытые `- [ ]` в `## 10. Открытые вопросы`, все вопросы имеют ответы. При любом пропуске `claude-workflow analyst-check --ticket <ticket>` вернёт ошибку и нужно вернуться к агенту с ответами.

### researcher — исследование кодовой базы
- **Вызов:** `claude-workflow research --ticket <ticket> --auto` (подбор целей/контекста, опции `--paths`, `--keywords`, `--note/@file`) и агент `/researcher <ticket>`.
- **Вход:** PRD, backlog, `reports/research/<ticket>-targets.json`, `reports/research/<ticket>-context.json`, slug-хинт, ручные заметки.
- **Выход:** `docs/research/<ticket>.md` со статусом `Status: reviewed` (или `pending` с baseline для новых проектов), заполненными секциями `## Паттерны/анти-паттерны`, `## Отсутствие паттернов`, `## Дополнительные заметки`; ссылка на отчёт зафиксирована в PRD и `docs/tasklist/<ticket>.md`.
- **Готовность:** отчёт описывает точки интеграции, reuse и риски; action items перенесены в план/тасклист; `reports/research/<ticket>-context.json` не устарел, baseline (если был) отмечен маркером «Контекст пуст, требуется baseline».

### planner — план реализации
- **Вызов:** `/plan-new <ticket>`
- **Вход:** актуальный PRD и ответы на вопросы аналитика.
- **Выход:** `docs/plan/<ticket>.md` с декомпозицией на итерации, DoD и ссылками на модули/файлы.
- **Особенности:** используй вывод Researcher как опорный список модулей и reuse; сразу после генерации план проходит проверку агентом `validator`, открытые вопросы синхронизируются в PRD.

### validator — проверка плана
- **Вызов:** автоматически внутри `/plan-new`.
- **Вход:** черновой план.
- **Выход:** статус PASS/BLOCKED, список уточняющих вопросов и рисков.
- **Готовность:** все критичные вопросы закрыты или перенесены в backlog; рекомендации Researcher учтены, план можно раздавать исполнителям.

### prd-reviewer — контроль качества PRD
- **Вызов:** `/review-prd <ticket>`
- **Вход:** `docs/prd/<ticket>.prd.md`, `docs/plan/<ticket>.md`, актуальные ADR, открытые вопросы.
- **Выход:** Раздел `## PRD Review` с `Status: approved|blocked|pending`, summary, findings и action items; отчёт `reports/prd/<ticket>.json`.
- **Особенности:** блокирующие замечания фиксируйте как `Status: blocked` и переносите action items в `docs/tasklist/<ticket>.md`; проверяйте, что `docs/research/<ticket>.md` имеет `Status: reviewed`. Без `approved` гейт `gate-workflow` не даст менять код.

### tasks-new — чеклист команды
- **Команда:** `/tasks-new <ticket>`
- **Выход:** обновлённый `docs/tasklist/<ticket>.md` с задачами на аналитику, разработку, QA и релиз.
- **Готовность:** чеклисты отражают фактический план, каждая задача содержит критерий приёмки.

### implementer — реализация
- **Вызов:** `/implement <ticket>`
- **Вход:** утверждённый план и `docs/tasklist/<ticket>.md`.
- **Выход:** серия небольших коммитов, обновлённые тесты и документация.
- **Особенности:** после каждой записи автоматически запускается `.claude/hooks/format-and-test.sh` (отключаемо `SKIP_AUTO_TESTS=1`). Агент следит за сообщениями `gate-workflow`, `gate-db-migration`, `gate-tests`, если они включены.
- **Прогресс:** каждую итерацию переводите релевантные пункты `- [ ] → - [x]`, добавляйте строку `Checkbox updated: …` и запускайте `claude-workflow progress --source implement --ticket <ticket>`. При отсутствии новых `- [x]` команда подскажет, что нужно отметить прогресс до завершения ответа.

### reviewer — код-ревью
- **Вызов:** `/review <ticket>`
- **Вход:** готовая ветка, PRD, план, `docs/tasklist/<ticket>.md`.
- **Выход:** отчёт об обнаруженных проблемах и рекомендации; чеклисты обновлены состоянием READY/BLOCKED.
- **Готовность:** все блокирующие замечания устранены, финальный статус — READY.
- **Тесты:** используйте `claude-workflow reviewer-tests --status required [--ticket <ticket>]`, чтобы запросить автотесты. После выполнения обновите маркер на `optional`, иначе `.claude/hooks/format-and-test.sh` будет запускать тесты автоматически.
- **Прогресс:** убедитесь, что отмечены выполненные пункты `- [x]`, добавьте строку `Checkbox updated: …` с перечислением закрытых чекбоксов и при необходимости выполните `claude-workflow progress --source review --ticket <ticket>`.

### qa — финальная проверка качества
- **Вызов:** `Claude: Run agent → qa`, либо `python3 scripts/qa-agent.py --gate` / `./.claude/hooks/gate-qa.sh`.
- **Вход:** активная фича, diff, результаты гейтов, раздел QA в `docs/tasklist/<ticket>.md`.
- **Выход:** структурированный отчёт (severity, scope, рекомендации), JSON `reports/qa/<ticket>.json`, обновлённый чеклист.
- **Особенности:** гейт `gate-qa.sh` блокирует релиз при `blocker`/`critical`, см. `docs/qa-playbook.md` для чеклистов и переменных окружения.
- **Прогресс:** после каждой регрессии фиксируйте, какие чекбоксы закрыты (`Checkbox updated: …`), и запускайте `claude-workflow progress --source qa --ticket <ticket>`, чтобы хук `gate-workflow.sh` не блокировал правки.

### db-migrator — миграции БД *(опционально)*
- **Вызов:** `Claude: Run agent → db-migrator`, когда `config/gates.json: db_migration=true`.
- **Выход:** новая миграция (`src/main/resources/**/db/migration/*.sql|*.xml|*.yaml`) и заметки о ручных шагах.
- **Готовность:** миграция покрывает все изменения доменной модели, гейт `gate-db-migration.sh` пропускает правки.

### contract-checker — сверка API *(опционально)*
- **Вызов:** `Claude: Run agent → contract-checker`, когда `api_contract=true`.
- **Выход:** отчёт о расхождениях между контроллерами и `docs/api/<ticket>.yaml`.
- **Готовность:** все эндпоинты синхронизированы с контрактом или занесены в backlog.

## Работа с барьерами

- `gate-workflow.sh` активен всегда и блокирует `src/**`, пока не готовы PRD, план и `docs/tasklist/<ticket>.md`. Он также проверяет, что после изменений появились новые `- [x]` (гейт `tasklist_progress`).
- Дополнительные проверки настраиваются в `config/gates.json`:
  - `api_contract=true` — требует `docs/api/<ticket>.yaml` для правок контроллеров.
  - `db_migration=true` — ищет новые файлы в `src/main/resources/**/db/migration/`.
  - `tests_required`: `disabled` / `soft` / `hard` — предупреждение или блокировка при отсутствии тестов.
- Сообщения гейтов содержат подсказки (какой файл создать, как отключить проверку).

## Автоформатирование и тесты

- Пресет `strict` запускает `.claude/hooks/format-and-test.sh` после каждой операции записи. Скрипт анализирует diff, форматирует код и выполняет выборочные Gradle/CLI задачи.
- Управляйте поведением через переменные окружения: `SKIP_AUTO_TESTS=1` — пауза, `FORMAT_ONLY=1` — форматирование без тестов, `TEST_SCOPE=":app:test"` — задать конкретные задачи и выключить режим changed-only, `TEST_CHANGED_ONLY=0` — форсировать полный прогон, `STRICT_TESTS=1` — падать при первых ошибках.
- Для ручного запуска выполните `bash .claude/hooks/format-and-test.sh` (команда учитывает те же переменные) и исправьте замечания перед продолжением работы.

## Чеклист быстрого старта фичи

1. Создайте ветку (`git checkout -b feature/<TICKET>`) и запустите `/idea-new <ticket> [slug-hint]` — команда зафиксирует ticket в `docs/.active_ticket` и, при необходимости, сохранит slug-хинт в `docs/.active_feature`.
2. Выполните `/plan-new` и `/tasks-new`, пока артефакты не получат статус READY.
3. При необходимости включите дополнительные гейты (`config/gates.json`) и подготовьте связанные артефакты: миграции, OpenAPI, дополнительные тесты.
4. Реализуйте фичу через `/implement`, следя за сообщениями `gate-workflow` и выбранных гейтов; фиксируйте прогресс в `docs/tasklist/<ticket>.md`.
5. Запросите `/review`, когда чеклисты закрыты, автотесты зелёные и артефакты синхронизированы.

Используйте этот playbook как основу и дополняйте его корпоративными процессами (release notes, ADR, демо). Если нужны расширенные команды или агенты, примените `claude-workflow-extensions.patch`.
