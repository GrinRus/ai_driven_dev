# План разделения (на основе аудитов)

## Входные документы
- `doc/dev/distro-audit.md`
- `doc/dev/root-audit.md`

## Шаги
1. **Утвердить границу runtime vs repo-only.**
   - Зафиксировать решения по спорным пунктам: `scripts/sync-payload.sh`, `scripts/lint-prompts.py`, `scripts/prompt-version`, `tools/check_payload_sync.py`, `tools/prompt_diff.py`, `tools/payload_audit.py` → repo-only.
   - Итог: список путей, которые обязаны попадать в payload, и список repo-only.
2. **Ввести allowlist/denylist для payload.**
   - Добавить явный список разрешенных директорий/файлов.
   - Подключить автоматическую проверку (скрипт/CLI-команда) в CI и релизный чеклист.
3. **Переместить repo-only инструменты.**
   - Вынести repo-only скрипты из `aidd/` в `scripts/`/`tools/`.
   - Обновить документацию и ссылки, поправить manifest/тесты.
4. **Упорядочить корень репозитория.**
   - Сгруппировать dev-only материалы (design/backlog/tests) и обновить README/CONTRIBUTING.
   - Добавить раздел "Состав репозитория" с явным разделением.
5. **Закрепить аудит в процессах.**
   - Использовать `python3 tools/payload_audit.py` как обязательную проверку перед тегом.
   - Обновить release checklist, чтобы аудит был обязательным перед релизом.
