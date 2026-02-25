# Research Summary — {{feature}}

Status: {{doc_status}}
Last reviewed: {{date}}
Commands:
  Research scan: python3 ${CLAUDE_PLUGIN_ROOT}/skills/researcher/runtime/research.py --ticket {{ticket}} --auto --paths {{paths}} --keywords {{keywords}}
  Search: rg "{{ticket|feature}}" {{modules}}
Artifacts:
  PRD: aidd/docs/prd/{{ticket}}.prd.md
  Tasklist: aidd/docs/tasklist/{{ticket}}.md

## AIDD:CONTEXT_PACK
- {{summary_short}}
- Limit: <= 20 lines / <= 1200 chars.
- Paths discovered: {{paths_discovered}}
- Invalid paths: {{invalid_paths}}
- Pack-first: используйте `*-rlm.pack.*` и `rlm-slice`; не вставляйте raw JSONL.

## AIDD:PRD_OVERRIDES
{{prd_overrides}}
- Должно совпадать с PRD (`USER OVERRIDE`) и не противоречить принятым решениям.

## AIDD:NON_NEGOTIABLES
- {{non_negotiables}}

## AIDD:OPEN_QUESTIONS
- {{open_questions}}

## AIDD:RISKS
- {{risks}}

## AIDD:DECISIONS
- {{decisions}}

## AIDD:INTEGRATION_POINTS
- {{integration_points}}

## AIDD:REUSE_CANDIDATES
- {{reuse_candidates}}

## AIDD:COMMANDS_RUN
- {{commands_run}}

## AIDD:RLM_EVIDENCE
- Status: {{rlm_status}}
- Pack: {{rlm_pack_path}}
- Pack status: {{rlm_pack_status}}
- Pack bytes: {{rlm_pack_bytes}}
- Pack updated_at: {{rlm_pack_updated_at}}
- Warnings: {{rlm_warnings}} (e.g., rlm_links_empty_warn)
- Pending reason: {{rlm_pending_reason}}
- Next action: {{rlm_next_action}}
- Baseline marker: {{rlm_baseline_marker}}
- Auto recovery: auto_recovery_attempted={{rlm_auto_recovery_attempted}}, bootstrap_attempted={{rlm_bootstrap_attempted}}, finalize_attempted={{rlm_finalize_attempted}}, recovery_path={{rlm_recovery_path}}
- Slice: python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-rlm/runtime/rlm_slice.py --ticket {{ticket}} --query "<token>"
- Nodes/links: {{rlm_nodes_path}} / {{rlm_links_path}} (не читать целиком)

## AIDD:TEST_HOOKS
- {{test_hooks}}
- Evidence: {{tests_evidence}}
- Suggested tasks: {{suggested_test_tasks}}

## Context Pack (TL;DR)
- **Entry points:** {{entry_points}}
- **Reuse candidates:** {{reuse_candidates}}
- **Integration points:** {{integration_points}}
- **RLM:** {{rlm_summary}} (pack: {{rlm_pack_path}})
- **Test pointers:** {{test_pointers}}
- **Top risks:** {{risks}}
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

## RLM evidence (если применимо)
- {{rlm-note}} (сводка по модулям/связям; используйте rlm-slice для точечных запросов)
- Pack: {{rlm_pack_path}}

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
