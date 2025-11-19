---
description: "Инициация фичи: сбор идеи → уточнения → PRD"
argument-hint: "<TICKET> [slug-hint]"
lang: ru
prompt_version: 1.0.0
source_version: 1.0.0
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(python3 tools/set_active_feature.py:*),Bash(claude-workflow research:*),Bash(claude-workflow analyst-check:*)
model: inherit
---

## Контекст
Команда `/idea-new` заводит новую фичу: фиксирует активный ticket, подготавливает шаблон PRD и запускает аналитика. Команда открывает Wave 32 цикл («идея → research → PRD») и задаёт основу для всех следующих агентов.

## Входные артефакты
- `doc/backlog.md`, заметки пользователя — исходное описание идеи.
- `docs/prd.template.md` — шаблон PRD для автосборки.
- `docs/research/<ticket>.md` — создаётся/обновляется в рамках шага (если отсутствует, используется шаблон `docs/templates/research-summary.md`).

## Когда запускать
- В самом начале работы над фичей, до любого планирования/кодовых правок.
- Повторный запуск допустим только если нужно пересоздать активный ticket (используй флаг `--force` и убедись, что не перетираешь заполненный PRD).

## Автоматические хуки и переменные
- `python3 tools/set_active_feature.py` синхронизирует `docs/.active_ticket`, `.active_feature` и scaffold'ит PRD.
- `claude-workflow research --auto` собирает кодовый контекст и создаёт `reports/research/<ticket>-context.json`.
- `claude-workflow analyst-check` валидирует, что блок `## Диалог analyst` заполнен и статус PRD не `draft`.

## Что редактируется
- `docs/.active_ticket`, `docs/.active_feature` — текущее состояние фичи.
- `docs/prd/<ticket>.prd.md` — основной документ; после запуска всегда существует хотя бы с `Status: draft`.
- `docs/research/<ticket>.md` — отчёт Researcher (при отсутствии разворачивается из шаблона).
- Дополнительные заметки/файлы, которые пользователь указал в аргументах (`--note`).

## Пошаговый план
1. Запусти `python3 tools/set_active_feature.py "$1" [--slug-note "$2"]` (при необходимости добавь `--skip-prd-scaffold`, но по умолчанию scaffold обязателен).
2. Сразу после фиксации тикета выполни `claude-workflow research --ticket "$1" --auto` (при необходимости дополни `--paths`, `--keywords`, `--note`).
3. Если CLI сообщает `0 matches`, создавай `docs/research/$1.md` из шаблона и добавь baseline «Контекст пуст, требуется baseline» в разделы `## Отсутствие паттернов` / `## Дополнительные заметки`.
4. Запусти саб-агента **analyst** (палитра `/analyst` или выбор агента вручную) и веди диалог согласно инструкциям, сразу напоминая пользователю отвечать в формате `Ответ N: …`.
5. Допиши `docs/prd/$1.prd.md` по шаблону: заполни раздел `## Диалог analyst`, ссылку на research, цели, сценарии, риски; переведи статус из `draft` в READY только после полного диалога.
6. После завершения диалога запусти `claude-workflow analyst-check --ticket "$1"`. Если есть замечания — вернись к PRD и дополни.
7. По желанию используй пресет `feature-prd` (`bash init-claude-workflow.sh --preset feature-prd --ticket "$1"`) для быстрого наполнения целей.

## Fail-fast и вопросы
- Если ticket не указан — остановись и попроси пользователя назвать ID (и при необходимости slug-hint).
- Не перезаписывай заполненный PRD без явного подтверждения: предупреди, что потребуется `--force`.
- При отсутствии контекста (нет путей/ключевых слов) попроси пользователя указать каталоги через `--paths` или заметки через `--note`.

## Ожидаемый вывод
- Активный ticket и slug зафиксированы в `docs/.active_ticket`, `.active_feature`.
- `docs/prd/<ticket>.prd.md` создан и заполнен (как минимум черновик) + статус READY/BLOCKED отражает состояние диалога.
- `docs/research/<ticket>.md` создан/обновлён, а `reports/research/<ticket>-context.json` содержит цели.
- Пользователь понимает, какие вопросы ещё остались (`Status: BLOCKED` + список).

## Примеры CLI
- `/idea-new ABC-123 checkout-demo`
- `/idea-new ABC-123 --paths src/app:src/shared --keywords "payment,checkout" --slug-note checkout-demo`
- `!bash -lc 'claude-workflow research --ticket "ABC-123" --auto --note "reuse payment gateway"'`
