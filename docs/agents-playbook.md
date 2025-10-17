# Playbook агентов и барьеров Claude Code

Документ помогает быстро провести фичу через цикл Claude Code, понять роли саб-агентов и поведение гейтов. Следуйте последовательности, чтобы избегать блокирующих хуков и расхождений в артефактах.

## Ролевая цепочка

| Шаг | Команда | Агент(ы) | Основной вход | Основной выход | Готовность |
| --- | --- | --- | --- | --- | --- |
| 1 | `/idea-new <slug> [TICKET]` | `analyst` | Свободная идея, вводные, ограничения | `docs/.active_feature`, `docs/prd/<slug>.prd.md` | PRD заполнен, статус READY/BLOCKED выставлен |
| 2 | `claude-workflow research --feature <slug>` → `/researcher <slug>` | `researcher` | PRD, backlog, целевые модули | `docs/research/<slug>.md`, `reports/research/<slug>-context.json` | Status: reviewed, пути интеграции подтверждены |
| 3 | `/plan-new <slug>` | `planner`, `validator` | PRD, отчёт Researcher, ответы на вопросы | `docs/plan/<slug>.md`, протокол проверки | План покрывает модули из research, критичные риски закрыты |
| 4 | `/review-prd <slug>` | `prd-reviewer` | PRD, план, ADR, Researcher | Раздел `## PRD Review`, отчёт `reports/prd/<slug>.json` | Status: approved, action items перенесены |
| 5 | `/tasks-new <slug>` | — | Утверждённый план | Обновлённый `docs/tasklist/<slug>.md` | Чеклисты привязаны к slug и этапам |
| 6 | `/implement <slug>` | `implementer` | План, `docs/tasklist/<slug>.md`, отчёт Researcher | Кодовые изменения + авто запуск `.claude/hooks/format-and-test.sh` | Гейты разрешают правки, тесты зелёные |
| 7 | `/review <slug>` | `reviewer` | Готовая ветка и артефакты | Замечания в `docs/tasklist/<slug>.md`, итоговый статус | Все блокеры сняты, чеклисты закрыты |
| 8 | `Claude: Run agent → qa` / `gate-qa.sh` | `qa` | Diff, `docs/tasklist/<slug>.md`, результаты гейтов | JSON-отчёт `reports/qa/<slug>.json`, статус READY/WARN/BLOCKED | Нет блокеров, warnings зафиксированы |

> Дополнительные агенты (`contract-checker`, `db-migrator`) вызываются вручную через палитру `Claude: Run agent …`, когда включены соответствующие гейты или требуется ручная проверка. Рядом с ними нет отдельных слэш-команд.

## Агенты и ожидаемые результаты

### analyst — аналитика идеи
- **Вызов:** `/idea-new <slug> [TICKET]`
- **Вход:** свободное описание задачи, бизнес-контекст, ограничения.
- **Процесс:** агент стартует с `Вопрос 1`, ждёт ответ `Ответ 1` и продолжает цикл, пока не закроет все блокирующие неопределённости. Каждая пара «Вопрос N»/«Ответ N» фиксируется в разделе `## Диалог analyst`, статусы обновляются на каждом раунде.
- **Выход:** PRD `docs/prd/<slug>.prd.md` с заполненным блоком `## Диалог analyst`, актуальным `Status: READY|BLOCKED`, целями, сценариями, рисками и открытыми вопросами.
- **Готовность:** `Status: READY`, отсутствуют незакрытые `- [ ]` в `## 10. Открытые вопросы`, все вопросы имеют ответы. При любом пропуске `claude-workflow analyst-check --feature <slug>` вернёт ошибку и нужно вернуться к агенту с ответами.

### researcher — исследование кодовой базы
- **Вызов:** `claude-workflow research --feature <slug>` (сбор контекста) и агент `/researcher <slug>`.
- **Вход:** PRD, backlog, `reports/research/<slug>-targets.json`, существующие источники в `src/**` и документации.
- **Выход:** `docs/research/<slug>.md` со статусом `Status: reviewed`, обновлённые файлы контекста `reports/research/<slug>-targets.json` и `<slug>-context.json`; ссылка на отчёт зафиксирована в PRD и `docs/tasklist/<slug>.md`.
- **Готовность:** отчёт описывает точки интеграции, reuse и риски; action items перенесены в план/тасклист, список директорий покрывает изменяемый код.

### planner — план реализации
- **Вызов:** `/plan-new <slug>`
- **Вход:** актуальный PRD и ответы на вопросы аналитика.
- **Выход:** `docs/plan/<slug>.md` с декомпозицией на итерации, DoD и ссылками на модули/файлы.
- **Особенности:** используй вывод Researcher как опорный список модулей и reuse; сразу после генерации план проходит проверку агентом `validator`, открытые вопросы синхронизируются в PRD.

### validator — проверка плана
- **Вызов:** автоматически внутри `/plan-new`.
- **Вход:** черновой план.
- **Выход:** статус PASS/BLOCKED, список уточняющих вопросов и рисков.
- **Готовность:** все критичные вопросы закрыты или перенесены в backlog; рекомендации Researcher учтены, план можно раздавать исполнителям.

### prd-reviewer — контроль качества PRD
- **Вызов:** `/review-prd <slug>`
- **Вход:** `docs/prd/<slug>.prd.md`, `docs/plan/<slug>.md`, актуальные ADR, открытые вопросы.
- **Выход:** Раздел `## PRD Review` с `Status: approved|blocked|pending`, summary, findings и action items; отчёт `reports/prd/<slug>.json`.
- **Особенности:** блокирующие замечания фиксируйте как `Status: blocked` и переносите action items в `docs/tasklist/<slug>.md`; проверяйте, что `docs/research/<slug>.md` имеет `Status: reviewed`. Без `approved` гейт `gate-workflow` не даст менять код.

### tasks-new — чеклист команды
- **Команда:** `/tasks-new <slug>`
- **Выход:** обновлённый `docs/tasklist/<slug>.md` с задачами на аналитику, разработку, QA и релиз.
- **Готовность:** чеклисты отражают фактический план, каждая задача содержит критерий приёмки.

### implementer — реализация
- **Вызов:** `/implement <slug>`
- **Вход:** утверждённый план и `docs/tasklist/<slug>.md`.
- **Выход:** серия небольших коммитов, обновлённые тесты и документация.
- **Особенности:** после каждой записи автоматически запускается `.claude/hooks/format-and-test.sh` (отключаемо `SKIP_AUTO_TESTS=1`). Агент следит за сообщениями `gate-workflow`, `gate-db-migration`, `gate-tests`, если они включены.

### reviewer — код-ревью
- **Вызов:** `/review <slug>`
- **Вход:** готовая ветка, PRD, план, `docs/tasklist/<slug>.md`.
- **Выход:** отчёт об обнаруженных проблемах и рекомендации; чеклисты обновлены состоянием READY/BLOCKED.
- **Готовность:** все блокирующие замечания устранены, финальный статус — READY.

### qa — финальная проверка качества
- **Вызов:** `Claude: Run agent → qa`, либо `python3 scripts/qa-agent.py --gate` / `./.claude/hooks/gate-qa.sh`.
- **Вход:** активная фича, diff, результаты гейтов, раздел QA в `docs/tasklist/<slug>.md`.
- **Выход:** структурированный отчёт (severity, scope, рекомендации), JSON `reports/qa/<slug>.json`, обновлённый чеклист.
- **Особенности:** гейт `gate-qa.sh` блокирует релиз при `blocker`/`critical`, см. `docs/qa-playbook.md` для чеклистов и переменных окружения.

### db-migrator — миграции БД *(опционально)*
- **Вызов:** `Claude: Run agent → db-migrator`, когда `config/gates.json: db_migration=true`.
- **Выход:** новая миграция (`src/main/resources/**/db/migration/*.sql|*.xml|*.yaml`) и заметки о ручных шагах.
- **Готовность:** миграция покрывает все изменения доменной модели, гейт `gate-db-migration.sh` пропускает правки.

### contract-checker — сверка API *(опционально)*
- **Вызов:** `Claude: Run agent → contract-checker`, когда `api_contract=true`.
- **Выход:** отчёт о расхождениях между контроллерами и `docs/api/<slug>.yaml`.
- **Готовность:** все эндпоинты синхронизированы с контрактом или занесены в backlog.

## Работа с барьерами

- `gate-workflow.sh` активен всегда и блокирует `src/**`, пока не готовы PRD, план и `docs/tasklist/<slug>.md`.
- Дополнительные проверки настраиваются в `config/gates.json`:
  - `api_contract=true` — требует `docs/api/<slug>.yaml` для правок контроллеров.
  - `db_migration=true` — ищет новые файлы в `src/main/resources/**/db/migration/`.
  - `tests_required`: `disabled` / `soft` / `hard` — предупреждение или блокировка при отсутствии тестов.
- Сообщения гейтов содержат подсказки (какой файл создать, как отключить проверку).

## Автоформатирование и тесты

- Пресет `strict` запускает `.claude/hooks/format-and-test.sh` после каждой операции записи. Скрипт анализирует diff, форматирует код и выполняет выборочные Gradle/CLI задачи.
- Управляйте поведением через переменные окружения: `SKIP_AUTO_TESTS=1` — пауза, `FORMAT_ONLY=1` — форматирование без тестов, `TEST_SCOPE=":app:test"` — задать конкретные задачи и выключить режим changed-only, `TEST_CHANGED_ONLY=0` — форсировать полный прогон, `STRICT_TESTS=1` — падать при первых ошибках.
- Для ручного запуска выполните `bash .claude/hooks/format-and-test.sh` (команда учитывает те же переменные) и исправьте замечания перед продолжением работы.

## Чеклист быстрого старта фичи

1. Создайте ветку (`git checkout -b feature/<TICKET>`) и запустите `/idea-new <slug>` — slug попадёт в `docs/.active_feature`.
2. Выполните `/plan-new` и `/tasks-new`, пока артефакты не получат статус READY.
3. При необходимости включите дополнительные гейты (`config/gates.json`) и подготовьте связанные артефакты: миграции, OpenAPI, дополнительные тесты.
4. Реализуйте фичу через `/implement`, следя за сообщениями `gate-workflow` и выбранных гейтов; фиксируйте прогресс в `docs/tasklist/<slug>.md`.
5. Запросите `/review`, когда чеклисты закрыты, автотесты зелёные и артефакты синхронизированы.

Используйте этот playbook как основу и дополняйте его корпоративными процессами (release notes, ADR, демо). Если нужны расширенные команды или агенты, примените `claude-workflow-extensions.patch`.
