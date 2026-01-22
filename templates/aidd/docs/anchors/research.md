# Anchor: research

## Goals
- Собрать подтверждённые integration points, reuse, risks, test hooks.
- Обновить research report и дать handoff в tasklist.
- Status reviewed — только при воспроизводимом сборе (commands + paths).

## Graph Read Policy
- MUST: читать `aidd/reports/research/<ticket>-call-graph.pack.*` или `graph-slice` pack.
- MUST: точечный `rg` по `aidd/reports/research/<ticket>-call-graph.edges.jsonl`.
- MUST NOT: читать raw call-graph артефакты; используйте только pack/edges/slice.

## MUST READ FIRST
- aidd/docs/prd/<ticket>.prd.md: AIDD:RESEARCH_HINTS
- aidd/reports/research/<ticket>-context.pack.* (pack-first)
- aidd/reports/research/<ticket>-ast-grep.pack.* (если есть)
- aidd/reports/research/<ticket>-call-graph.pack.* (если есть)
- aidd/reports/research/<ticket>-context.json (если pack нет)
- aidd/docs/research/<ticket>.md (если существует)

## Schema notes
- `keywords_raw` и `non_negotiables` хранят исходные подсказки (не идут в фильтры).
- `paths_discovered` и `invalid_paths` показывают авто‑discovery и проблемы пути.
- `tests_evidence`/`suggested_test_tasks` помогают понять, где есть тесты и что запускать.
- `call_graph_edges_path`/`call_graph_edges_stats` указывают view `*-call-graph.edges.jsonl` и его лимиты.
- `ast_grep_path`/`ast_grep_stats` указывают структурный scan и его лимиты.
- `*-call-graph.edges.jsonl` schema (v1): `schema`, `caller`, `callee`, `caller_file`, `caller_line`, `callee_file`, `callee_line`, `lang`, `type`.
- `*-ast-grep.jsonl` schema (v1): `schema`, `rule_id`, `path`, `line`, `col`, `snippet`, `message`, `tags`.

## MUST UPDATE
- aidd/docs/research/<ticket>.md:
  - AIDD:INTEGRATION_POINTS
  - AIDD:REUSE_CANDIDATES
  - AIDD:RISKS
  - AIDD:TEST_HOOKS
  - AIDD:AST_GREP_EVIDENCE (если есть pack/jsonl)
  - Commands run / paths

## MUST NOT
- Писать “возможно” без файлов/команд.
- Вставлять большие JSON — только ссылки/pack/slice.
- Читать `*-call-graph.edges.jsonl` целиком (только `rg`/срезы).
- Читать `*-context.json` целиком — только pack или фрагменты (offset/limit).

## Output contract
- Status: reviewed|pending
- Handoff: задачи формата "Research: ..." (source: aidd/reports/research/...).
