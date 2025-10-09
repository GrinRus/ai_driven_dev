# Демонстрация использования `init-claude-workflow.sh`

Этот документ иллюстрирует, как установить Claude Code workflow на минимальный Gradle-монорепозиторий. В примере используется каталог `demo-monorepo`, но те же шаги применимы к любому Java/Kotlin проекту.

## Цель сценария
- развернуть шаблон всего за один запуск скрипта;
- понять, какие файлы и настройки добавляются;
- проверить, что выборочные тесты и хуки работают сразу после установки.

## Требования
- установленный `bash`, `git`, `python3`;
- Gradle wrapper (`./gradlew`) в корне демо-проекта;
- скрипт `init-claude-workflow.sh` расположен рядом с проектом или доступен по URL;
- опционально: `ktlint` или Spotless, чтобы увидеть работу автоформатирования.

## Структура до запуска

```text
demo-monorepo/
├── build.gradle.kts
├── settings.gradle.kts
├── gradle/
│   └── wrapper/…
├── service-checkout/
│   ├── build.gradle.kts
│   └── src/main/kotlin/CheckoutService.kt
└── service-payments/
    ├── build.gradle.kts
    └── src/main/kotlin/PaymentsService.kt
```

## Пошаговый walkthrough

### 1. Подготовьте окружение

```bash
git clone git@github.com:your-org/demo-monorepo.git
cd demo-monorepo
cp ../init-claude-workflow.sh .
chmod +x init-claude-workflow.sh
```

> Совет: если скрипт хранится в отдельном репозитории, загрузите его через `curl` или `wget`. Для публичных шаблонов чаще используют вариант с `curl`.

### 2. Запустите установку

```bash
bash init-claude-workflow.sh \
  --commit-mode ticket-prefix \
  --enable-ci \
  --force
```

- `--commit-mode` задаёт стартовый режим сообщений коммитов;
- `--enable-ci` добавляет workflow GitHub Actions;
- `--force` перезаписывает существующие файлы (удобно при повторном запуске на демо).

Ожидаемые лог-сообщения (сокращённо):

```text
[INFO] Checking prerequisites: bash ✅ python3 ✅ gradle ✅
[INFO] Generating Claude Code structure…
[INFO] Installing git hooks to .claude/hooks
[INFO] Writing config/conventions.json (mode=ticket-prefix)
[INFO] CI workflow enabled → .github/workflows/gradle.yml
[DONE] Claude Code workflow is ready to use 🎉
```

### 3. Проверьте git-статус и содержимое

```bash
git status -sb
```

```text
## main
A  .claude/settings.json
A  .claude/hooks/format-and-test.sh
A  config/conventions.json
…
```

При желании сделайте `git diff` по любому файлу, чтобы посмотреть значения по умолчанию.

### 4. Запустите выборочные тесты вручную (опционально)

```bash
.claude/hooks/format-and-test.sh
```

Проверьте, что скрипт определил Gradle-модули и запустил тесты только для них.

## Структура после запуска

```text
demo-monorepo/
├── .claude/
│   ├── agents/
│   ├── commands/
│   ├── gradle/init-print-projects.gradle
│   ├── hooks/{format-and-test.sh,protect-prod.sh}
│   ├── settings.json
│   └── cache/project-dirs.txt
├── config/conventions.json
├── docs/
│   ├── adr.template.md
│   ├── prd.template.md
│   └── tasklist.template.md
├── scripts/
│   ├── branch_new.py
│   ├── commit_msg.py
│   └── conventions_set.py
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── PULL_REQUEST_TEMPLATE.md
│   └── workflows/gradle.yml
└── README.md (обновлён)
```

> Снимок «после» удобно зафиксировать командой `tree -L 2` или встроенным предпросмотром IDE. Для презентаций добавьте изображения каталога до/после в `docs/images/`.

## Проверка результата в Claude Code
1. Откройте проект и выполните `/test-changed` — убедитесь, что скрипт проходит без ошибок.
2. Создайте ветку через `/branch-new feature DEMO-1` и убедитесь, что формат ветки корректный.
3. Запустите `/feature-new checkout-discounts DEMO-1` и проверьте, что шаблоны PRD/ADR/Tasklist добавлены.
4. Для проверки политик сделайте тестовый коммит `/commit "DEMO-1: spike"` — сообщение должно соответствовать режиму из `config/conventions.json`.

## Частые вопросы
- **Запуск скрипта терпит неудачу:** проверьте вывод проверки зависимостей и убедитесь, что Gradle доступен в PATH.
- **Тесты не стартуют:** убедитесь, что `./gradlew` исполняемый (`chmod +x gradlew`) и что скрипт имеет права на запуск.
- **Файлы уже существуют:** добавьте `--force`, но предварительно сохраните изменения в git или сделайте резервную копию.
- **Нужно повторно прогнать установку:** скрипт безопасно перезаписывает артефакты. Чтобы увидеть только изменения, используйте `git diff`.

Теперь демо-проект готов к работе с Claude Code workflow. Сохраните изменения (`git commit`) или удалите установленную структуру и повторите сценарий для отладки.
