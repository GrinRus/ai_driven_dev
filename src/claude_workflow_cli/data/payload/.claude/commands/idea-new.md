---
description: "Инициация фичи: сбор идеи → уточнения → PRD"
argument-hint: "<TICKET> [slug-hint]"
lang: ru
prompt_version: 1.1.0
source_version: 1.1.0
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(python3 tools/set_active_feature.py:*),Bash(claude-workflow research:*),Bash(claude-workflow analyst-check:*)
model: inherit
---

## Контекст
Команда `/idea-new` заводит новую фичу: фиксирует активный ticket, подготавливает шаблон PRD и запускает аналитика. Команда открывает цикл «идея → research → PRD» и задаёт основу для следующих агентов, придерживаясь agent-first принципа: аналитик и исследователь используют slug-hint пользователя (`docs/.active_feature`), `docs/research/*.md`, `reports/research/*.json` и запускают нужные CLI автоматически, а к пользователю обращаются только при недостающих фактах.

## Входные артефакты
- Slug-hint пользователя (аргумент `[slug-hint]` у `/idea-new`) и любые найденные ссылки на тикет (`rg <ticket> docs/**`) — исходное описание.
- `docs/prd.template.md` — шаблон PRD для автосборки.
- `docs/research/<ticket>.md`, `reports/research/<ticket>-context.json`, `reports/research/<ticket>-targets.json` — создаются/обновляются автоматически (если отчёта нет, разворачивается `docs/templates/research-summary.md` с baseline).
- Пользовательский `slug-hint` из команды `/idea-new <ticket> [slug-hint]` — первичный текст запроса; зафиксируй его в PRD (обзор, контекст) и, при необходимости, импортируй в backlog/заметки.

## Когда запускать
- В самом начале работы над фичей, до любого планирования/кодовых правок.
- Повторный запуск допустим только если нужно пересоздать активный ticket (используй флаг `--force` и убедись, что не перетираешь заполненный PRD).

## Автоматические хуки и переменные
- `python3 tools/set_active_feature.py` синхронизирует `docs/.active_ticket`, `.active_feature` и scaffold'ит PRD (может читать slug/alias из аргументов).
- `claude-workflow research --ticket <ticket> --auto` собирает кодовый контекст и обновляет `reports/research/<ticket>-context.json`/`-targets.json`; параметры `--paths/--keywords/--note` указываем только при реальной необходимости уточнить область поиска.
- `claude-workflow analyst-check --ticket <ticket>` валидирует, что блок `## Диалог analyst` заполнен и статус PRD не `draft`.

## Что редактируется
- `docs/.active_ticket`, `docs/.active_feature` — текущее состояние фичи.
- `docs/prd/<ticket>.prd.md` — основной документ; после запуска всегда существует хотя бы с `Status: draft`.
- `docs/research/<ticket>.md` — отчёт Researcher (при отсутствии разворачивается из шаблона).
- Автогенерируемые отчёты в `reports/research/*.json` (при необходимости CLI обновляет их повторно).
- Дополнительные заметки/файлы, которые пользователь указал в аргументах (`--note`).

## Пошаговый план
1. Запусти `python3 tools/set_active_feature.py "$1" [--slug-note "$2"]` — команда обновит `docs/.active_ticket`, `.active_feature` (сохраняет slug-hint как сырой запрос пользователя) и создаст PRD (`Status: draft`). Аргумент `--force` используем только если подтверждено перезаписывание существующей фичи.
2. Сразу после фиксации тикета выполни `claude-workflow research --ticket "$1" --auto` — это соберёт пути/ключевые слова/experts и создаст `reports/research/<ticket>-context.json`. Дополнительные `--paths`/`--keywords` указываем только при явном ограничении области поиска; по умолчанию агент сам сканирует репозиторий.
3. Если CLI сообщает `0 matches`, развёрни `docs/templates/research-summary.md` в `docs/research/$1.md`, добавь baseline «Контекст пуст, требуется baseline» и перечисли команды/пути, которые ничего не нашли.
4. Запусти саб-агента **analyst** через `/analyst` (или палитру) и попроси его сначала собрать данные из slug-hint (`docs/.active_feature`), `docs/research/<ticket>.md`, `reports/research/*.json`. Вопросы пользователю разрешены только для пробелов; ответ должен приходить в формате `Ответ N: …`.
5. После автосбора аналитик заполняет `docs/prd/$1.prd.md` (включая `## Диалог analyst`, цели, сценарии, риски) и меняет статус на READY, когда репозитория достаточно либо получены ответы.
6. Запусти `claude-workflow analyst-check --ticket "$1"` — убедись, что структура вопросов/ответов корректна и статус не `draft`. При замечаниях вернись к PRD и дополни.
7. При необходимости воспользуйся пресетом `feature-prd` (`bash init-claude-workflow.sh --preset feature-prd --ticket "$1"`) или добавь `--note @file.md`, чтобы приложить дополнительные наблюдения в отчет research.

## Fail-fast и вопросы
- Если ticket не указан — остановись и попроси пользователя назвать ID (и при необходимости slug-hint).
- Не перезаписывай заполненный PRD без явного подтверждения: предупреди, что потребуется `--force`.
- При отсутствии ticket или slug-hint остановись и запроси корректные аргументы.
- Не перезаписывай заполненный PRD без подтверждения: предупреди про `--force`.
- Если после запуска `claude-workflow research --auto` нет данных, задокументируй baseline и попроси пользователя уточнить каталоги/фичи только после перечисления того, что уже проверено.

## Ожидаемый вывод
- Активный ticket и slug зафиксированы в `docs/.active_ticket`, `.active_feature`.
- `docs/prd/<ticket>.prd.md` создан и заполнен (как минимум черновик) + статус READY/BLOCKED отражает состояние диалога.
- `docs/research/<ticket>.md` создан/обновлён, а `reports/research/<ticket>-context.json` содержит цели.
- Пользователь понимает, какие вопросы ещё остались (`Status: BLOCKED` + список).

## Примеры CLI
- `/idea-new ABC-123 checkout-demo`
- `/idea-new ABC-123 --paths src/app:src/shared --keywords "payment,checkout" --slug-note checkout-demo`
- `!bash -lc 'claude-workflow research --ticket "ABC-123" --auto --note "reuse payment gateway"'`
