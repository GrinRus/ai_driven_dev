---
description: "Реализация фичи по плану + выборочные тесты"
argument-hint: "<slug>"
allowed-tools: Bash("$CLAUDE_PROJECT_DIR/.claude/hooks/format-and-test.sh:*"),Bash(claude-workflow progress:*),Read,Edit,Write,Grep,Glob
---
1) Вызови саб‑агента **implementer** для выполнения шага реализации по `docs/plan/$1.md`.
2) Следи за автозапуском `.claude/hooks/format-and-test.sh`: он стартует после записи и выполняет форматирование+тесты. При необходимости приостанови `export SKIP_AUTO_TESTS=1`, запусти только форматирование `FORMAT_ONLY=1` или укажи конкретные задачи `TEST_SCOPE=":app:test"`.
3) Для ручного прогона вызови `!"$CLAUDE_PROJECT_DIR"/.claude/hooks/format-and-test.sh` (уважает `STRICT_TESTS`, `TEST_CHANGED_ONLY` и другие переменные).
4) После каждой итерации обновляй `docs/tasklist/$1.md`: переводи выполненные пункты `- [ ] → - [x]`, добавляй отметку времени/итерации и кратко фиксируй результат (см. раздел «Как отмечать прогресс» в шаблоне).
5) Перед завершением команды запусти `!bash -lc 'claude-workflow progress --source implement --feature "$1"'`. Если утилита сообщает, что новые `- [x]` не найдены, вернись к tasklist и дополни чеклист прежде чем продолжать.
6) В финальном ответе перечисли, какие чекбоксы tasklist закрыты и что остаётся в работе; добавь строку `Checkbox updated: <список чекбоксов>` и при неопределённости (алгоритм/интеграция/БД) приостановись и уточни детали у пользователя.
