# Release Notes Process

Документ описывает, как готовить и публиковать релизы Claude Code workflow.

## Версионирование
- Используем семантическую схему `MAJOR.MINOR.PATCH`.
- `MAJOR` — несовместимые изменения (структура артефактов, критические API-изменения скриптов).
- `MINOR` — новые возможности и улучшения, сохраняющие обратную совместимость.
- `PATCH` — исправления багов, обновления документации или улучшения, не влияющие на интерфейсы.
- Текущая версия указывается в README и релизных заметках.

## Структура release notes
Каждый релиз получает файл/раздел вида:

```
## vX.Y.Z — YYYY-MM-DD
### Added
- ...

### Changed
- ...

### Fixed
- ...

### Migration
- ...
```

Секции «Migration» и «Breaking changes» заполняются только при необходимости.

## Подготовка релиза
- [ ] Обновить `README.md` и `README.en.md` (TL;DR, список фич, ссылки на новые документы).
- [ ] Проверить Wave backlog — закрыть выполненные пункты и создать Wave 2/3 для новых задач.
- [ ] Обновить демо (`examples/gradle-demo/`) и убедиться, что `examples/apply-demo.sh` отрабатывает без ошибок.
- [ ] Убедиться, что CI (`.github/workflows/ci.yml`) проходит на ветке `main`.
- [ ] Выполнить `scripts/ci-lint.sh` локально.
- [ ] Зафиксировать изменения в `docs/release-notes.md`.

## Публикация релиза
- [ ] Проставить тег `vX.Y.Z` (annotated tag).
- [ ] Создать GitHub Release и вложить основные тезисы из release notes.
- [ ] Загрузить артефакты из `dist/`: wheel/tarball, `claude-workflow-payload-<tag>.zip`, `claude-workflow-manifest-<tag>.json` и соответствующие `.sha256`.
- [ ] Приложить ссылки на новые/обновлённые документы (usage/customization/command reference).
- [ ] Обновить `docs/usage-demo.md`, если поведение установки изменилось.
- [ ] Сообщить в выбранных каналах (Slack, email, команда).

## Пост-релиз
- [ ] Создать задачу на планирование следующего релиза.
- [ ] Собрать обратную связь от пользователей (issues, комментарии).
- [ ] Проверить, что `.claude/settings.json` соответствует политике доступа.
- [ ] Обновить Wave backlog: перенести оставшиеся задачи в следующую волну.

Храните заметки в одном файле (`docs/release-notes.md`), добавляя записи в обратном хронологическом порядке.

## vNext — YYYY-MM-DD

### Changed
- Tasklist чеклисты перенесены в `docs/tasklist/<slug>.md`: обновлены шаблоны, init/CLI пресеты, гейты и документация, добавлена автомиграция через `scripts/migrate-tasklist.py` и `set_active_feature.py`.

### Migration
- Запустить `python3 scripts/migrate-tasklist.py --slug <slug>` в проектах с legacy `tasklist.md`, либо повторно вызвать `tools/set_active_feature.py <slug>` для автопереноса. Убедиться, что гейты используют новый путь и PRD/план ссылаются на `docs/tasklist/<slug>.md`.
