# Feature Cookbook

Этот конспект дополняет `workflow.md` и помогает быстро свериться со стадиями
фичи. Перед тем как переходить к планированию или реализации, убедитесь, что
исследование завершено, план сформирован и review-plan/PRD review пройдены (или выполнена команда `/review-spec`).

## Idea → Research
- Запустите `/idea-new <ticket> [slug-hint]`: команда фиксирует активный тикет, сохраняет slug-hint пользователя в `aidd/docs/.active_feature`, автогенерирует `aidd/docs/prd/<ticket>.prd.md` и вызывает `claude-workflow research --ticket <ticket> --auto --deep-code [--langs ... --reuse-only]`. Аналитик начинает со slug-hint, затем читает `aidd/docs/research/<ticket>.md`, `reports/research/*.json` (`code_index`/`reuse_candidates`), фиксирует источники в PRD и только при нехватке данных запускает Q&A по формату `Вопрос N (Blocker|Clarification)` с `Зачем/Варианты/Default` (ответы: `Ответ N: ...`).
- Поддерживайте `Status: READY/BLOCKED` и `## 10. Открытые вопросы`, указывая, какие данные нужны (ссылки на файлы/команды). После каждого обновления запускайте `claude-workflow analyst-check --ticket <ticket>` — он подтвердит, что диалог заполнен и PRD не остался в `draft`.
- Если `claude-workflow research --auto --deep-code` не находит контекст, Researcher разворачивает `aidd/docs/templates/research-summary.md`, добавляет baseline «Контекст пуст...» и перечисляет команды/пути, которые уже проверены; только после этого просите команду уточнить `--paths/--keywords`.

## Research → Plan
- Запускайте `claude-workflow research --ticket <ticket> --auto --deep-code` столько раз, сколько требуется, чтобы `reports/research/<ticket>-targets.json` и `<ticket>-context.json` отражали актуальные каталоги/ключевые слова/`code_index`. Приложите список команд (`rg`, `find`, `python`) в `aidd/docs/research/<ticket>.md`.
- Через `/researcher <ticket>` заполните `aidd/docs/research/<ticket>.md` (шаблон `aidd/docs/templates/research-summary.md`): точки интеграции, что переиспользуем (как/риски/тесты/контракты), call/import graph по `code_index`, обязательные проверки. Секции «Commands/Artifacts» помогают downstream-команде повторить шаги.
- Обновите PRD/tasklist ссылками на research и пометьте `Status: reviewed`, когда команды согласованы; блокирующие действия перенесите в `aidd/docs/plan/<ticket>.md` и `aidd/docs/tasklist/<ticket>.md`.

## Plan → Review-spec → Implementation
- Проверяйте, что план покрывает все директории из `reports/research/<ticket>-targets.json`, содержит секцию «Architecture & Patterns» (KISS/YAGNI/DRY/SOLID, service layer + adapters/ports), reuse-точки и ссылки на research.
- Используйте `/review-spec` (или `/review-plan` перед `/review-prd`): блокеры должны быть закрыты, иначе `tasks-new` и `implement` недоступны.
- Во время реализации держите `reports/research/<ticket>-context.json` в актуальном состоянии (`claude-workflow research --ticket <ticket> --auto --deep-code` без `--dry-run`). Это обеспечит прохождение `gate-workflow` и напомнит команде о согласованных точках интеграции.

## Миграция на agent-first
> Repo-only: `scripts/sync-payload.sh` и `tools/check_payload_sync.py` доступны только в корне репозитория.

1. Выполните `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py`, чтобы новые шаблоны PRD/tasklist/research и команда `/idea-new` попали в рабочее дерево и в payload CLI.
2. Скопируйте обновлённые `aidd/agents|commands` и `aidd/prompts/en/**`, затем прогоните `claude-workflow research --ticket <ticket> --auto` и `claude-workflow analyst-check --ticket <ticket>` для каждой активной фичи — это подтянет baseline, отчёты и PRD к новым секциям «Commands/Reports».
3. Tasklist должен содержать поля `Reports/Commands`, а в ответах агентов перечисляются запущенные CLI. Smoke-тест `claude-workflow smoke` поможет убедиться, что миграция завершена.
