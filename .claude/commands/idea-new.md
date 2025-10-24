---
description: "Инициация фичи: сбор идеи → уточнения → PRD"
argument-hint: "<TICKET> [slug-hint]"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(*)
---
1) Установи активную фичу: запусти `python3 tools/set_active_feature.py "$1"` (если нужно передать slug-хинт, добавь `--slug-note "$2"`). Скрипт обновит `docs/.active_ticket`, синхронизирует `.active_feature` и пересоберёт цели Researcher.
2) Используя @docs/prd.template.md, @conventions.md и @workflow.md, создай/обнови `docs/prd/$1.prd.md`.
3) Перед запуском саб-агента **analyst** объясни пользователю, что ответы должны приходить в формате `Ответ N: …`. Агент обязан начать с `Вопрос 1`, дождаться `Ответ 1` и продолжать цикл вопросов/ответов, пока все блокеры не закрыты. Если ответы отсутствуют, не переходи к генерации PRD и повторно запроси информацию.
4) После обновления PRD запусти проверку:
!bash -lc 'claude-workflow analyst-check --ticket "$1"'
   - Если команда сообщает о пропущенных вопросах или статусе `Status: BLOCKED`, вернись к диалогу, запроси недостающие ответы и повтори проверку.
5) Для быстрого старта воспользуйся пресетом `feature-prd` (`bash init-claude-workflow.sh --preset feature-prd --ticket "$1"`), чтобы подхватить готовый шаблон и цели из backlog/usage-demo.
