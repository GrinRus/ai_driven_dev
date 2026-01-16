# Prompt Versioning

Этот документ описывает правила версионирования RU‑промптов и поддерживающих инструментов.

## 1. Цели
- Единый semver для `prompt_version` в промптах.
- `source_version` всегда совпадает с `prompt_version`.
- Прозрачный контроль изменений через repo-only скрипты.

## 2. Структура директорий
- Промпты находятся в `agents/*.md` и `commands/*.md`.
- `<workflow-root>` — каталог, где лежат `agents/` и `commands/` (как правило, корень репозитория).

## 3. Поля версий
- `prompt_version`: semver (`MAJOR.MINOR.PATCH`).
  - `major` — изменена структура секций или контракт.
  - `minor` — добавлены/переформулированы требования без изменения контракта.
  - `patch` — правки формулировок и примеров.
- `source_version`: для RU-файла всегда равен `prompt_version`.

## 4. Рабочий процесс
> Repo-only: `dev/repo_tools/prompt-version`, `dev/repo_tools/lint-prompts.py` живут в корне репозитория.

1. Обновите текст промпта.
2. Поднимите версии: `dev/repo_tools/prompt-version bump --root <workflow-root> --prompts <name> --kind agent|command --lang ru --part <major|minor|patch>`.
3. Запустите lint: `python3 dev/repo_tools/lint-prompts.py --root <workflow-root>`.
4. Зафиксируйте изменения в `dev/doc/release-notes.md` и при необходимости в `CHANGELOG.md`.

## 5. Инструменты
- `dev/repo_tools/lint-prompts.py` — валидирует фронт-маттер и обязательные секции.
- `dev/repo_tools/prompt-version bump --root <workflow-root> --prompts analyst --kind agent --lang ru --part minor` — повышает версии. Используйте `--dry-run` для проверки.

## 6. Release checklist
- `python3 dev/repo_tools/prompt-version bump --root <workflow-root> --prompts <list> --kind agent|command --lang ru --part patch --dry-run`
- `python3 dev/repo_tools/lint-prompts.py --root <workflow-root>`
- Pytest-сьюты `dev/tests/test_prompt_lint.py`, `dev/tests/test_prompt_versioning.py`
- Обновите release notes и проверьте prompt-тесты при изменении промптов.
