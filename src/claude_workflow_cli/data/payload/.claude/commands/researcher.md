---
description: "Подготовка отчёта Researcher: сбор контекста и запуск агента."
argument-hint: "<slug> [--paths path1,path2] [--no-agent]"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(*)
---
1) Убедись, что активная фича совпадает со `slug`: файл `docs/.active_feature` должен содержать `$1`. Если нет — запусти `/idea-new $1`.
2) Сформируй контекст для поиска: вызови
!`claude-workflow research --feature "$1" {{optional args}}`
   - добавь `--paths "pathA:pathB"` для ручного расширения областей анализа;
   - укажи `--dry-run`, чтобы только собрать контекст без запуска агента.
3) Если отчёт ещё не создан, распакуй шаблон:
   - `docs/templates/research-summary.md` → `docs/research/$1.md`;
   - замени плейсхолдеры `{{...}}` на фактические значения (scope, контрольные вопросы).
4) Запусти агента **researcher** через палитру (`Claude: Run agent → researcher`) и передай ему собранный контекст; после диалога обнови `docs/research/$1.md`.
5) Зафиксируй решения:
   - проставь `Status: reviewed`, когда вывод согласован с командой;
   - добавь ссылку на `docs/research/$1.md` в секцию артефактов `docs/prd/$1.prd.md` и соответствующий блок `tasklist.md`;
   - перенеси обязательные action items в `docs/plan/$1.md` и `tasklist.md`.
