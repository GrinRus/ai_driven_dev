# Feature Cookbook

Этот конспект дополняет `workflow.md` и помогает быстро свериться со стадиями
фичи. Перед тем как переходить к планированию или реализации, убедитесь, что
исследование завершено и рекомендации приняты командой.

## Idea → Research
- Запустите `/idea-new <ticket> [slug-hint]`: команда фиксирует активный тикет, автогенерирует `docs/prd/<ticket>.prd.md` и вызывает `claude-workflow research --ticket <ticket> --auto`. Аналитик сначала читает `doc/backlog.md`, `docs/research/<ticket>.md`, `reports/research/*.json`, фиксирует источники в PRD, и только если репозитория недостаточно — формирует вопросы формата `Вопрос/Ответ N`.
- Поддерживайте `Status: READY/BLOCKED` и `## 10. Открытые вопросы`, указывая, какие данные нужны (ссылки на файлы/команды). После каждого обновления запускайте `claude-workflow analyst-check --ticket <ticket>` — он подтвердит, что диалог заполнен и PRD не остался в `draft`.
- Если `claude-workflow research --auto` не находит контекст, Researcher разворачивает `docs/templates/research-summary.md`, добавляет baseline «Контекст пуст...» и перечисляет команды/пути, которые уже проверены; только после этого просите команду уточнить `--paths/--keywords`.

## Research → Plan
- Запускайте `claude-workflow research --ticket <ticket>` столько раз, сколько требуется, чтобы `reports/research/<ticket>-targets.json` и `<ticket>-context.json` отражали актуальные каталоги/ключевые слова. Приложите список команд (`rg`, `find`, `python`) в `docs/research/<ticket>.md`.
- Через `/researcher <ticket>` заполните `docs/research/<ticket>.md` (шаблон `docs/templates/research-summary.md`): точки интеграции, что переиспользуем, какие тесты обязательны. Секции «Commands/Artifacts» помогают downstream-команде повторить шаги.
- Обновите PRD/tasklist ссылками на research и пометьте `Status: reviewed`, когда команды согласованы; блокирующие действия перенесите в `docs/plan/<ticket>.md` и `docs/tasklist/<ticket>.md`.

## Plan → Implementation
- Проверяйте, что план покрывает все директории из `reports/research/<ticket>-targets.json`.
- Во время реализации держите `reports/research/<ticket>-context.json` в актуальном
  состоянии (`claude-workflow research --ticket <ticket>` без `--dry-run`). Это
  обеспечит прохождение `gate-workflow` и напомнит команде о согласованных
  точках интеграции.

## Миграция на agent-first
1. Выполните `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py`, чтобы новые шаблоны PRD/tasklist/research и команда `/idea-new` попали в рабочее дерево и в payload CLI.
2. Скопируйте обновлённые `.claude/agents|commands` и `prompts/en/**`, затем прогоните `claude-workflow research --ticket <ticket> --auto` и `claude-workflow analyst-check --ticket <ticket>` для каждой активной фичи — это подтянет baseline, отчёты и PRD к новым секциям «Commands/Reports».
3. Tasklist должен содержать поля `Reports/Commands`, а в ответах агентов перечисляются запущенные CLI. Smoke-тест `scripts/smoke-workflow.sh` и `scripts/ci-lint.sh` помогут убедиться, что миграция завершена.
