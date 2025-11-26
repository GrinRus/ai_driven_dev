# Tasklist — шаблон фичи

Tasklist хранится по адресу `docs/tasklist/&lt;ticket&gt;.md` и содержит фронт-маттер с основными артефактами фичи. Скопируйте блок ниже, подставьте ticket/slug-hint и ссылки, либо воспользуйтесь `/tasks-new &lt;ticket&gt;` — команда создаст файл автоматически.

```markdown
---
Ticket: &lt;ticket&gt;
Slug hint: &lt;slug-hint или повторите ticket&gt;
Feature: &lt;display name&gt;
Status: draft
PRD: docs/prd/&lt;ticket&gt;.prd.md
Plan: docs/plan/&lt;ticket&gt;.md
Research: docs/research/&lt;ticket&gt;.md
Reports:
  Research: reports/research/&lt;ticket&gt;-context.json
  QA: reports/qa/&lt;ticket&gt;.json
Commands:
  Progress: claude-workflow progress --source &lt;stage&gt; --ticket "&lt;ticket&gt;"
  Tests: ./gradlew test --tests &lt;pattern&gt;
Updated: YYYY-MM-DD
---

# Tasklist — &lt;Feature title&gt;

## Как отмечать прогресс
- После каждого инкремента заменяйте выполненные пункты `- [ ]` на `- [x]`, добавляя в конце `— YYYY-MM-DD • итерация N` и ссылку на PR/commit или краткое описание результата.
- Если закрываете часть большого пункта, добавляйте отдельный `- [x]` с пояснением, что именно готово (история прогресса сохраняется).
- В ответах агентов используйте строку `Checkbox updated: …`, чтобы перечислить закрытые элементы и договорённости на следующий шаг.
- Перед завершением `/implement`, `/qa`, `/review` запускайте `claude-workflow progress --source <этап> --ticket "&lt;ticket&gt;"` — утилита проверит, что появились новые `- [x]` и подскажет, если tasklist не обновлён.
- После отчётов QA/Review/Research добавляйте handoff-задачи через `claude-workflow tasks-derive --source <qa|review|research> --append --ticket "&lt;ticket&gt;"`; новые `- [ ]` должны ссылаться на соответствующий `reports/<source>/...`.

## 1. Аналитика и дизайн
- [ ] PRD и дизайн синхронизированы, риски зафиксированы (`docs/prd/&lt;ticket&gt;.prd.md`, макеты).
- [ ] Метрики успеха и ограничения подтверждены артефактами (`docs/.active_feature`, `reports/research/&lt;ticket&gt;-context.json`).
- [ ] Согласован объём разработки и зависимости (ссылки на ADR/план).

## 2. Реализация
- [ ] Код реализован в целевых модулях, тесты покрывают новые ветви (укажите путь к diff и лог тестов).
- [ ] Учтены негативные сценарии, feature flags/конфиги обновлены (`config/*.json`, `settings/*.yaml`).
- [ ] `.claude/hooks/format-and-test.sh` и ручные команды (`./gradlew …`) выполняются без ошибок (приложите выдержки).

## 3. QA / Проверки
- [ ] Обновлены тест-кейсы и тестовые данные (ссылки на `docs/testcases/*.md` или `tests/**`).
- [ ] Прогнаны unit/integration/e2e, результаты задокументированы (логи `./gradlew test`, `pytest`, `claude-workflow qa --gate`).
- [ ] Проведено ручное тестирование или UAT (протокол в `docs/tasklist/<ticket>.md` или отдельном отчёте; `Checkbox updated` перечисляет QA-пункты).

## 4. Интеграция с гейтами
- [ ] READY: `docs/.active_ticket` указывает на `&lt;ticket&gt;`, чеклист READY.
- [ ] Researcher: `docs/research/&lt;ticket&gt;.md` со статусом `Status: reviewed`.
- [ ] API/DB: обновлены контракты и миграции, гейты зелёные.
- [ ] Tests: включены новые тесты, `gate-tests` завершился успешно.

## 5. Документация и релиз
- [ ] README и связанные руководства отражают изменения (укажите пути к файлам).
- [ ] Добавлены заметки в `docs/release-notes.md` и `CHANGELOG.md`.
- [ ] Подготовлен план выката/отката, инструментальные инструкции (`scripts/deploy.sh`, runbook).

## 6. Пострелиз
- [ ] Собраны метрики и обратная связь (источник данных, путь к дашборду/отчёту).
- [ ] Закрыты инциденты и действия по результатам (ссылка на issue/документ).
- [ ] Обновлён roadmap/бэклог (используйте собственные источники, например `docs/roadmap.md`).

## 7. Примечания
- Свободное поле для договёрностей, ссылок, action items.
```

Обновляйте tasklist вместе с прогрессом фичи: чекбоксы помогают гейтам и команде видеть статус, а фронт-маттер обеспечивает быстрый переход ко всем связанным документам. В ответах агентов фиксируйте строку `Checkbox updated: ...` и ссылкуйте на обновлённые пункты — это упростит автоматические проверки `claude-workflow progress`.
