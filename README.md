# Claude Code Workflow — Java/Kotlin Monorepo (Template)

Готовый **GitHub‑шаблон** и инсталлятор, который добавляет в ваш репозиторий
рабочий флоу для **Claude Code**: слэш‑команды, саб‑агенты, безопасные хуки и
поддержку **монорепозитория Gradle** с запуском тестов **только по затронутым модулям**.
Также включены шаблоны PRD/ADR, настраиваемые ветки/коммиты и (опционально) CI‑workflow.

> ❗️Проект не зависит от Spec Kit и BMAD. Всё локально, просто и прозрачно.

---

## 📦 Возможности

- **Слэш‑команды Claude Code** для вашего `<work_flow>`: PRD → ADR → Tasks → Docs.
- **Выборочные Gradle‑тесты** в монорепо: определяет затронутые модули по `git diff`
  и запускает `:module:clean :module:test` (fallback `:jvmTest`/Android).
- **Кастомизация веток/коммитов** через `config/conventions.json`:
  - `ticket-prefix` (например, `STORE-123: ...` из ветки `feature/STORE-123`),
  - `conventional` (`feat(scope): ...` из ветки `feat/scope`),
  - `mixed` (`STORE-123 feat(scope): ...` из ветки `feature/STORE-123/feat/scope`).
- **Хуки безопасности**: блокировка правок прод‑артефактов, автоматическое форматирование
  (Spotless/ktlint, если доступны) и автозапуск тестов после правок.
- **Готовность к GitHub**: LICENSE, README, CONTRIBUTING, Code of Conduct, Issue/PR шаблоны,
  (опционально) CI с кэшем Gradle.
- **Мягкие зависимости** — если чего‑то нет (например, ktlint), скрипты не ломают поток.

---

## 🚀 Установка

### Вариант A — через curl (рекомендуется для публичного шаблона)

> Замените `<your-org>/<repo>` на ваш репозиторий‑шаблон, где лежит `init-claude-workflow.sh`.

```bash
curl -fsSL https://raw.githubusercontent.com/<your-org>/<repo>/main/init-claude-workflow.sh \
  | bash -s -- --commit-mode ticket-prefix --enable-ci
```

### Вариант B — локально

1) Сохраните `init-claude-workflow.sh` в корень проекта.  
2) Выполните:

```bash
bash init-claude-workflow.sh --commit-mode ticket-prefix --enable-ci
# опции:
#   --commit-mode ticket-prefix | conventional | mixed
#   --enable-ci   добавить шаблон CI (ручной запуск по умолчанию)
#   --force       перезаписывать существующие файлы
```

После инициализации сделайте коммит:
```bash
git add -A && git commit -m "chore: bootstrap Claude Code workflow"
```

---

## ✅ Предпосылки

- **Bash**, **Git**, **Python 3**;
- **Gradle wrapper** (`./gradlew`) **или** установленный Gradle;
- (опц.) **ktlint** и/или плагин **Spotless** в проекте — для автоформатирования.

Работает на macOS/Linux. На Windows используйте WSL или Git Bash.

---

## 🧭 Быстрый старт в Claude Code

Откройте проект в Claude Code и выполните команды:

```
/branch-new feature STORE-123
/feature-new checkout-discounts STORE-123
/feature-adr checkout-discounts
/feature-tasks checkout-discounts
/commit "UC1: implement rule engine"
/test-changed
```

**Что произойдёт:**  
- создастся PRD/ADR/Tasklist,  
- при правках сработает автоформат и запустятся тесты изменённых модулей,  
- `/commit` сформирует корректное сообщение по выбранному режиму.

---

## 🧩 Слэш‑команды

| Команда | Назначение | Аргументы (пример) |
|---|---|---|
| `/branch-new` | Создать/переключить ветку по пресету | `feature STORE-123` / `feat orders` / `mixed STORE-123 feat pricing` |
| `/feature-new` | Создать PRD и стартовые артефакты | `checkout-discounts STORE-123` |
| `/feature-adr` | Сформировать ADR из PRD | `checkout-discounts` |
| `/feature-tasks` | Обновить `tasklist.md` | `checkout-discounts` |
| `/docs-generate` | Сгенерировать/обновить документацию | — |
| `/test-changed` | Прогнать тесты по затронутым Gradle‑модулям | — |
| `/conventions-set` | Сменить режим коммитов | `conventional` / `ticket-prefix` / `mixed` |
| `/conventions-sync` | Синхронизировать `conventions.md` с Gradle‑конфигами | — |
| `/commit` | Сформировать и сделать коммит | `"implement rule engine"` |
| `/commit-validate` | Проверить сообщение коммита на соответствие режиму | `"feat(orders): add x"` |

---

## 🧾 Режимы веток/коммитов

Файл: `config/conventions.json`

**ticket-prefix** (по умолчанию)  
- Ветка: `feature/STORE-123` → Коммит: `STORE-123: краткое описание`

**conventional**  
- Ветка: `feat/orders` → Коммит: `feat(orders): краткое описание`

**mixed**  
- Ветка: `feature/STORE-123/feat/orders` → Коммит: `STORE-123 feat(orders): краткое описание`

Сменить режим:
```text
/conventions-set conventional
```

(Для принудительной проверки добавьте git‑хук `commit-msg` — пример в разделе «Полезно».)

---

## 🏗️ Монорепо Gradle: как работают выборочные тесты

Скрипт `.claude/hooks/format-and-test.sh` делает следующее:

1. **Форматирует код** (Spotless/ktlint — если доступны).  
2. **Строит карту проектов Gradle** через init‑скрипт `.claude/gradle/init-print-projects.gradle`
   и кэширует её в `.claude/cache/project-dirs.txt` (вид `:path=/abs/dir`).  
3. Собирает список изменённых файлов (`git diff` + untracked).  
4. Фильтрует только влияющие на сборку (`src/**`, `build.gradle*`, `settings.gradle*`, `gradle/libs.versions.toml`).  
5. Сопоставляет каждый файл с **наиболее глубоким** модульным каталогом из карты.  
6. Запускает одним вызовом Gradle набор задач вида:  
   `:moduleA:clean :moduleA:test :moduleB:clean :moduleB:test`  
   Если `:test` не найден (KMP/Android), пытается `:jvmTest`/`:testDebugUnitTest`.  
7. Если не удалось выделить модули, выполняет `gradle test` всего репо (fallback).

> Поведение «мягкое»: падение тестов не блокирует правки (удалите `|| true` в скрипте, чтобы сделать строгим).

---

## 🗂️ Что будет создано

```
.claude/
  settings.json
  commands/*.md
  agents/*.md
  hooks/{protect-prod.sh, format-and-test.sh}
  gradle/init-print-projects.gradle
config/conventions.json
scripts/{branch_new.py, commit_msg.py, conventions_set.py}
docs/{prd.template.md, adr.template.md}
CLAUDE.md, conventions.md, workflow.md, tasklist.md
.github/ISSUE_TEMPLATE/*, .github/PULL_REQUEST_TEMPLATE.md
(optional) .github/workflows/gradle.yml
```

---

## ⚙️ CI (опционально)

Флаг `--enable-ci` добавляет `.github/workflows/gradle.yml` с ручным триггером:

```yaml
on: { workflow_dispatch: {} }
```

Чтобы запускать на PR, замените на:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened]
```

Workflow запускает тот же скрипт выборочных тестов, что и локально.

---

## 🛡️ Безопасность по умолчанию

- **PreToolUse‑хук** блокирует правки в `infra/prod/**`, prod‑конфигов и секретов.  
- `.claude/settings.json` ограничивает доступ к инструментам: `allow/ask/deny`.  
- `ask` на `git commit/push` — вы подтверждаете чувствительные действия явно.

---

## 🛠️ Полезно

### Git‑хук для проверки сообщений коммитов

```bash
mkdir -p .git/hooks
cat > .git/hooks/commit-msg <<'HOOK'
#!/usr/bin/env bash
python3 scripts/commit_msg.py --validate "$(cat "$1")" >/dev/null || {
  echo "❌ Commit message не соответствует активному режиму в config/conventions.json" 1>&2
  exit 1
}
HOOK
chmod +x .git/hooks/commit-msg
```

### Смена режима коммитов

```
/conventions-set ticket-prefix
```

### Создание веток (CLI, без /branch-new)

```bash
python3 scripts/branch_new.py feature STORE-123 | { read n; git checkout -b "$n"; }
```

---

## ❓ Траблшутинг

- **`./gradlew: not found`** — добавьте Gradle wrapper в проект или установите Gradle.  
- **Форматирование не применяется** — подключите Spotless/ktlint (иначе просто пропускается).  
- **Скрипт «не видит» модуль** — убедитесь, что модуль включён в `settings.gradle*`.  
- **Запускаются все тесты** — изменены общие файлы (напр. `settings.gradle`/`libs.versions.toml`) — это намеренно.  
- **Claude Code спрашивает разрешение на commit/push** — это ожидаемо (политика `ask`).

---

## 🤝 Вклад

PR/Issues приветствуются. Перед отправкой:
1. Соблюдайте выбранный режим веток/коммитов.  
2. Добавьте юнит‑тесты.  
3. Убедитесь, что `/test-changed` проходит локально.

---

## 📄 Лицензия

MIT © 2025. Используйте свободно, с сохранением уведомления об авторских правах.

---

### Отказ от ответственности
Этот шаблон создан для упрощения работы с Claude Code в проектах на Java/Kotlin.
Он не является официальным продуктом и не аффилирован с поставщиками IDE/инструментов.
