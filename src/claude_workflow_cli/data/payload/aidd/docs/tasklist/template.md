---
Ticket: <ticket>
Slug hint: <slug-hint or repeat ticket>
Feature: <display name>
Status: draft
PRD: aidd/docs/prd/<ticket>.prd.md
Plan: aidd/docs/plan/<ticket>.md
Research: aidd/docs/research/<ticket>.md
Reports:
  Research: aidd/reports/research/<ticket>-context.json
  QA: aidd/reports/qa/<ticket>.json
Commands:
  Progress: claude-workflow progress --source <stage> --ticket "<ticket>"
  Tests: <test-runner> <args>
Updated: YYYY-MM-DD
---

# Tasklist — <Feature title>

## Как отмечать прогресс
- После каждого инкремента заменяйте выполненные пункты `- [ ]` на `- [x]`, добавляя в конце `— YYYY-MM-DD • итерация N` и ссылку на PR/commit или краткое описание результата.
- Если закрываете часть большого пункта, добавляйте отдельный `- [x]` с пояснением, что именно готово (история прогресса сохраняется).
- В ответах агентов используйте строку `Checkbox updated: …`, чтобы перечислить закрытые элементы и договорённости на следующий шаг.
- Перед завершением `/implement`, `/qa`, `/review` запускайте `claude-workflow progress --source <этап> --ticket "<ticket>"` — утилита проверит, что появились новые `- [x]` и подскажет, если tasklist не обновлён.
- После отчётов QA/Research добавляйте handoff-задачи через `claude-workflow tasks-derive --source <qa|research> --append --ticket "<ticket>"`; новые `- [ ]` должны ссылаться на соответствующий `aidd/reports/<source>/...`.

## AIDD:NEXT_3
- [ ] <первый приоритетный чекбокс>
- [ ] <второй приоритетный чекбокс>
- [ ] <третий приоритетный чекбокс>

## AIDD:CONTEXT_PACK
- Focus: <какой чекбокс из AIDD:NEXT_3>
- Files: <2-8 путей/модулей>
- Invariants: <1-3 пункта>
- Plan refs: <итерация/секция плана>
- Next: <что дальше>
- Limit: <= 20 lines / <= 1200 chars

## AIDD:NON_NEGOTIABLES
- <что нельзя нарушать>

## AIDD:OPEN_QUESTIONS
- <вопрос> → <кто отвечает> → <срок>

## AIDD:RISKS_TOP5
- <риск> → <митигация>

## AIDD:DECISIONS
- <решение> → <почему>

## AIDD:INBOX_DERIVED
- [ ] <handoff из QA/Review/Research со ссылкой на report>

## AIDD:CHECKLIST
- Используйте разделы 1–6 ниже как полный чеклист с критериями готовности.

## 1. Аналитика и дизайн
- [ ] PRD и дизайн синхронизированы, риски зафиксированы (`aidd/docs/prd/<ticket>.prd.md`, макеты).
- [ ] Метрики успеха и ограничения подтверждены артефактами (`aidd/docs/.active_feature`, `aidd/reports/research/<ticket>-context.json`).
- [ ] Согласован объём разработки и зависимости (ссылки на ADR/план).

## 2. Реализация
- [ ] Код реализован в целевых модулях, тесты покрывают новые ветви (укажите путь к diff и лог тестов).
- [ ] Учтены негативные сценарии, feature flags/конфиги обновлены (`config/*.json`, `settings/*.yaml`).
- [ ] Test profile: `<fast|targeted|full|none>` (ссылка на `aidd/.cache/test-policy.env`), Tests run: `<команды/задачи>`.
- [ ] `${CLAUDE_PLUGIN_ROOT:-./aidd}/hooks/format-and-test.sh` и ручные команды (например, `pytest`, `npm test`, `go test`) выполняются без ошибок (приложите выдержки).

## 3. QA / Проверки
- [ ] Обновлены тест-кейсы и тестовые данные (ссылки на `docs/testcases/*.md` или `tests/**`).
- [ ] Прогнаны unit/integration/e2e, результаты задокументированы (логи тест-раннера, `claude-workflow qa --gate`).
- [ ] Проведено ручное тестирование или UAT (протокол в `aidd/docs/tasklist/<ticket>.md` или отдельном отчёте; `Checkbox updated` перечисляет QA-пункты).
- [ ] Traceability: для каждого acceptance criteria из PRD указано, как проверено (ссылка на тест/лог/шаг).

## AIDD:QA_TRACEABILITY
- <AC-1> → <тест/лог/шаг>
- <AC-2> → <тест/лог/шаг>

## 4. Интеграция с гейтами
- [ ] READY: `aidd/docs/.active_ticket` указывает на `<ticket>`, чеклист READY.
- [ ] Researcher: `aidd/docs/research/<ticket>.md` со статусом `Status: reviewed`.
- [ ] API/DB: обновлены контракты и миграции, гейты зелёные.
- [ ] Tests: включены новые тесты, `gate-tests` завершился успешно.

## 5. Документация и релиз
- [ ] README и связанные руководства отражают изменения (укажите пути к файлам).
- [ ] Добавлены заметки в release notes и `CHANGELOG.md` (если ведутся в проекте).
- [ ] Подготовлен план выката/отката, инструментальные инструкции (`scripts/deploy.sh`, runbook).

## 6. Пострелиз
- [ ] Собраны метрики и обратная связь (источник данных, путь к дашборду/отчёту).
- [ ] Закрыты инциденты и действия по результатам (ссылка на issue/документ).
- [ ] Обновлён roadmap/бэклог (используйте собственные источники, например `docs/roadmap.md`).

## 7. Примечания
- Свободное поле для договёрностей, ссылок, action items.

## AIDD:PROGRESS_LOG
- <YYYY-MM-DD> — <что сделано> — <ссылка/лог/PR>
