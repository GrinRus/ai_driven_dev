---
description: "Подготовка отчёта Researcher: сбор контекста и запуск агента."
argument-hint: "<TICKET> [--paths path1,path2] [--no-agent]"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(*)
---
1) Убедись, что активная фича совпадает с `ticket`: файл `docs/.active_ticket` должен содержать `$1`. Если нет — запусти `/idea-new $1` и синхронизируй slug-хинт при необходимости.
2) Собери контекст автоматически:
!bash -lc 'claude-workflow research --ticket "$1" --auto'
   - `--paths "pathA:pathB"` и `--keywords "foo,bar"` расширяют охват, `--note "ручные наблюдения"`/`--note @memo.md` добавят свободный ввод в контекст;
   - `--dry-run` сохранит только JSON, `--targets-only` пригодится, когда нужно обновить пути без сканирования.
3) Если отчёт ещё не создан, распакуй шаблон `docs/templates/research-summary.md` в `docs/research/$1.md` и заполни блоки:
   - `## Паттерны/анти-паттерны` — перечисли, что можно переиспользовать и чего стоит избегать;
   - `## Отсутствие паттернов` — отметь «Контекст пуст, требуется baseline», если CLI сообщил `0 matches`, добавь рекомендации;
   - `## Дополнительные заметки` — перенеси свободный ввод (`--note`) и ручные наблюдения.
4) Запусти агента **researcher** через палитру (`Claude: Run agent → researcher`), передай ему JSON из `reports/research/$1-context.json` и обнови отчёт: статус `pending` допустим только в новых проектах; по завершении согласования проставь `Status: reviewed`.
5) Зафиксируй решения:
   - ссылка на `docs/research/$1.md` обязательна в PRD (`## Диалог analyst`) и `docs/tasklist/$1.md`;
   - action items перенеси в `docs/plan/$1.md`/`docs/tasklist/$1.md`;
   - если статус остаётся `pending`, обязательно пропиши baseline и TODO для перехода к reviewed.
