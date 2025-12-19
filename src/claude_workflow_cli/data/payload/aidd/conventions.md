# conventions.md

- **Стиль кода**: придерживаемся KISS/YAGNI/MVP; используем JetBrains/Google style (Spotless + ktlint при наличии).
- **Установка**: `claude-workflow init --target . [--commit-mode ... --enable-ci --prompt-locale en]` разворачивает payload в `./aidd`; команды/агенты читают артефакты только из этого каталога.
- **Ветки**: создаём через `git checkout -b` по пресетам (`feature/<TICKET>`, `feat/<scope>`, `hotfix/<TICKET>`).
- **Коммиты**: оформляем `git commit`, сообщения валидируются правилами `config/conventions.json`.
- **Документация**: PRD (`aidd/docs/prd/<ticket>.prd.md`), план (`aidd/docs/plan/<ticket>.md`), tasklist (`aidd/docs/tasklist/<ticket>.md`), при необходимости ADR (`aidd/docs/adr/*.md`); активные маркеры — `aidd/docs/.active_*`.
- **Автогейты**: базовый цикл требует готовности PRD/плана/tasklist (`aidd/docs/tasklist/<ticket>.md`) и новых `- [x]` после изменений в коде (`claude-workflow progress --source <implement|qa|review>`); дополнительные проверки (`tests_required`, `qa`, `deps_allowlist`) настраиваются в `config/gates.json`.
- **Тесты**: `${CLAUDE_PLUGIN_ROOT:-./aidd}/.claude/hooks/format-and-test.sh` запускается автоматически после записей (`SKIP_AUTO_TESTS=1` отключает автозапуск, `STRICT_TESTS=1` делает падение тестов блокирующим); при необходимости запустите вручную `bash ${CLAUDE_PLUGIN_ROOT:-./aidd}/.claude/hooks/format-and-test.sh`.
- **Контроль зависимостей**: актуальный allowlist — `config/allowed-deps.txt`, изменения проходят через ревью.
