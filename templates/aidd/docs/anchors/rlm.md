# Anchor: rlm

## Goals
- Provide verified RLM evidence (recursive summaries + verified links).
- Keep packs small and deterministic (pack-first, slice on demand).

## RLM Read Policy
- MUST: read `aidd/reports/research/<ticket>-rlm.pack.*` first.
- PREFER: use `rlm-slice` pack for focused queries.
- MUST NOT: read `*-rlm.nodes.jsonl` or `*-rlm.links.jsonl` fully (only spot checks).

## MUST READ FIRST
- `aidd/reports/research/<ticket>-rlm.pack.*`
- `aidd/reports/context/<ticket>-rlm-slice-<sha1>.pack.*` (if needed)
- `aidd/reports/research/<ticket>-context.pack.*`

## MUST UPDATE
- `aidd/docs/research/<ticket>.md` (integration points, reuse, risks, tests)
- `aidd/reports/research/<ticket>-rlm.pack.*`

## MUST NOT
- Dump large JSONL into reports.
- Read full `*-rlm.nodes.jsonl` or `*-rlm.links.jsonl`.
