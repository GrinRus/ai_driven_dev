# Research Summary — {{feature}}

Status: pending
Last reviewed: {{date}}
Commands:
  Research scan: claude-workflow research --ticket {{ticket}} --auto --paths {{paths}} --keywords {{keywords}}
  Search: rg "{{ticket|feature}}" {{modules}}
Artifacts:
  PRD: aidd/docs/prd/{{ticket}}.prd.md
  Tasklist: aidd/docs/tasklist/{{ticket}}.md

## AIDD:CONTEXT_PACK
- {{summary_short}}
- Limit: <= 20 lines / <= 1200 chars.

## AIDD:NON_NEGOTIABLES
- {{non_negotiables}}

## AIDD:OPEN_QUESTIONS
- {{open_questions}}

## AIDD:RISKS_TOP5
- {{risks_top5}}

## AIDD:DECISIONS
- {{decisions}}

## AIDD:INTEGRATION_POINTS
- {{integration_points}}

## AIDD:REUSE_CANDIDATES
- {{reuse_candidates}}

## AIDD:COMMANDS_RUN
- {{commands_run}}

## AIDD:TEST_HOOKS
- {{test_hooks}}

## AIDD:GAPS
- {{gaps}}

## Context Pack (TL;DR)
- **Entry points:** {{entry_points}}
- **Reuse candidates:** {{reuse_candidates}}
- **Integration points:** {{integration_points}}
- **Test pointers:** {{test_pointers}}
- **Top risks:** {{risks_top5}}
- Keep concise; may be longer than AIDD:CONTEXT_PACK.

## Definition of reviewed
- Найдены ≥ 1 точки интеграции или явно указан baseline.
- Указаны тесты/контракты или явно зафиксирован риск «нет тестов».
- Зафиксированы команды/пути сканирования и ссылки на отчёты.

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
