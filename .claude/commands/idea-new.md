---
description: "Инициация фичи: сбор идеи → уточнения → PRD"
argument-hint: "<TICKET> [slug-hint]"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(*)
---
1) Установи активную фичу: запусти `python3 tools/set_active_feature.py "$1"` (если нужно передать slug-хинт, добавь `--slug-note "$2"`). Скрипт обновит `docs/.active_ticket`, синхронизирует `.active_feature` и пересоберёт цели Researcher.
2) Сразу после фиксации тикета собери контекст:
!bash -lc 'claude-workflow research --ticket "$1" --auto'
   - добавь `--paths "pathA:pathB"` и/или `--keywords "foo,bar"` если нужно расширить охват; свободные текстовые заметки передавай через `--note "что нашли"` или `--note @file.md`;
   - если CLI сообщает `0 matches`, создай `docs/research/$1.md` на базе шаблона, оставь `Status: pending` и впиши маркер «Контекст пуст, требуется baseline» в секции `## Отсутствие паттернов` и `## Следующие шаги`.
3) Используя @docs/prd.template.md, @docs/research/$1.md и @workflow.md, создай/обнови `docs/prd/$1.prd.md`: в разделе `## Диалог analyst` ссылку на отчёт Researcher указывай явным URL/путём.
4) Перед запуском саб-агента **analyst** объясни пользователю, что ответы должны приходить в формате `Ответ N: …`. Агент обязан начать с `Вопрос 1`, дождаться `Ответ 1` и продолжать цикл вопросов/ответов, пока все блокеры не закрыты. Если ответы отсутствуют, не переходи к генерации PRD и повторно запроси информацию; опирайся на вывод Researcher при формулировании уточнений.
5) После обновления PRD запусти проверку:
!bash -lc 'claude-workflow analyst-check --ticket "$1"'
   - Если команда сообщает о пропущенных вопросах или статусе `Status: BLOCKED`, вернись к диалогу, запроси недостающие ответы и повтори проверку.
6) Для быстрого старта воспользуйся пресетом `feature-prd` (`bash init-claude-workflow.sh --preset feature-prd --ticket "$1"`), чтобы подхватить готовый шаблон и актуальные цели Researcher из backlog/usage-demo.
