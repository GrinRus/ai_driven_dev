# Claude Code Workflow (AI-driven)

> Команды и агенты поставляются как плагин `feature-dev-aidd` (`aidd/.claude-plugin/plugin.json`, файлы в `aidd/{commands,agents,hooks}`); рантайм-хуки/настройки лежат в `aidd/.claude/`. Следуйте `workflow.md` и `config/conventions.json` — они описывают порядок шагов и соглашения. Hook events живут в `aidd/hooks/hooks.json` и вызывают `${CLAUDE_PLUGIN_ROOT}/.claude/hooks/*.sh`.

## Основной цикл
1. `/idea-new <ticket> [slug-hint]` — фиксирует ticket в `aidd/docs/.active_ticket` (и при необходимости slug-хинт в `.active_feature`), агент analyst оформляет PRD и собирает вводные.
2. `/researcher <ticket>` или `claude-workflow research --ticket <ticket> --auto` — запускается при нехватке контекста (после аналитика); формирует `aidd/docs/research/<ticket>.md` и отчёты `reports/research/*.json`, baseline допустим для пустых проектов.
3. `/plan-new <ticket>` — planner строит план реализации, validator проверяет риски и возвращает вопросы.
4. `/tasks-new <ticket>` — tasklist синхронизируется с планом: чеклисты по аналитике, разработке, тестированию и релизу.
5. `/implement <ticket>` — агент implementer вносит изменения малыми итерациями, автозапускает `.claude/hooks/format-and-test.sh`.
6. `/review <ticket>` — reviewer проводит финальное ревью и фиксирует замечания в `aidd/docs/tasklist/<ticket>.md`.

## Хуки и гейты
- `.claude/hooks/gate-workflow.sh` — не даёт редактировать `src/**`, пока не готовы PRD, план и `aidd/docs/tasklist/<ticket>.md`.
- `.claude/hooks/gate-tests.sh` — опционально требует наличие юнит-тестов для изменённых исходников (`tests_required=soft|hard`).
- `.claude/hooks/format-and-test.sh` — форматирует код и запускает выборочные Gradle-тесты после каждой записи (отключается `SKIP_AUTO_TESTS=1`).
- `.claude/hooks/lint-deps.sh` — напоминает про allowlist зависимостей.

Дополнительные проверки настраиваются в `config/gates.json`. Пресеты разрешений и хуков описаны в `.claude/settings.json`, правила веток/коммитов — в `config/conventions.json`.

## Контроль контекста (context GC)
- Working Set собирается из `aidd/docs/.active_ticket`, PRD/research/tasklist и состояния git, затем подмешивается в `SessionStart` (startup/resume/clear/compact).
- Перед `/compact` (`PreCompact`) сохраняется снапшот: `aidd/reports/context/<session_id>/working_set.md`, `precompact_meta.json`, `transcript_tail.jsonl`, а также `aidd/reports/context/latest_working_set.md`. Дополнительно создаётся индекс по тикету: `aidd/reports/context/by-ticket/<ticket>/<session_id>/...` и `aidd/reports/context/by-ticket/<ticket>/latest_working_set.md`.
- `PreToolUse` ограничивает раздувание контекста: Bash-команды с большим выводом логируются в `aidd/reports/logs/` и в чат попадает только tail, большие `Read` требуют подтверждения или блокируются.
- `UserPromptSubmit` предупреждает или блокирует промпты при достижении лимита: основной режим `context_limits` работает по токенам (128k), при невозможности парсинга транскрипта используется bytes‑fallback из `transcript_limits`. Настройки — в `aidd/config/context_gc.json`.
- Smoke-проверка: новая сессия → есть Working Set в начале; `/compact` → появляются файлы в `aidd/reports/context/`; `docker logs` без `--tail` и `Read` большого файла → срабатывают guard'ы.
