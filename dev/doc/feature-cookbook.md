# Feature Cookbook

Этот конспект дополняет `aidd/docs/sdlc-flow.md` и помогает быстро свериться со стадиями
фичи. Перед тем как переходить к планированию или реализации, убедитесь, что
исследование завершено, план сформирован и review-plan/PRD review пройдены (через `/feature-dev-aidd:review-spec`).

## Idea → Research
- Запустите `/feature-dev-aidd:idea-new <ticket> [slug-hint]`: команда фиксирует активный тикет, сохраняет slug-hint в `aidd/docs/.active_feature`, автогенерирует `aidd/docs/prd/<ticket>.prd.md`. Аналитик читает доступные артефакты, заполняет PRD, формирует вопросы и фиксирует `## AIDD:RESEARCH_HINTS` (пути/ключевые слова/заметки).
- Поддерживайте `Status: READY/BLOCKED` и `## 10. Открытые вопросы`, указывая, какие данные нужны. После каждого обновления запускайте `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh --ticket <ticket>` — он подтвердит, что диалог заполнен и PRD не остался в `draft`.
- Затем запустите `/feature-dev-aidd:researcher <ticket>`: команда читает `## AIDD:RESEARCH_HINTS`, вызывает `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket> --auto --deep-code` и обновляет `aidd/docs/research/<ticket>.md`.

## Research → Plan
- Запускайте `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket> --auto --deep-code` столько раз, сколько требуется, чтобы `aidd/reports/research/<ticket>-targets.json` и `<ticket>-context.json` отражали актуальные каталоги/ключевые слова/`code_index`. Приложите список команд (`rg`, `find`, `python`) в `aidd/docs/research/<ticket>.md`.
- Через `/feature-dev-aidd:researcher <ticket>` заполните `aidd/docs/research/<ticket>.md` (шаблон `aidd/docs/research/template.md`): точки интеграции, что переиспользуем (как/риски/тесты/контракты), call/import graph по `code_index`, обязательные проверки. Секции «Commands/Artifacts» помогают downstream-команде повторить шаги.
- Обновите PRD/tasklist ссылками на research и пометьте `Status: reviewed`, затем перед `/feature-dev-aidd:plan-new` выполните `${CLAUDE_PLUGIN_ROOT}/tools/research-check.sh --ticket <ticket>`; блокирующие действия перенесите в `aidd/docs/plan/<ticket>.md` и `aidd/docs/tasklist/<ticket>.md`.

## Plan → Review-spec → Implementation
- Проверяйте, что план покрывает все директории из `aidd/reports/research/<ticket>-targets.json`, содержит секцию «Architecture & Patterns» (KISS/YAGNI/DRY/SOLID, service layer + adapters/ports), reuse-точки и ссылки на research.
- Используйте `/feature-dev-aidd:review-spec`: блокеры должны быть закрыты, иначе `tasks-new` и `implement` недоступны.
- Во время реализации держите `aidd/reports/research/<ticket>-context.json` в актуальном состоянии (`${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket> --auto --deep-code` без `--dry-run`). Это обеспечит прохождение `gate-workflow` и напомнит команде о согласованных точках интеграции.

## Миграция на agent-first
1. Обновите плагин через marketplace и запустите `/feature-dev-aidd:aidd-init`, чтобы недостающие файлы появились в `./aidd` без перезаписи пользовательских правок.
2. Сверьте `templates/aidd` с вашим `aidd/` и перенесите новые секции в PRD/tasklist/research (особенно `Commands/Reports`).
3. Для активных тикетов прогоните `${CLAUDE_PLUGIN_ROOT}/tools/research.sh --ticket <ticket> --auto` и `${CLAUDE_PLUGIN_ROOT}/tools/analyst-check.sh --ticket <ticket>`, чтобы обновить baseline и статусы.
