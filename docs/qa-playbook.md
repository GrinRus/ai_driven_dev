# QA playbook

Документ описывает, как готовить входные данные, запускать QA-агента и
интерпретировать результаты гейта (`gate-qa.sh`). Используйте его вместе с
`docs/agents-playbook.md` и шаблоном `docs/tasklist/<ticket>.md`.

> Ticket — основной идентификатор фичи; при необходимости указывайте slug-hint (сохраняется в `docs/.active_feature`).

## Входные данные

- **Активная фича** — `docs/.active_ticket` указывает ticket. В PRD и плане должны
  быть закрыты блокирующие вопросы.
- **Чеклисты** — раздел `QA` в `docs/tasklist/<ticket>.md` заполнен, новые сценарии добавлены.
- **Артефакты** — релевантные логи, отчёты нагрузочного тестирования, ссылки на
  демо или тестовые окружения.
- **Research** — `docs/research/<ticket>.md` со статусом `Status: reviewed`, актуальный
  `reports/research/<ticket>-context.json` (не старше установленного порога), ссылка
  на отчёт проставлена в PRD и `docs/tasklist/<ticket>.md`.
- **Diff** — локально агент анализирует рабочее дерево (`git diff HEAD` +
  незакоммиченные файлы). В CI добавьте `QA_AGENT_DIFF_BASE=origin/<base>`, чтобы
  сравнивать с веткой-основой.
- **Прогресс** — в `docs/tasklist/<ticket>.md` фиксируются завершённые пункты `- [x]`, рядом указаны дата/итерация и строка `Checkbox updated: …`; предыдущий запуск `claude-workflow progress --source qa --ticket <ticket>` прошёл без ошибок.

## Как запускать QA-агента

### Локально

```bash
# короткий отчёт + запись JSON в reports/qa/<ticket>.json
python3 scripts/qa-agent.py --gate --report "reports/qa/{ticket}.json"

# dry-run (не проваливать выполнение при блокерах)
CLAUDE_QA_DRY_RUN=1 ./.claude/hooks/gate-qa.sh --payload '{"tool_input":{"file_path":"src/main/App.kt"}}'
```

Перед завершением каждой сессии QA обновите чеклист, сформируйте строку `Checkbox updated: …` и выполните `claude-workflow progress --source qa --ticket <ticket>` — гейт `gate-workflow.sh` блокирует правки без новых `- [x]`.

### В CI

1. Настройте `actions/checkout` с `fetch-depth: 0` и сделайте `git fetch` базовой
   ветки (см. `.github/workflows/ci.yml`).
2. Перед шагом QA установите
   `QA_AGENT_DIFF_BASE=origin/${{ github.event.pull_request.base.ref }}`.
3. Запустите `./.claude/hooks/gate-qa.sh --payload '{}'`. Скрипт вызовет
   `scripts/qa-agent.py` и провалит job при блокерах.

## Severity и статус гейта

| Severity | Значение | Действие |
| --- | --- | --- |
| `blocker` | Нельзя релизить без фикса | `gate-qa.sh` → exit 1 (если не `dry-run`) |
| `critical` | Высокий риск, требует немедленного решения | exit 1 |
| `major` | Существенное, но допустимое как known issue | WARN, гейт проходит |
| `minor` | Минорные шероховатости | WARN |
| `info` | Наблюдения, идеи на будущее | INFO |

`gate-qa.sh` печатает суммарную строку и каждое замечание отдельной записью с
рекомендацией. JSON-отчёт лежит в `reports/qa/<ticket>.json`, если
`allow_missing_report=false`.

## Переменные окружения

- `CLAUDE_SKIP_QA=1` — полностью пропустить гейт.
- `CLAUDE_QA_DRY_RUN=1` — не проваливать выполнение при блокерах.
- `CLAUDE_GATES_ONLY=qa` — запускать гейт только по требованию (`--only qa`).
- `CLAUDE_QA_COMMAND` — переопределить команду агента (например, если используете
  внешний runner).
- `QA_AGENT_DIFF_BASE` — diff-база (например, `origin/main`) для CI.

## Чеклист QA-подготовки

- [ ] Все шаги раздела `QA` в `docs/tasklist/<ticket>.md` закрыты/перенесены.
- [ ] В PR добавлены шаги воспроизведения, метрики и снапшоты, если есть UX/визуальные изменения.
- [ ] Тестовое окружение задокументировано (URL, пользователи, токены).
- [ ] Автоматические гейты (`gate-tests`, `gate-api-contract`, `gate-db-migration`) прошли.
- [ ] `gate-workflow` подтвердил актуальность отчёта Researcher (`Status: reviewed`, свежий контекст).
- [ ] Результаты `scripts/qa-agent.py` приложены к описанию PR или загружены в CI артефакты.
- [ ] В `CHANGELOG.md`/release notes отмечены найденные и устранённые дефекты.
- [ ] Строка `Checkbox updated: …` отражает прогресс QA, а `claude-workflow progress --source qa --ticket <ticket>` возвращает успех.
