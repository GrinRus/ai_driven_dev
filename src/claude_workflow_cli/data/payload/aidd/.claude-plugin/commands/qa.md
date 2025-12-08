---
description: "Финальная QA-проверка фичи"
argument-hint: "<TICKET>"
lang: ru
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - "Bash(claude-workflow qa:*)"
  - "Bash(claude-workflow progress:*)"
model: inherit
---

## Контекст
Команда `/qa` запускает обязательную финальную проверку фичи: вызывает саб-агента **qa** через `claude-workflow qa --gate`, формирует отчёт `reports/qa/<ticket>.json`, обновляет раздел QA в `docs/tasklist/<ticket>.md` и фиксирует прогресс. Выполняется после `/review` и перед релизом.

## Входные артефакты
- Активный тикет (`docs/.active_ticket`), slug-hint (`docs/.active_feature`).
- `docs/prd/<ticket>.prd.md`, `docs/plan/<ticket>.md`, `docs/tasklist/<ticket>.md` (QA секция), логи предыдущих гейтов (`gate-tests`, `gate-api-contract`, `gate-db-migration`).
- Diff/логи выполнения (`git diff`, `reports/reviewer/<ticket>.json`, тесты, демо окружение).

## Когда запускать
- После `/review`, перед релизом и мёржем в основную ветку.
- Повторяй при новых коммитах или изменении QA чеков.

## Автоматические хуки и переменные
- Обязательный вызов: `!("claude-workflow" qa --ticket "<ticket>" --report "reports/qa/<ticket>.json" --gate --emit-json)`.
- Гейт `.claude/hooks/gate-qa.sh` использует `config/gates.json: qa.command` (по умолчанию `claude-workflow qa --gate`), блокирует merge при `blocker/critical` и отсутствии отчёта `reports/qa/<ticket>.json`.
- Зафиксируй прогресс: `!("claude-workflow" progress --source qa --ticket "<ticket>")`.

## Что редактируется
- `docs/tasklist/<ticket>.md` — отмечаются QA чекбоксы, даты прогонов, ссылки на логи/отчёт.
- `reports/qa/<ticket>.json` — свежий отчёт агента QA.

## Пошаговый план
1. Запусти саб-агента **qa** через CLI (см. команду выше) и дождись формирования `reports/qa/<ticket>.json` со статусом READY/WARN/BLOCKED.
2. Сопоставь diff с чеклистом: какие QA пункты покрыты, какие нет; зафиксируй найденные проблемы с severity и рекомендациями.
3. Обнови `docs/tasklist/<ticket>.md`: переведи релевантные пункты `- [ ] → - [x]`, добавь дату/итерацию, ссылку на отчёт и лог команд.
4. Выполни `claude-workflow progress --source qa --ticket <ticket>` и убедись, что новые `[x]` зафиксированы; при WARN перечисли known issues.
5. В ответе укажи итоговый статус, закрытые чекбоксы (`Checkbox updated: ...`), ссылку на отчёт и следующее действие (если есть WARN/BLOCKED).

## Fail-fast и вопросы
- Нет активного тикета/QA чеклиста? Попроси оформить `/tasks-new` или обновить `docs/.active_ticket`.
- Отчёт не записался? Перезапусти CLI команду и приложи stderr; без отчёта гейт заблокирует merge.
- Нет автотестов/логов среды — запроси у команды или зафиксируй объём непокрытых зон.

## Ожидаемый вывод
- Строка `Checkbox updated: <перечень QA пунктов>` и статус `READY|WARN|BLOCKED`.
- Ссылка на `reports/qa/<ticket>.json`, summary замечаний и дальнейшие шаги.

## Примеры CLI
- `/qa ABC-123`
- `!bash -lc 'claude-workflow qa --ticket "ABC-123" --branch "$(git rev-parse --abbrev-ref HEAD)" --report "reports/qa/ABC-123.json" --gate'`
