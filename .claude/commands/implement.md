---
description: "Реализация фичи по плану + выборочные тесты"
argument-hint: "<slug>"
allowed-tools: Bash("$CLAUDE_PROJECT_DIR/.claude/hooks/format-and-test.sh:*"),Read,Edit,Write,Grep,Glob
---
1) Вызови саб‑агента **implementer** для выполнения шага реализации по `docs/plan/$1.md`.
2) Следи за автозапуском `.claude/hooks/format-and-test.sh`: он стартует после записи и выполняет форматирование+тесты. При необходимости приостанови `export SKIP_AUTO_TESTS=1`, запусти только форматирование `FORMAT_ONLY=1` или укажи конкретные задачи `TEST_SCOPE=":app:test"`.
3) Для ручного прогона вызови `!"$CLAUDE_PROJECT_DIR"/.claude/hooks/format-and-test.sh` (уважает `STRICT_TESTS`, `TEST_CHANGED_ONLY` и другие переменные).
4) Если возникает неопределённость (алгоритм/интеграция/БД) — приостановись и задавай вопросы пользователю.
5) Используй секцию `## $1` в `docs/tasklist/$1.md` (создаётся пресетом `feature-impl`) как чеклист готовности перед пушем.
