# Prompt Playbook

Документ описывает единые требования к промптам агентов и слэш-команд Claude Code. Следуя этим правилам, вы получите предсказуемое поведение агентов, детерминированные гейты и повторяемые ответы на вопросы «что должен сделать агент?».

## 1. Назначение
- Зафиксировать обязательные блоки и тональность промптов.
- Синхронизировать ожидания по входам/выходам между агентами и командными файлами.
- Минимизировать дублирование инструкций (например, правила `Checkbox updated`) и держать их в одном месте.
- Задать единый словарь терминов (ticket, slug, plan, PRD, tasklist) и порядок ссылок на артефакты.
- Обеспечить **agent-first** подход: агент по умолчанию использует данные из репозитория (backlog, reports, tests) и запускает разрешённые команды; вопросы пользователю разрешены только когда в артефактах нет ответа и это явно задокументировано.
- Базовые правила — `aidd/AGENTS.md`, порядок стадий — `aidd/docs/sdlc-flow.md`, статусы — `aidd/docs/status-machine.md`.

### Performance KPIs (минимум)
- Stop на 1 checkbox (за итерацию).
- Запуски `${CLAUDE_PLUGIN_ROOT}/hooks/format-and-test.sh` на 1 checkbox.
- Частота чтения `aidd/reports/**` (pack‑first vs full JSON).
- Средний размер stdout логов (summary vs full).

## 2. Структура промпта

### 2.1 YAML фронт-маттер
Каждый файл `agents/*.md` и `commands/*.md` начинается с блока:

```yaml
---
name: <agent-name>          # для команд поле `name` опционально, но требуется `description`
description: ...            # короткое назначение (≤120 символов)
lang: ru                    # текущая локаль
prompt_version: 1.0.0       # major.minor.patch
source_version: 1.0.0       # для RU-файла совпадает с prompt_version
tools: Read, Write, ...     # только разрешённые инструменты
model: inherit | opus       # при необходимости фиксируйте модель
permissionMode: default     # для агентов (acceptEdits/bypassPermissions/plan/ignore/default)
---
```

Требования:
- Поля `lang`, `prompt_version`, `description`, `source_version` обязательны. `source_version` совпадает с `prompt_version`.
- `prompt_version` повышается при любых правках текста (см. раздел 7).
- Список инструментов перечисляйте через запятую; wildcard `Bash(*)` запрещён, только конкретные команды. Если агенту доступны CLI-команды (`rg`, `pytest`, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh`), перечислите их точно, чтобы было понятно, чем он располагает.
- Для поиска используйте один способ: `rg` через `Bash(rg:*)` (Grep не добавляйте).
- Для команд обязательно добавляйте `argument-hint`, используйте позиционные `$1/$2` и `$ARGUMENTS` в теле; свободный ввод после тикета должен быть предусмотрен и описан. Для агентов поле `name` обязательно.

### 2.2 Обязательные разделы
После фронт-маттера соблюдайте блоки в указанном порядке:
1. **Контекст** — 1–3 абзаца с ролью, основными входами и ссылками на артефакты (`@aidd/docs/...`). Добавьте MUST READ FIRST: `aidd/AGENTS.md`, `aidd/docs/sdlc-flow.md`, `aidd/docs/status-machine.md`. В этом блоке явно укажите философию agent-first: какие данные агент обязан собрать самостоятельно и какие действия автоматизированы.
2. **Входные артефакты** — маркированный список (`- PRD: aidd/docs/prd/<ticket>.prd.md`). Указывайте обязательность и fallback (например, «если отчёт research отсутствует → попроси запустить команду»).
3. **Автоматизация** — что делает CLA `gate-*`, какие переменные окружения поддерживаются, как реагировать на автозапуск `format-and-test`. Здесь же перечислите разрешённые команды (например, `<test-runner>`, `rg pattern`, `${CLAUDE_PLUGIN_ROOT}/tools/progress.sh`) и ожидаемый формат фиксации их вывода.
4. **Пошаговый план** — пронумерованный список действий агента/команды. Для команд допускается блок «Когда запускать / Что модифицируем / Ожидаемый вывод».
5. **Fail-fast & вопросы** — что считать блокером, как задавать вопросы пользователю (формат, обязательные ответы). Подчеркните, что вопросы задаются только после того, как агент перечислил проверенные артефакты/команды.
6. **Формат ответа** — чёткие требования к финальному сообщению (статус, блоки, `Checkbox updated`).

Запрещено использовать свободный текст вне этих блоков: если нужна справка, добавьте ссылку на документ (`см. dev/doc/agents-playbook.md`).

### 2.3 Agent-first обязательства
- Любой агент должен описывать, **какие данные он собирает автоматически**: ссылки на файлы, пути поиска (`rg <ticket> aidd/docs/**`), используемые отчёты (`aidd/reports/research/*.json`), автозапуски (`${CLAUDE_PLUGIN_ROOT}/tools/progress.sh ...`).
- Контекст читается anchors‑first: stage‑anchor → `AIDD:*` секции → full docs; предпочтение snippet‑first (`rg` → `sed`); pack‑first если рядом есть `*.pack.yaml`.
- Разрешённый Q&A с пользователем всегда идёт в формате «перечислены изученные артефакты → сформулирован недостающий ответ → приложен требуемый формат ответа».
- Если агент не имеет прав на определённые действия (например, запуск `rg` или запись в `aidd/docs/`), это должно быть указано в контексте и дублироваться в списке инструментов.

## 3. Правила `Checkbox updated`
- Всегда начинайте блок статуса строкой `Checkbox updated: <список>` или `Checkbox updated: none`.
- Формат списка: идентификатор чекбокса (`1.1 – Аналитика`) или ссылку на файл (`aidd/docs/tasklist/ABC-123.md: QA #3`).
- Команды/агенты, которые не обновляют tasklist, должны явно указывать `Checkbox updated: not-applicable`.
- Далее добавляйте строки: `Status: ...`, `Artifacts updated: ...`, `Next actions: ...`.
- Любые дополнения (например, краткий отчёт) следуют после этих строк.

## 4. Fail-fast и эскалация
- Если обязательный вход отсутствует → немедленно завершайте ответ со статусом `BLOCKED` и перечисляйте, какую команду запустить (`/feature-dev-aidd:idea-new`, `${CLAUDE_PLUGIN_ROOT}/tools/research.sh ...`).
- При сомнениях по архитектуре или миграциям формируйте список вопросов в конце ответа и не продолжайте реализацию.
- Для слэш-команд описывайте, как проверять готовность (например, `!bash -lc '${CLAUDE_PLUGIN_ROOT}/tools/progress.sh ...'`).
- Формат вопросов обязателен:
  ```
  Вопрос N (Blocker|Clarification): ...
  Зачем: ...
  Варианты: A) ... B) ...
  Default: ...
  ```

## 5. Матрица «роль → артефакты/хуки»

| Роль/команда | Обязательные артефакты | Автохуки/гейты | Вывод | Ссылки |
| --- | --- | --- | --- | --- |
| `analyst` / `/feature-dev-aidd:idea-new` | `aidd/docs/prd/<ticket>.prd.md` (включая `## AIDD:RESEARCH_HINTS`) | `gate-workflow` | PRD READY/BLOCKED, список вопросов | `aidd/docs/prd/template.md`, `dev/doc/agents-playbook.md` |
| `planner` / `/feature-dev-aidd:plan-new` | PRD READY, `research-check`, `aidd/docs/plan/<ticket>.md` | `gate-workflow` | План + протокол validator | `aidd/docs/plan/template.md` |
| `plan-reviewer` / `/feature-dev-aidd:review-spec` | План, PRD, research | `gate-workflow` | `## Plan Review` | `aidd/docs/plan/template.md` |
| `prd-reviewer` / `/feature-dev-aidd:review-spec` | PRD, план, research | `gate-workflow`, `gate-prd-review` | `## PRD Review` + отчёт | `aidd/docs/prd/template.md` |

> `/feature-dev-aidd:review-spec` — единая команда для review-plan и review-prd.
| `implementer` / `/feature-dev-aidd:implement` | План, tasklist, reports | `gate-tests` | Код + обновлённый tasklist | `aidd/docs/tasklist/template.md` |
| `reviewer` / `/feature-dev-aidd:review` | Diff, план, tasklist | `gate-tests`, `gate-qa` | Замечания + tasklist | `dev/doc/agents-playbook.md` |
| `qa` | Tasklist, PRD AIDD:ACCEPTANCE, логи гейтов | `gate-qa`, `${CLAUDE_PLUGIN_ROOT}/hooks/gate-qa.sh` | QA отчёт | `dev/doc/qa-playbook.md` |

Расширяйте матрицу по мере добавления агентов. Таблица используется линтером для проверки ссылок.

## 6. Автоматизация и ссылки
- Ссылайтесь на переменные окружения из `.claude/settings.json` (например, `SKIP_AUTO_TESTS`, `TEST_SCOPE`).
- Для команд, которые вызывают дополнительные скрипты, описывайте формат `!bash -lc '...'` и ожидаемые побочные эффекты.
- Если агент должен запускаться из палитры (например, `qa`), напишите явное указание «Запусти через Claude: Run agent → qa».
- Hook events: `hooks/hooks.json` задаёт PreCompact/SessionStart/PreToolUse/UserPromptSubmit/Stop/SubagentStop; команды вызывают хук скриптами вида `${CLAUDE_PLUGIN_ROOT}/hooks/<name>.sh`.

## 7. Процесс изменений и версионирование
> Repo-only: `dev/repo_tools/prompt-version`, `dev/repo_tools/lint-prompts.py` доступны только в репозитории.
> `<workflow-root>` — каталог, где лежат `agents/`, `commands/` (как правило, корень репозитория).

- Любая правка текста или структуры требует увеличения `prompt_version` (major — изменение секций/формата, minor — содержание, patch — уточнение формулировок/примеры).
- Используйте `dev/repo_tools/prompt-version bump --root <workflow-root> --prompts <name> --kind agent|command --lang ru --part <...>` для контроля версий.
- После обновления промпта обязательно опишите изменения в `dev/doc/release-notes.md` и при необходимости добавьте запись в `CHANGELOG.md`.

## 8. Минимальный чеклист перед публикацией
1. Проверить фронт-маттер (`lang`, `prompt_version`, инструменты).
2. Убедиться, что все обязательные блоки присутствуют и оформлены.
3. Добавить ссылку на соответствующую таблицу в разделе 5 (если роль новая).
4. Запустить `dev/repo_tools/lint-prompts.py --root <workflow-root>` и убедиться, что проверки пройдены.
5. Обновить внутренний wave backlog (dev-only, `dev/doc/backlog.md`) и сопутствующие документы (README, `dev/doc/agents-playbook.md`) при необходимости.

Следование этому плейбуку гарантирует, что агенты и команды работают консистентно в любых проектах, подключивших workflow.

## 9. Шаблоны и автоматизация
- Используйте `dev/doc/templates/prompts/prompt-agent.md` и `dev/doc/templates/prompts/prompt-command.md` как базу: они уже содержат требуемые секции и подсказки.
- Для быстрого старта скопируйте шаблон в `agents/<name>.md` или `commands/<name>.md` и заполните фронт-маттер вручную.
- Проверяйте промпты: `python3 dev/repo_tools/lint-prompts.py --root <workflow-root>`, `dev/repo_tools/prompt-version bump --root <workflow-root> --prompts <name> --kind agent|command --lang ru --part patch --dry-run`.
- После генерации обязательно заполните все блоки и обновите `prompt_version`/`source_version`.
