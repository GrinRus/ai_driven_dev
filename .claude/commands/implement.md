---
description: "Реализация фичи по плану + выборочные тесты"
argument-hint: "<slug>"
allowed-tools: Bash("$CLAUDE_PROJECT_DIR/.claude/hooks/format-and-test.sh:*"),Read,Edit,Write,Grep,Glob
---
1) Вызови саб‑агента **implementer** для выполнения шага реализации по `docs/plan/$1.md`.
2) После каждой правки запускай `/test-changed` — автозапуск срабатывает автоматически после успешных правок (отключить: `SKIP_AUTO_TESTS=1`).
3) Если возникает неопределённость (алгоритм/интеграция/БД) — приостановись и задавай вопросы пользователю.
