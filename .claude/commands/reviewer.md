---
description: "Управление маркером тестов reviewer"
argument-hint: "[ticket]"
allowed-tools: Bash(claude-workflow reviewer-tests:*)
---
1. Если тесты нужны, выполни `claude-workflow reviewer-tests --status required [--ticket $1]`.
2. После успешного прогона обнови маркер: `claude-workflow reviewer-tests --status optional [--ticket $1]`.
3. Для сброса статуса используй `claude-workflow reviewer-tests --clear [--ticket $1]`.

Маркер сохраняется в `reports/reviewer/<ticket>.json`; format-and-test запускает тесты, только когда значение равно `required`.
