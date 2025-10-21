---
description: "Управление маркером тестов reviewer"
argument-hint: "[slug]"
allowed-tools: Bash(claude-workflow reviewer-tests:*)
---
1. Если тесты нужны, выполни `claude-workflow reviewer-tests --status required [--feature $1]`.
2. После успешного прогона обнови маркер: `claude-workflow reviewer-tests --status optional [--feature $1]`.
3. Для сброса статуса используй `claude-workflow reviewer-tests --clear [--feature $1]`.

Маркер сохраняется в `reports/reviewer/<slug>.json`; format-and-test запускает тесты, только когда значение равно `required`.
