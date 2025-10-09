# /branch-new

**Назначение**: создать или переключиться на ветку согласно активной конвенции (`config/conventions.json`).

**Аргументы**: `<type> <args>`
- `feature <TICKET>` — ветка `feature/<TICKET>` (например, `feature STORE-123`).
- `<type> <scope>` — `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `revert`.
- `mixed <TICKET> <type> <scope>` — комбинированный режим.
- `hotfix <TICKET>` — ветка для хотфикса.

**Примеры**
```
/branch-new feature STORE-123
/branch-new feat checkout
/branch-new mixed STORE-123 feat pricing
```

**Результат**
- Запускает `scripts/branch_new.py`, создаёт ветку через `git checkout -b` или переключается, если она уже существует.
- Выводит имя активной ветки.

**Типичные ошибки**
- «Use: feature <TICKET>» — проверьте формат тикета (`ABC-123`).
- «Unknown branch type» — допустимые типы перечислены выше.
- Ошибка git о незакоммиченных изменениях — закоммитьте или заstashите текущие правки.

**Советы**
- Используйте перед `/commit`, чтобы имя ветки совпадало с выбранной конвенцией.
