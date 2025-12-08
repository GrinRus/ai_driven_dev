---
description: "Подготовка отчёта Researcher: сбор контекста и запуск агента."
argument-hint: "<TICKET> [--paths path1,path2] [--keywords kw1,kw2] [--note text]"
lang: ru
prompt_version: 1.1.0
source_version: 1.1.0
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - "Bash(claude-workflow research:*)"
  - "Bash(python3 tools/set_active_feature.py:*)"
  - "Bash(claude-workflow preset:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/researcher` собирает кодовый контекст для новой фичи: запускает автоматический анализ, обновляет `docs/research/<ticket>.md` по шаблону и связывает результаты с PRD/plan/tasklist. Это обязательный шаг перед планированием и реализацией.

## Входные артефакты
- `docs/.active_ticket` и `.active_feature` — активный тикет/slug.
- `docs/prd/<ticket>.prd.md` — для понимания целей.
- `docs/templates/research-summary.md` — шаблон отчёта (если файл ещё не создан).
- `reports/research/<ticket>-context.json` — формируется `claude-workflow research`.

## Когда запускать
- После `/idea-new`, до `/plan-new`.
- Повторно — при появлении новых модулей/рисков или после значительного рефакторинга.

## Автоматические хуки и переменные
- `claude-workflow research --ticket <ticket> --auto --deep-code --call-graph [--reuse-only] [--paths ... --keywords ... --langs ... --graph-langs ... --graph-filter <regex> --graph-limit <N> --note ...]` сканирует кодовую базу, собирает `code_index`/`reuse_candidates` и `call_graph`/`import_graph` (только Java/Kotlin, tree-sitter при наличии) и обновляет JSON.
- По умолчанию call graph фильтруется по `<ticket>|<keywords>` и ограничивается N=300 рёбер; полный граф сохраняется отдельно в `reports/research/<ticket>-call-graph-full.json`, а в context попадает focus-версия.
- Опции: `--dry-run` (только JSON), `--targets-only` (обновить пути без сканирования), `--reuse-only` (показать только reuse-кандидаты), `--langs` (фильтр языков для deep-code), `--graph-langs` (kt/kts/java), `--graph-filter`, `--graph-limit`, `--no-agent` (пропустить запуск саб-агента).
- После формирования отчёта подготовь handoff для исполнителя: перечисли доработки/reuse/риски и запусти `claude-workflow tasks-derive --source research --append --ticket <ticket>` (новые `- [ ]` ссылаются на `reports/research/<ticket>-context.json`).

## Что редактируется
- `docs/research/<ticket>.md` — отчёт (разделы «Паттерны/анти-паттерны», «Отсутствие паттернов», «Дополнительные заметки» + статус `pending`/`reviewed`).
- PRD и tasklist получают ссылки на отчёт (если отсутствуют).

## Пошаговый план
1. Убедись, что активный ticket = `$1`. Если нет — запусти `/idea-new $1` или `python3 tools/set_active_feature.py $1`.
2. Выполни `claude-workflow research --ticket "$1" --auto --deep-code --call-graph [доп. опции]` (при необходимости `--reuse-only`, `--langs`, `--graph-langs`).
3. Если CLI сообщает `0 matches`, создай `docs/research/$1.md` из шаблона и добавь baseline «Контекст пуст, требуется baseline».
4. Запусти саб-агента **researcher** (через палитру) с JSON из `reports/research/$1-context.json`, используй `call_graph`/`import_graph` (Java/Kotlin) и при необходимости расширь связи в Claude Code, обнови отчёт и перенеси рекомендации.
5. Зафиксируй статус: `reviewed`, если команда согласовала действия; `pending`, если нужны уточнения (пропиши TODO).
6. Убедись, что ссылки на отчёт добавлены в PRD (`## Диалог analyst`) и tasklist; добавь handoff-пункты (`- [ ] Research: ... (source: reports/research/$1-context.json)`) или выполни `claude-workflow tasks-derive --source research --append --ticket "$1"`.

## Fail-fast и вопросы
- Нет активного тикета или PRD — остановись и попроси пользователя завершить `/idea-new`.
- Пользователь не указал каталоги → попроси `--paths`/`--keywords` для более точного поиска.
- Если отчёт остаётся `pending`, перечисли действия для перехода к `reviewed`.

## Ожидаемый вывод
- Обновлённый `docs/research/<ticket>.md` (статус `pending|reviewed`).
- `reports/research/<ticket>-context.json` актуализирован.
- PRD/tasklist содержат ссылку на отчёт.

## Примеры CLI
- `/researcher ABC-123 --paths src/app:src/shared --keywords "payment,checkout" --deep-code --langs py,kt`
- `!bash -lc 'claude-workflow research --ticket "ABC-123" --auto --deep-code --note "reuse payment gateway" --reuse-only'`
