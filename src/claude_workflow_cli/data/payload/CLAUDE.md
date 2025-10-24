# Claude Code Workflow (AI-driven)

## Основной цикл
1. `/idea-new <ticket> [slug-hint]` — фиксирует ticket в `docs/.active_ticket` (и при необходимости slug-хинт в `.active_feature`), агент analyst оформляет PRD и собирает вводные.
2. `/plan-new <ticket>` — planner строит план реализации, validator проверяет риски и возвращает вопросы.
3. `/tasks-new <ticket>` — tasklist синхронизируется с планом: чеклисты по аналитике, разработке, тестированию и релизу.
4. `/implement <ticket>` — агент implementer вносит изменения малыми итерациями, автозапускает `.claude/hooks/format-and-test.sh`.
5. `/review <ticket>` — reviewer проводит финальное ревью и фиксирует замечания в `docs/tasklist/<ticket>.md`.

## Хуки и гейты
- `.claude/hooks/gate-workflow.sh` — не даёт редактировать `src/**`, пока не готовы PRD, план и `docs/tasklist/<ticket>.md`.
- `.claude/hooks/gate-db-migration.sh` — опционально проверяет, что изменения домена сопровождаются миграцией (`config/gates.json: db_migration=true`).
- `.claude/hooks/gate-tests.sh` — опционально требует наличие юнит-тестов для изменённых исходников (`tests_required=soft|hard`).
- `.claude/hooks/gate-api-contract.sh` — опционально сверяет наличие `docs/api/$TICKET.yaml` для контроллеров (`api_contract=true`).
- `.claude/hooks/format-and-test.sh` — форматирует код и запускает выборочные Gradle-тесты после каждой записи (отключается `SKIP_AUTO_TESTS=1`).
- `.claude/hooks/lint-deps.sh` — напоминает про allowlist зависимостей.

Дополнительные проверки настраиваются в `config/gates.json`. Пресеты разрешений и хуков описаны в `.claude/settings.json`, правила веток/коммитов — в `config/conventions.json`.
