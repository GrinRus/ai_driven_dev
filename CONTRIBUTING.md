# Руководство по вкладу

Спасибо за интерес к проекту! Ниже - короткий и практичный гайд, чтобы изменения были прозрачными и воспроизводимыми.

## TL;DR
- Для крупных изменений заведите issue или ссылку на ADR/PRD.
- Работайте из веток `feature/<ticket>` или `feat/<scope>` (см. `config/conventions.json`).
- Формируйте сообщения коммитов вручную по шаблонам из `config/conventions.json`.
- Перед PR запустите `scripts/ci-lint.sh` (или `aidd/hooks/format-and-test.sh` в рабочем workspace).
- Обновляйте `README.md` и `README.en.md` вместе (и поле _Last sync_).
- Если трогаете runtime/payload (`aidd/`, `.claude/`, `.claude-plugin/`), используйте sync-процедуру.

## Процесс работы
1. **Обсуждение.** Issue или ссылка на ADR/PRD, если меняется архитектура/поведение.
2. **Ветка.** `git checkout -b feature/<TICKET>` или другой паттерн из `config/conventions.json`.
3. **Коммиты.** Сообщения - по правилам `config/conventions.json`.
4. **Тесты.** Запустите `scripts/ci-lint.sh` (или `aidd/hooks/format-and-test.sh` для установленного workflow).
5. **Документация.** Обновите README (RU/EN) и связанные файлы в `doc/dev/`.
6. **PR.** Приложите ссылки на задачи и список проверок.

## Payload и runtime
Единственный источник правды для runtime-артефактов - `src/claude_workflow_cli/data/payload`.

Если меняете `.claude/`, `.claude-plugin/` или `aidd/**`:
- Перед правками: `scripts/sync-payload.sh --direction=to-root`.
- После правок: `scripts/sync-payload.sh --direction=from-root && python3 tools/check_payload_sync.py`.
- По необходимости: `python3 tools/payload_audit.py`.

## Документация и переводы
- Любые изменения в README делайте в `README.md` и синхронно переносите в `README.en.md`.
- Обновляйте _Last sync_ в англоязычной версии.
- Если меняется поведение скриптов, дополните `doc/dev/workflow.md` и `doc/dev/customization.md`.

## Безопасность
- Не ослабляйте ограничения `.claude/settings.json` без обсуждения.
- Новые гейты и правила документируйте в `config/gates.json` и `doc/dev/`.

## Релизы и поддержка
- Процесс релизов и чеклисты: `doc/dev/release-notes.md`.
- Аудит дистрибутива: `doc/dev/distro-audit.md`.
