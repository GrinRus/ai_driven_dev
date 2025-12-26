---
description: "План реализации по согласованному PRD + валидация"
argument-hint: "<TICKET> [note...]"
lang: ru
prompt_version: 1.0.2
source_version: 1.0.2
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
model: inherit
disable-model-invocation: false
---

## Контекст
Команда`/plan-new`преобразует PRD со статусом READY (диалог) и PRD Review READY в технический план (`@aidd/docs/plan/<ticket>.md`) и сразу прогоняет валидацию. После завершения шаг используют`/tasks-new`,`/implement`. Свободный ввод после тикета используй как уточнение требований и внеси его в план.

## Входные артефакты
- `@aidd/docs/prd/<ticket>.prd.md` — статус READY и заполненный`## PRD Review`со статусом READY обязательны.
- `@aidd/docs/research/<ticket>.md` — точки интеграции и reuse.
- ADR (если есть) — вспомогательные материалы.

## Когда запускать
- После`/idea-new`и`/review-prd`, когда PRD READY и PRD Review READY, а также есть результаты Researcher.
- Повторный запуск возможен для актуализации плана (например, при существенных добавлениях к PRD).

## Автоматические хуки и переменные
- Саб-агенты`planner`и`validator`вызываются в рамках команды. Если validator возвращает BLOCKED, команда должна запросить уточнения у пользователя.
-`gate-workflow`проверяет, что план существует перед изменением кода.
- Пресет`claude-presets/feature-plan.yaml`можно развернуть для типовых задач (Wave 7).

## Что редактируется
-`aidd/docs/plan/<ticket>.md`— основной результат.
- Раздел «Открытые вопросы» в PRD/плане — синхронизируй action items из`## PRD Review`.

## Пошаговый план
1. Убедись, что PRD имеет`Status: READY`и актуальный`## PRD Review`со статусом READY. Если нет — сначала запусти `/review-prd <ticket>`.
2. Вызови саб-агента **planner**: он создаст`aidd/docs/plan/<ticket>.md`с архитектурой (KISS/YAGNI/DRY/SOLID, паттерны service layer + adapters/ports по умолчанию), reuse-точками, итерациями, DoD и ссылками на модули.
3. Сразу запусти **validator**. Если он сообщает BLOCKED, верни список вопросов пользователю и дождись ответов, затем обнови план и повтори проверку.
4. Перенеси action items и открытые вопросы из`## PRD Review`в план (разделы «Риски», «Открытые вопросы»), а также обнови одноимённый блок в самом PRD.
5. При необходимости разверни пресет`feature-plan`(см.`claude-presets/feature-plan.yaml`), чтобы добавить типовые итерации.

## Fail-fast и вопросы
- Нет READY PRD/PRD Review или отсутствует research — остановись и попроси пользователя завершить предыдущие шаги.
- При неопределённых зависимостях/интеграциях сформулируй вопросы до перехода к реализационной фазе.
- Если planner/validator вернул BLOCKED, обязательно перечисли, какая информация нужна.

## Ожидаемый вывод
-`aidd/docs/plan/<ticket>.md`заполнен, содержит секцию «Architecture & Patterns» (границы/паттерны/реuse), итерации с DoD, ссылки на файлы, список рисков и открытых вопросов.
- Validator дал PASS; если нет — команда получила вопросы.
- PRD обновлён (перенесены открытые вопросы/action items).

## Примеры CLI
-`/plan-new ABC-123`
-`!bash -lc 'claude-workflow preset feature-plan --ticket "ABC-123"'`(для подсказок)
