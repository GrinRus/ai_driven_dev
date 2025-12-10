# Git Hook Templates

Скопируйте нужные файлы из этого каталога в `.git/hooks/`, убрав суффикс `.sample`, и сделайте их исполняемыми:

```bash
cp templates/git-hooks/commit-msg.sample .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
```

Аналогично для других хуков. Переменные окружения и конфигурация описаны внутри файлов.

| Файл | Назначение |
| --- | --- |
| `commit-msg.sample` | Проверяет сообщение коммита на соответствие активной конвенции из `config/conventions.json`. |
| `prepare-commit-msg.sample` | Предзаполняет шаблон сообщения на основе ветки и режима. |
| `pre-push.sample` | Выполняет `${CLAUDE_PROJECT_DIR}/.claude/hooks/format-and-test.sh` перед пушем, чтобы поймать ошибки локально. |

## Рекомендации
- Добавьте `export PRE_PUSH_SKIP=1` или аналогичные переменные в rare-case сценариях (см. скрипты).
- Сохраняйте хуки под контролем версий в `templates/git-hooks/`, а в `.git/hooks/` держите копии.
- При обновлении шаблонов перезапишите файлы в `.git/hooks/` и снова установите бит исполнения.
