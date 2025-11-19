# Feature Backlog (Demo)

## DEMO-1 — Checkout Observability
- **Цель**: показать, как агент собирает вводные из репозитория.
- **Контекст**: стартуйте с `/idea-new DEMO-1`, затем сразу `claude-workflow research --ticket DEMO-1 --auto`, чтобы заполнить `reports/research/DEMO-1-(context|targets).json`.
- **Источники**: `doc/backlog.md`, `docs/prd.template.md`, `docs/templates/research-summary.md`, `reports/research/*.json` (после автозапуска Researcher).
- **Ожидания**:
  - Аналитик читает backlog/research/reports и заполняет PRD; задаёт вопросы пользователю только для пробелов и требует ответы формата `Ответ N: …`.
  - Researcher перечисляет запущенные команды (`rg "checkout" src/`, `python tools/list_modules.py`) и ссылки на файлы в `docs/research/DEMO-1.md`.
  - Implementer после каждой итерации запускает `claude-workflow progress --source implement --ticket DEMO-1` и прикладывает логи `.claude/hooks/format-and-test.sh` / `./gradlew test` в tasklist.
