---
description: "Инициация фичи: сбор идеи → уточнения → PRD"
argument-hint: "<TICKET> [slug-hint]"
lang: ru
prompt_version: 1.2.0
source_version: 1.2.0
allowed-tools:
  - Read
  - Edit
  - Write
  - Grep
  - Glob
  - "Bash(${CLAUDE_PLUGIN_ROOT}/tools/set_active_feature.py:*)"
  - "Bash(claude-workflow analyst:*)"
  - "Bash(claude-workflow analyst-check:*)"
  - "Bash(claude-workflow research:*)"
model: inherit
disable-model-invocation: false
---

## Контекст
Команда `/idea-new` запускает фичу: фиксирует активный ticket, готовит шаблон PRD и передаёт работу аналитику. Research — опционален и включается только если контекста мало (ручной `/researcher` или `claude-workflow research`). Базовый порядок: `/idea-new → analyst → (по необходимости) /researcher → analyst-check → plan`. Аналитик/ресерчер сначала читают slug-hint (`aidd/docs/.active_feature`), `aidd/docs/research/*.md`, `reports/research/*.json`, ищут по репо и только потом задают вопросы; research вызывается аналитиком при нехватке входных данных (можно уточнять paths/keywords).

## Входные артефакты
- Slug-hint пользователя (аргумент`[slug-hint]`у`/idea-new`) и любые найденные ссылки на тикет (`rg`&lt;ticket&gt;`aidd/docs/**`) — исходное описание.
- @aidd/docs/prd.template.md — шаблон PRD для автосборки.
- @aidd/docs/research/`&lt;ticket&gt;`.md,`reports/research/`&lt;ticket&gt;`-context.json`,`reports/research/`&lt;ticket&gt;`-targets.json`— создаются/обновляются автоматически (если отчёта нет, разворачивается`aidd/docs/templates/research-summary.md`с baseline).
- Пользовательский`slug-hint`из команды`/idea-new`&lt;ticket&gt;`[slug-hint]`— первичный текст запроса; зафиксируй его в PRD (обзор, контекст) и, при необходимости, импортируй в backlog/заметки.

## Когда запускать
- В самом начале работы над фичей, до любого планирования/кодовых правок.
- Повторный запуск допустим только если нужно пересоздать активный ticket (используй флаг`--force`и убедись, что не перетираешь заполненный PRD).

## Автоматические хуки и переменные
-`${CLAUDE_PLUGIN_ROOT}/tools/set_active_feature.py`синхронизирует`aidd/docs/.active_ticket`,`.active_feature`и scaffold'ит PRD (может читать slug/alias из аргументов).
-`claude-workflow analyst --ticket`&lt;ticket&gt;`--auto`запускает агента-аналитика, который сам перечитывает slug-hint и артефакты; при нехватке данных он инициирует дополнительный research (см. шаги ниже).
-`claude-workflow research --ticket`&lt;ticket&gt;`--auto`используется по требованию (когда аналитик видит нехватку контекста). Параметры`--paths/--keywords/--note`указываем только при явном ограничении области поиска.
-`claude-workflow analyst-check --ticket`&lt;ticket&gt;``валидирует, что блок`## Диалог analyst`заполнен и статус PRD не`draft`.

## Что редактируется
-`aidd/docs/.active_ticket`,`aidd/docs/.active_feature`— текущее состояние фичи.
-`aidd/docs/prd/`&lt;ticket&gt;`.prd.md`— основной документ; после запуска всегда существует хотя бы с`Status: draft`.
-`aidd/docs/research/`&lt;ticket&gt;`.md`— отчёт Researcher (при отсутствии разворачивается из шаблона).
- Автогенерируемые отчёты в`reports/research/*.json`(при необходимости CLI обновляет их повторно).
- Дополнительные заметки/файлы, которые пользователь указал в аргументах (`--note`).

## Пошаговый план
1. Запусти`${CLAUDE_PLUGIN_ROOT}/tools/set_active_feature.py "$1" [--slug-note "$2"]`— команда обновит`aidd/docs/.active_ticket`,`.active_feature`(сохраняет slug-hint как сырой запрос пользователя) и создаст PRD (`Status: draft`). Аргумент`--force`используем только если подтверждено перезаписывание существующей фичи.
2. Запусти саб-агента **analyst** автомодно:`claude-workflow analyst --ticket "$1" --auto`. Агент читает slug-hint (`aidd/docs/.active_feature`), при необходимости ищет упоминания тикета (`rg`), сверяет существующие артефакты и фиксирует вопросы.
3. Если аналитику не хватает контекста (нет `aidd/docs/research/$1.md` или устаревший/пустой отчёт), запусти исследование: `/researcher $1` или`claude-workflow research --ticket "$1" --auto [--paths ... --keywords ...]`. При `0 matches` разверни шаблон`aidd/docs/templates/research-summary.md`в`aidd/docs/research/$1.md`и добавь baseline «Контекст пуст, требуется baseline» + перечисление команд/путей, которые ничего не нашли.
4. После обновления отчёта вернись к аналитику (при необходимости перезапусти `claude-workflow analyst --ticket "$1" --auto`) и дополни PRD: заполненные разделы, `## Диалог analyst`, ссылки на research/отчёты; статус READY ставь только если контекст достаточен (research `Status: reviewed` или baseline-проект).
5. Запусти`claude-workflow analyst-check --ticket "$1"`— убедись, что структура вопросов/ответов корректна и статус не`draft`. При замечаниях вернись к PRD и дополни.
6. При необходимости воспользуйся пресетом`feature-prd`(`bash init-claude-workflow.sh --preset feature-prd --ticket "$1"`) или добавь`--note @file.md`, чтобы приложить дополнительные наблюдения в отчет research.

## Fail-fast и вопросы
- Если ticket не указан — остановись и попроси пользователя назвать ID (и при необходимости slug-hint).
- Не перезаписывай заполненный PRD без явного подтверждения: предупреди, что потребуется`--force`.
- При отсутствии ticket или slug-hint остановись и запроси корректные аргументы.
- Если после запуска`claude-workflow research --auto`нет данных, задокументируй baseline и попроси пользователя уточнить каталоги/фичи только после перечисления того, что уже проверено. При нехватке контекста аналитик инициирует повторный research с уточнением путей/ключевых слов или просит пользователя вызвать `/researcher`.

## Ожидаемый вывод
- Активный ticket и slug зафиксированы в`aidd/docs/.active_ticket`,`.active_feature`.
-`aidd/docs/prd/`&lt;ticket&gt;`.prd.md`создан и заполнен (как минимум черновик) + статус READY/BLOCKED отражает состояние диалога.
-`aidd/docs/research/`&lt;ticket&gt;`.md`создан/обновлён, а`reports/research/`&lt;ticket&gt;`-context.json`содержит цели.
- Пользователь понимает, какие вопросы ещё остались (`Status: BLOCKED`+ список).

## Примеры CLI
-`/idea-new ABC-123 checkout-demo`
-`/idea-new ABC-123 --paths src/app:src/shared --keywords "payment,checkout" --slug-note checkout-demo`
-`!bash -lc 'claude-workflow research --ticket "ABC-123" --auto --note "reuse payment gateway"'`
