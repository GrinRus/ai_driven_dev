---
description: "План реализации по согласованному PRD + валидация"
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
model: inherit
disable-model-invocation: false
---

## Контекст
Команда`/plan-new`преобразует утверждённый PRD в технический план (@docs/plan/`&lt;ticket&gt;`.md) и сразу прогоняет валидацию. После завершения шаг используют`/tasks-new`,`/implement`.

## Входные артефакты
- @docs/prd/`&lt;ticket&gt;`.prd.md — статус READY и заполненный`## PRD Review`обязательны.
- @docs/research/`&lt;ticket&gt;`.md — точки интеграции и reuse.
- @doc/backlog.md, ADR (если есть) — вспомогательные материалы.

## Когда запускать
- После`/idea-new`и`/review-prd`, когда PRD утверждён и есть результаты Researcher.
- Повторный запуск возможен для актуализации плана (например, при существенных добавлениях к PRD).

## Автоматические хуки и переменные
- Саб-агенты`planner`и`validator`вызываются в рамках команды. Если validator возвращает BLOCKED, команда должна запросить уточнения у пользователя.
-`gate-workflow`проверяет, что план существует перед изменением кода.
- Пресет`claude-presets/feature-plan.yaml`можно развернуть для типовых задач (Wave 7).

## Что редактируется
-`docs/plan/`&lt;ticket&gt;`.md`— основной результат.
- Раздел «Открытые вопросы» в PRD/плане — синхронизируй action items из`## PRD Review`.

## Пошаговый план
1. Убедись, что PRD имеет`Status: approved`и актуальный`## PRD Review`. Если нет — сначала запусти`/review-prd`&lt;ticket&gt;``.
2. Вызови саб-агента **planner**: он создаст`docs/plan/`&lt;ticket&gt;`.md`с архитектурой (KISS/YAGNI/DRY/SOLID, паттерны service layer + adapters/ports по умолчанию), reuse-точками, итерациями, DoD и ссылками на модули.
3. Сразу запусти **validator**. Если он сообщает BLOCKED, верни список вопросов пользователю и дождись ответов, затем обнови план и повтори проверку.
4. Перенеси action items и открытые вопросы из`## PRD Review`в план (разделы «Риски», «Открытые вопросы»), а также обнови одноимённый блок в самом PRD.
5. При необходимости разверни пресет`feature-plan`(см.`claude-presets/feature-plan.yaml`), чтобы добавить типовые итерации.

## Fail-fast и вопросы
- Нет approved PRD или отсутствует research — остановись и попроси пользователя завершить предыдущие шаги.
- При неопределённых зависимостях/интеграциях сформулируй вопросы до перехода к реализационной фазе.
- Если planner/validator вернул BLOCKED, обязательно перечисли, какая информация нужна.

## Ожидаемый вывод
-`docs/plan/`&lt;ticket&gt;`.md`заполнен, содержит секцию «Architecture & Patterns» (границы/паттерны/реuse), итерации с DoD, ссылки на файлы, список рисков и открытых вопросов.
- Validator дал PASS; если нет — команда получила вопросы.
- PRD обновлён (перенесены открытые вопросы/action items).

## Примеры CLI
-`/plan-new ABC-123`
-`!bash -lc 'claude-workflow preset feature-plan --ticket "ABC-123"'`(для подсказок)
