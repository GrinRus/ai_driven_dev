# Claude Code Workflow (AI-driven)

## Основной цикл
1. `/idea-new <slug> [TICKET]` — фиксирует slug в `docs/.active_feature`, агент analyst оформляет PRD и собирает вводные.
2. `/plan-new <slug>` — planner строит план реализации, validator проверяет риски и возвращает вопросы.
3. `/tasks-new <slug>` — tasklist синхронизируется с планом: чеклисты по аналитике, разработке, тестированию и релизу.
4. `/implement <slug>` — агент implementer вносит изменения малыми итерациями, автозапускает `.claude/hooks/format-and-test.sh`.
5. `/review <slug>` — reviewer проводит финальное ревью и фиксирует замечания в `tasklist.md`.

## Хуки и гейты
- `.claude/hooks/protect-prod.sh` — защищает продовые каталоги (`infra/prod`, `deploy/prod`).
- `.claude/hooks/gate-workflow.sh` — не даёт редактировать `src/**`, пока не готовы PRD, план и tasklist.
- `.claude/hooks/gate-db-migration.sh` — опционально проверяет, что изменения домена сопровождаются миграцией (`config/gates.json: db_migration=true`).
- `.claude/hooks/gate-tests.sh` — опционально требует наличие юнит-тестов для изменённых исходников (`tests_required=soft|hard`).
- `.claude/hooks/gate-api-contract.sh` — опционально сверяет наличие `docs/api/$SLUG.yaml` для контроллеров (`api_contract=true`).
- `.claude/hooks/format-and-test.sh` — форматирует код и запускает выборочные Gradle-тесты после каждой записи (отключается `SKIP_AUTO_TESTS=1`).
- `.claude/hooks/lint-deps.sh` — напоминает про allowlist зависимостей.

Дополнительные проверки настраиваются в `config/gates.json`. Пресеты разрешений и хуков описаны в `.claude/settings.json`, правила веток/коммитов — в `config/conventions.json`.
