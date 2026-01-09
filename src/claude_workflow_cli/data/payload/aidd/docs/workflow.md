# Workflow Notes

## Context pack

Создать компактный контекст по якорям можно командой:

```
claude-workflow context-pack --ticket <TICKET> --agent <agent>
```

Файл сохраняется в `aidd/reports/context/<ticket>-<agent>.md`.

## Test cadence

Поле `.claude/settings.json → automation.tests.cadence` управляет автозапуском тестов:
- `on_stop` — запуск по Stop/SubagentStop (по умолчанию).
- `checkpoint` — запуск после `claude-workflow progress`.
- `manual` — запуск только при явном запросе.

Для ручного триггера используйте `AIDD_TEST_CHECKPOINT=1` или явный `AIDD_TEST_PROFILE`.
