# Research Summary — {{feature}}

Status: pending
Last reviewed: {{date}}
Commands:
  Research scan: claude-workflow research --ticket {{ticket}} --auto --paths {{paths}} --keywords {{keywords}}
  Search: rg "{{ticket|feature}}" {{modules}}
Artifacts:
  PRD: aidd/docs/prd/{{ticket}}.prd.md
  Tasklist: aidd/docs/tasklist/{{ticket}}.md

## Контекст
- **Цель фичи:** {{goal}}
- **Scope изменений:** {{scope}}
- **Ключевые модули/директории:** {{modules}}
- **Исходные артефакты:** {{inputs}}
- **Логи команд / отчёты:** {{logs}}

## Точки интеграции
- {{target-point}} (файл/класс/endpoint → куда вставляем → связанные вызовы/импорты)

## Повторное использование
- {{reused-component}} (путь → как использовать → риски → тесты/контракты)

## Принятые практики
- {{guideline}} (ссылка на тест/лог/контракт, который это подтверждает)

## Граф вызовов/импортов (если применимо)
- {{graph-note}} (кто вызывает/импортирует целевой модуль; источники из call graph/import graph для поддерживаемых языков)

## Паттерны/анти-паттерны
- **Паттерны:** {{positive-patterns}} (ссылки на код/тесты)
- **Анти-паттерны:** {{negative-patterns}} (ссылки на код/тесты)

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
