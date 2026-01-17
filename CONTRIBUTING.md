# Руководство по вкладу

Спасибо за интерес к проекту! Ниже - короткий и практичный гайд, чтобы изменения были прозрачными и воспроизводимыми.

## TL;DR
- Для крупных изменений заведите issue или ссылку на ADR/PRD.
- Работайте из веток `feature/<ticket>` или `feat/<scope>` (см. `config/conventions.json`).
- Формируйте сообщения коммитов вручную по шаблонам из `config/conventions.json`.
- Перед PR запустите `tests/repo_tools/ci-lint.sh` (или `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` в рабочем workspace).
- Если используете `pre-commit`, он запускает `tests/repo_tools/ci-lint.sh`.
- Обновляйте `README.md` и `README.en.md` вместе (и поле _Last sync_).
- Если трогаете runtime/шаблоны (`commands/`, `agents/`, `hooks/`, `templates/aidd/`), обновляйте связанные доки и тесты.

## Процесс работы
1. **Обсуждение.** Issue или ссылка на ADR/PRD, если меняется архитектура/поведение.
2. **Ветка.** `git checkout -b feature/<TICKET>` или другой паттерн из `config/conventions.json`.
3. **Коммиты.** Сообщения - по правилам `config/conventions.json`.
4. **Тесты.** Запустите `tests/repo_tools/ci-lint.sh` (или `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` для установленного workflow).
5. **Документация.** Обновите README (RU/EN) и `AGENTS.md`.
6. **PR.** Приложите ссылки на задачи и список проверок.

## Плагин и шаблоны
- Канонические промпты и хуки живут в `commands/`, `agents/`, `hooks/`.
- Шаблоны workspace лежат в `templates/aidd/` (они разворачиваются в `./aidd` командой `/feature-dev-aidd:aidd-init`).
- Рантайм-логика живёт в `tools/` (Python-entrypoint скрипты) и вызывается как `${CLAUDE_PLUGIN_ROOT}/tools/*.sh`.
- Локальный `aidd/` в репозитории используйте только для dogfooding; источником истины остаются `templates/aidd/`.

## Документация и переводы
- Любые изменения в README делайте в `README.md` и синхронно переносите в `README.en.md`.
- Обновляйте _Last sync_ в англоязычной версии.
- Если меняется поведение скриптов, дополните `AGENTS.md`.

## Безопасность
- Не ослабляйте ограничения `.claude/settings.json` без обсуждения.
- Новые гейты и правила документируйте в `config/gates.json` и `AGENTS.md`.

## Релизы и поддержка
- Процесс релизов и чеклисты: `AGENTS.md`.
- Аудит дистрибутива: `AGENTS.md`.
