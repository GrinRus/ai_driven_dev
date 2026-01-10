# Feature Cookbook

Этот конспект дополняет `aidd/docs/sdlc-flow.md` и помогает быстро свериться со стадиями
фичи. Перед тем как переходить к планированию или реализации, убедитесь, что
исследование завершено, план сформирован и review-plan/PRD review пройдены (через `/review-spec`).

## Idea → Research
- Запустите `/idea-new <ticket> [slug-hint]`: команда фиксирует активный тикет, сохраняет slug-hint в `aidd/docs/.active_feature`, автогенерирует `aidd/docs/prd/<ticket>.prd.md`. Аналитик читает доступные артефакты, заполняет PRD, формирует вопросы и фиксирует `## AIDD:RESEARCH_HINTS` (пути/ключевые слова/заметки).
- Поддерживайте `Status: READY/BLOCKED` и `## 10. Открытые вопросы`, указывая, какие данные нужны. После каждого обновления запускайте `claude-workflow analyst-check --ticket <ticket>` — он подтвердит, что диалог заполнен и PRD не остался в `draft`.
- Затем запустите `/researcher <ticket>`: команда читает `## AIDD:RESEARCH_HINTS`, вызывает `claude-workflow research --ticket <ticket> --auto --deep-code` и обновляет `aidd/docs/research/<ticket>.md`.

## Research → Plan
- Запускайте `claude-workflow research --ticket <ticket> --auto --deep-code` столько раз, сколько требуется, чтобы `aidd/reports/research/<ticket>-targets.json` и `<ticket>-context.json` отражали актуальные каталоги/ключевые слова/`code_index`. Приложите список команд (`rg`, `find`, `python`) в `aidd/docs/research/<ticket>.md`.
- Через `/researcher <ticket>` заполните `aidd/docs/research/<ticket>.md` (шаблон `aidd/docs/research/template.md`): точки интеграции, что переиспользуем (как/риски/тесты/контракты), call/import graph по `code_index`, обязательные проверки. Секции «Commands/Artifacts» помогают downstream-команде повторить шаги.
- Обновите PRD/tasklist ссылками на research и пометьте `Status: reviewed`, затем перед `/plan-new` выполните `claude-workflow research-check --ticket <ticket>`; блокирующие действия перенесите в `aidd/docs/plan/<ticket>.md` и `aidd/docs/tasklist/<ticket>.md`.

## Plan → Review-spec → Implementation
- Проверяйте, что план покрывает все директории из `aidd/reports/research/<ticket>-targets.json`, содержит секцию «Architecture & Patterns» (KISS/YAGNI/DRY/SOLID, service layer + adapters/ports), reuse-точки и ссылки на research.
- Используйте `/review-spec`: блокеры должны быть закрыты, иначе `tasks-new` и `implement` недоступны.
- Во время реализации держите `aidd/reports/research/<ticket>-context.json` в актуальном состоянии (`claude-workflow research --ticket <ticket> --auto --deep-code` без `--dry-run`). Это обеспечит прохождение `gate-workflow` и напомнит команде о согласованных точках интеграции.

## Миграция на agent-first
1. Обновите payload в проекте через `claude-workflow sync` или `claude-workflow upgrade --force`, чтобы свежие шаблоны PRD/tasklist/research и команда `/idea-new` попали в рабочее дерево.
2. Скопируйте обновлённые `aidd/agents|commands` (или переустановите workflow), затем прогоните `claude-workflow research --ticket <ticket> --auto` и `claude-workflow analyst-check --ticket <ticket>` для каждой активной фичи — это подтянет baseline, отчёты и PRD к новым секциям «Commands/Reports».
3. Tasklist должен содержать поля `Reports/Commands`, а в ответах агентов перечисляются запущенные CLI. Smoke-тест `claude-workflow smoke` поможет убедиться, что миграция завершена.
