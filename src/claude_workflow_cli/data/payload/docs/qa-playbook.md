# QA playbook

Документ описывает, как готовить входные данные, запускать QA-агента и
интерпретировать результаты гейта (`gate-qa.sh`). Используйте его вместе с
`docs/agents-playbook.md` и шаблоном `docs/tasklist/<slug>.md`.

## Входные данные

- **Активная фича** — `docs/.active_feature` указывает slug. В PRD и плане должны
  быть закрыты блокирующие вопросы.
- **Чеклисты** — раздел `QA` в `docs/tasklist/<slug>.md` заполнен, новые сценарии добавлены.
- **Артефакты** — релевантные логи, отчёты нагрузочного тестирования, ссылки на
  демо или тестовые окружения.
- **Diff** — локально агент анализирует рабочее дерево (`git diff HEAD` +
  незакоммиченные файлы). В CI добавьте `QA_AGENT_DIFF_BASE=origin/<base>`, чтобы
  сравнивать с веткой-основой.

## Как запускать QA-агента

### Локально

```bash
# короткий отчёт + запись JSON в reports/qa/<slug>.json
python3 scripts/qa-agent.py --gate --report "reports/qa/{slug}.json"

# dry-run (не проваливать выполнение при блокерах)
CLAUDE_QA_DRY_RUN=1 ./.claude/hooks/gate-qa.sh --payload '{"tool_input":{"file_path":"src/main/App.kt"}}'
```

### В CI

1. Настройте `actions/checkout` с `fetch-depth: 0` и сделайте `git fetch` базовой
   ветки (см. `.github/workflows/ci.yml`).
2. Перед шагом QA установите
   `QA_AGENT_DIFF_BASE=origin/${{ github.event.pull_request.base.ref }}`.
3. Запустите `./.claude/hooks/gate-qa.sh --payload '{}'`. Скрипт вызовет
   `scripts/qa-agent.py` и провалит job при блокерах.

## Severity и статус гейта

| Severity  | Значение                                   | Действие                                        |
|-----------|--------------------------------------------|-------------------------------------------------|
| `blocker` | Нельзя релизить без фикса                  | `gate-qa.sh` → exit 1 (если не `dry-run`)       |
| `critical`| Высокий риск, требует немедленного решения | exit 1                                          |
| `major`   | Существенное, но допустимое как known issue| WARN, гейт проходит                              |
| `minor`   | Минорные шероховатости                     | WARN                                            |
| `info`    | Наблюдения, идеи на будущее                | INFO                                            |

`gate-qa.sh` печатает суммарную строку и каждое замечание отдельной записью с
рекомендацией. JSON-отчёт лежит в `reports/qa/<slug>.json`, если
`allow_missing_report=false`.

## Переменные окружения

- `CLAUDE_SKIP_QA=1` — полностью пропустить гейт.
- `CLAUDE_QA_DRY_RUN=1` — не проваливать выполнение при блокерах.
- `CLAUDE_GATES_ONLY=qa` — запускать гейт только по требованию (`--only qa`).
- `CLAUDE_QA_COMMAND` — переопределить команду агента (например, если используете
  внешний runner).
- `QA_AGENT_DIFF_BASE` — diff-база (например, `origin/main`) для CI.

## Чеклист QA-подготовки

- [ ] Все шаги раздела `QA` в `docs/tasklist/<slug>.md` закрыты/перенесены.
- [ ] В PR добавлены шаги воспроизведения, метрики и снапшоты, если есть UX/визуальные изменения.
- [ ] Тестовое окружение задокументировано (URL, пользователи, токены).
- [ ] Автоматические гейты (`gate-tests`, `gate-api-contract`, `gate-db-migration`) прошли.
- [ ] Результаты `scripts/qa-agent.py` приложены к описанию PR или загружены в CI артефакты.
- [ ] В `CHANGELOG.md`/release notes отмечены найденные и устранённые дефекты.
