# План разделения (marketplace-only)

## Входные документы
- `doc/dev/distro-audit.md`
- `doc/dev/root-audit.md`

## Шаги
1. **Утвердить границу runtime vs dev-only.**
   - Runtime: `commands/`, `agents/`, `hooks/`, `aidd_runtime/`, `.claude-plugin/`.
   - Шаблоны workspace: `templates/aidd/`.
   - Dev-only: `doc/dev/`, `tests/`, `repo_tools/`.
2. **Зафиксировать источник истины для шаблонов.**
   - Все изменения шаблонов делаются в `templates/aidd/`.
   - `/aidd-init` остаётся идемпотентным и не перезаписывает пользовательские правки.
3. **Поддерживать чистый корень репозитория.**
   - Группировать dev-only материалы и обновлять README/CONTRIBUTING.
4. **Закрепить аудит в процессах.**
   - Проверки: `repo_tools/ci-lint.sh`, `repo_tools/smoke-workflow.sh`.
   - Регулярно сверять `doc/dev/distro-audit.md` перед релизом.
