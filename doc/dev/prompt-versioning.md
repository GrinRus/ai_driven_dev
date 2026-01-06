# Prompt Versioning

Этот документ описывает правила версионирования RU‑промптов и поддерживающих инструментов.

## 1. Цели
- Единый semver для `prompt_version` в промптах.
- `source_version` всегда совпадает с `prompt_version`.
- Прозрачный контроль изменений через repo-only скрипты.

## 2. Структура директорий
- Промпты находятся в `aidd/agents/*.md` и `aidd/commands/*.md`.
- `<workflow-root>` — каталог, где лежат `agents/` и `commands/` (например, `./aidd` или `src/claude_workflow_cli/data/payload/aidd`).

## 3. Поля версий
- `prompt_version`: semver (`MAJOR.MINOR.PATCH`).
  - `major` — изменена структура секций или контракт.
  - `minor` — добавлены/переформулированы требования без изменения контракта.
  - `patch` — правки формулировок и примеров.
- `source_version`: для RU-файла всегда равен `prompt_version`.

## 4. Рабочий процесс
> Repo-only: `scripts/prompt-version`, `scripts/lint-prompts.py`, `tools/check_payload_sync.py` живут в корне репозитория и не входят в установленный payload.

1. Обновите текст промпта.
2. Поднимите версии: `scripts/prompt-version bump --root <workflow-root> --prompts <name> --kind agent|command --lang ru --part <major|minor|patch>`.
3. Запустите lint: `python3 scripts/lint-prompts.py --root <workflow-root>`.
4. Зафиксируйте изменения в `doc/dev/release-notes.md` и при необходимости в `CHANGELOG.md`.

## 5. Инструменты
- `scripts/lint-prompts.py` — валидирует фронт-маттер и обязательные секции.
- `scripts/prompt-version bump --root <workflow-root> --prompts analyst --kind agent --lang ru --part minor` — повышает версии. Используйте `--dry-run` для проверки.

## 6. Release checklist
- `python3 scripts/prompt-version bump --root <workflow-root> --prompts <list> --kind agent|command --lang ru --part patch --dry-run`
- `python3 scripts/lint-prompts.py --root <workflow-root>`
- Pytest-сьюты `tests/test_prompt_lint.py`, `tests/test_prompt_versioning.py`
- `python3 tools/check_payload_sync.py` (если менялись runtime-снапшоты)
