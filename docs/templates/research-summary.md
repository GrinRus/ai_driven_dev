# Research Summary — {{feature}}

Status: pending
Last reviewed: {{date}}
Commands:
  Research scan: claude-workflow research --ticket {{ticket}} --auto --paths {{paths}} --keywords {{keywords}}
  Search: rg "{{ticket|feature}}" {{modules}}
Artifacts:
  PRD: docs/prd/{{ticket}}.prd.md
  Tasklist: docs/tasklist/{{ticket}}.md

## Контекст
- **Цель фичи:** {{goal}}
- **Scope изменений:** {{scope}}
- **Ключевые модули/директории:** {{modules}}
- **Исходные артефакты:** {{inputs}}
- **Логи команд / отчёты:** {{logs}}

## Точки интеграции
- {{target-point}} (файл/класс/endpoint)

## Повторное использование
- {{reused-component}} (ссылка на код/модуль)

## Принятые практики
- {{guideline}} (ссылка на тест/лог, который это подтверждает)

## Паттерны/анти-паттерны
- **Паттерны:** {{positive-patterns}}
- **Анти-паттерны:** {{negative-patterns}}

## Отсутствие паттернов / отсутствующие данные
- {{empty-context-note}} (перечислите команды/пути, которые ничего не нашли)

## Gap-анализ
- {{gap-description}} (ссылка на ограничение + предложенный компенсационный шаг)

## Следующие шаги
- {{next-step}} (укажите, кто и какой файл/команду должен обновить)

## Дополнительные заметки
- {{manual-note}}

## Открытые вопросы
- {{question}}
