# План разделения (marketplace-only)

## Входные документы
- `dev/doc/distro-audit.md`
- `dev/doc/root-audit.md`

## Шаги
1. **Утвердить границу runtime vs dev-only.**
   - Runtime: `commands/`, `agents/`, `hooks/`, `tools/`, `.claude-plugin/`.
   - Шаблоны workspace: `templates/aidd/`.
   - Dev-only: `dev/doc/`, `dev/tests/`, `dev/repo_tools/`.
2. **Зафиксировать источник истины для шаблонов.**
   - Все изменения шаблонов делаются в `templates/aidd/`.
   - `/feature-dev-aidd:aidd-init` остаётся идемпотентным и не перезаписывает пользовательские правки.
3. **Поддерживать чистый корень репозитория.**
   - Группировать dev-only материалы и обновлять README/CONTRIBUTING.
4. **Закрепить аудит в процессах.**
   - Проверки: `dev/repo_tools/ci-lint.sh`, `dev/repo_tools/smoke-workflow.sh`.
   - Регулярно сверять `dev/doc/distro-audit.md` перед релизом.
