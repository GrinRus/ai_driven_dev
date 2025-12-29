---
description: "Финальная QA-проверка фичи"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.3
source_version: 1.0.3
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - "Bash(claude-workflow qa:*)"
  - "Bash(claude-workflow progress:*)"
  - "Bash(scripts/ci-lint.sh:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда`/qa`запускает обязательную финальную проверку фичи: вызывает саб-агента **qa** через`claude-workflow qa --gate`, формирует отчёт`${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/qa/<ticket>.json`, обновляет раздел QA в`aidd/docs/tasklist/<ticket>.md`и фиксирует прогресс. Выполняется после`/review`и перед релизом. Свободный ввод после тикета используй как контекст проверки.

## Входные артефакты
- Активный тикет (`aidd/docs/.active_ticket`), slug-hint (`aidd/docs/.active_feature`).
- `@aidd/docs/prd/<ticket>.prd.md`, `@aidd/docs/plan/<ticket>.md`, `@aidd/docs/tasklist/<ticket>.md` (QA секция), логи предыдущих гейтов (`gate-tests`).
- Diff/логи выполнения (`git diff`,`reports/reviewer/<ticket>.json`, тесты, демо окружение).

## Когда запускать
- После`/review`, перед релизом и мёржем в основную ветку.
- Повторяй при новых коммитах или изменении QA чеков.

## Автоматические хуки и переменные
- Обязательный вызов:`!bash -lc 'claude-workflow qa --ticket "<ticket>" --report "${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/qa/<ticket>.json" --gate --emit-json'`.
- Гейт`${CLAUDE_PLUGIN_ROOT:-./aidd}/.claude/hooks/gate-qa.sh` использует`config/gates.json: qa.command`(по умолчанию`claude-workflow qa --gate`), блокирует merge при`blocker/critical`и отсутствии отчёта`${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/qa/<ticket>.json`.
- Зафиксируй прогресс:`!bash -lc 'claude-workflow progress --source qa --ticket "<ticket>"'`.

## Что редактируется
-`aidd/docs/tasklist/<ticket>.md`— отмечаются QA чекбоксы, даты прогонов, ссылки на логи/отчёт.
-`${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/qa/<ticket>.json`— свежий отчёт агента QA.

## Пошаговый план
1. Запусти саб-агента **qa** через CLI (см. команду выше) и дождись формирования`${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/qa/<ticket>.json`со статусом READY/WARN/BLOCKED.
2. Сопоставь diff с чеклистом: какие QA пункты покрыты, какие нет; зафиксируй найденные проблемы с severity и рекомендациями.
3. Обнови`aidd/docs/tasklist/<ticket>.md`: переведи релевантные пункты`- [ ] → - [x]`, добавь дату/итерацию, ссылку на отчёт и лог команд.
4. Выполни`claude-workflow progress --source qa --ticket <ticket>`и убедись, что новые`[x]`зафиксированы; при WARN перечисли known issues.
5. В ответе укажи итоговый статус, закрытые чекбоксы (`Checkbox updated: ...`), ссылку на отчёт и следующее действие (если есть WARN/BLOCKED).

## Fail-fast и вопросы
- Нет активного тикета/QA чеклиста? Попроси оформить`/tasks-new`или обновить`aidd/docs/.active_ticket`.
- Отчёт не записался? Перезапусти CLI команду и приложи stderr; без отчёта гейт заблокирует merge.
- Нет автотестов/логов среды — запроси у команды или зафиксируй объём непокрытых зон.

## Ожидаемый вывод
- Ответ начинается со строки`Checkbox updated: <перечень QA пунктов>`и содержит статус`READY|WARN|BLOCKED`.
- Ссылка на`${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/qa/<ticket>.json`, summary замечаний и дальнейшие шаги.

## Примеры CLI
-`/qa ABC-123`
-`!bash -lc 'claude-workflow qa --ticket "ABC-123" --branch "$(git rev-parse --abbrev-ref HEAD)" --report "${CLAUDE_PLUGIN_ROOT:-./aidd}/reports/qa/ABC-123.json" --gate'`
