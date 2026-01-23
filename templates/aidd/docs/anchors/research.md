# Anchor: research

## Goals
- Собрать подтверждённые integration points, reuse, risks, test hooks.
- Обновить research report и дать handoff в tasklist.
- Status reviewed — только при воспроизводимом сборе (commands + paths).

## RLM Read Policy
- MUST: читать `aidd/reports/research/<ticket>-rlm.pack.*` first.
- PREFER: использовать `rlm-slice` pack для узких запросов.
- MUST NOT: читать `*-rlm.nodes.jsonl` или `*-rlm.links.jsonl` целиком; только spot‑check через `rg`.

## MUST READ FIRST
- aidd/docs/prd/<ticket>.prd.md: AIDD:RESEARCH_HINTS
- aidd/reports/research/<ticket>-context.pack.* (pack-first)
- aidd/reports/research/<ticket>-rlm.pack.* (pack-first)
- aidd/reports/context/<ticket>-rlm-slice-<sha1>.pack.* (если нужно)
- aidd/reports/research/<ticket>-context.json (если pack нет)
- aidd/docs/research/<ticket>.md (если существует)

## Schema notes
- `keywords_raw` и `non_negotiables` хранят исходные подсказки (не идут в фильтры).
- `paths_discovered` и `invalid_paths` показывают авто‑discovery и проблемы пути.
- `tests_evidence`/`suggested_test_tasks` помогают понять, где есть тесты и что запускать.
- `rlm_status` отражает готовность RLM evidence (`pending|ready`).
- `rlm_*_path` указывают targets/manifest/nodes/links/pack.
- `*-rlm.nodes.jsonl`/`*-rlm.links.jsonl` читать фрагментами, не целиком.

## MUST UPDATE
- aidd/docs/research/<ticket>.md:
  - AIDD:INTEGRATION_POINTS
  - AIDD:REUSE_CANDIDATES
  - AIDD:RISKS
  - AIDD:TEST_HOOKS
  - Commands run / paths

## MUST NOT
- Писать “возможно” без файлов/команд.
- Вставлять большие JSON — только ссылки/pack/slice.
- Читать `*-rlm.nodes.jsonl`/`*-rlm.links.jsonl` целиком (только `rg`/срезы).
- Читать `*-context.json` целиком — только pack или фрагменты (offset/limit).

## Output contract
- Status: reviewed|pending
- Handoff: задачи формата "Research: ..." (source: aidd/reports/research/...).
