# /conventions-set

**Назначение**: переключить активный режим сообщений коммитов.

**Аргументы**: `<commit-mode>`
- допустимые значения: `ticket-prefix`, `conventional`, `mixed`.

**Пример**
```
/conventions-set conventional
```

**Результат**
- Запускает `python3 scripts/conventions_set.py --commit-mode <mode>`.
- Обновляет поле `commit.mode` в `config/conventions.json`.

**Типичные ошибки**
- «Unknown mode» — передано значение вне списка.
- Конфликт при записи файла — закройте `config/conventions.json` в IDE, если он открыт в режиме только чтения.

**Советы**
- После смены режима выполните `/branch-new` и `/commit`, чтобы убедиться, что новое правило применяется.
- Добавьте `commit-msg` hook (см. `docs/customization.md`), чтобы коммиты соответствовали новому формату.
