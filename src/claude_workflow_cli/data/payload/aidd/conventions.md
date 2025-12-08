# conventions.md

- **Стиль кода**: придерживаемся KISS/YAGNI/MVP; используем JetBrains/Google style (Spotless + ktlint при наличии).
- **Ветки**: создаём через `git checkout -b` по пресетам (`feature/<TICKET>`, `feat/<scope>`, `hotfix/<TICKET>`).
- **Коммиты**: оформляем `git commit`, сообщения валидируются правилами `config/conventions.json`.
- **Документация**: PRD (`aidd/docs/prd/<ticket>.prd.md`), план (`aidd/docs/plan/<ticket>.md`), tasklist (`aidd/docs/tasklist/<ticket>.md`), при необходимости ADR (`aidd/docs/adr/*.md`).
- **Автогейты**: базовый цикл требует готовности PRD/плана/tasklist (`aidd/docs/tasklist/<ticket>.md`); дополнительные проверки включаются флагами в `config/gates.json`.
- **Тесты**: `.claude/hooks/format-and-test.sh` запускается автоматически после записей; при длительных правках можно вызвать его вручную.
- **Контроль зависимостей**: актуальный allowlist — `config/allowed-deps.txt`, изменения проходят через ревью.
