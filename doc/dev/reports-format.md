# Reports Format (MVP)

This document defines the minimal report contract for pack-first reading.

## Naming

- Research context: `aidd/reports/research/<ticket>-context.json` + `*.pack.yaml`/`*.pack.toon`
- Research targets: `aidd/reports/research/<ticket>-targets.json` (no pack)
- QA report: `aidd/reports/qa/<ticket>.json` + `*.pack.yaml`/`*.pack.toon`
- PRD review: `aidd/reports/prd/<ticket>.json` + `*.pack.yaml`/`*.pack.toon`
- Review report + reviewer marker (tests gate): `aidd/reports/reviewer/<ticket>.json` (not a pack report)
- Tests log (JSONL): `aidd/reports/tests/<ticket>.jsonl`

The pack file is JSON (valid YAML) for deterministic output. When `AIDD_PACK_FORMAT=toon`,
the output is still JSON-encoded but stored as `.pack.toon` (format is experimental).

## Pack-first

Consumers should read `*.pack.yaml` when available and fall back to the JSON report.
When `AIDD_PACK_FORMAT=toon` is set, prefer `*.pack.toon` and fall back to `*.pack.yaml` or JSON.

## Report header (common)

Each report (JSON or JSONL entry) should include these fields when applicable:
- `ticket`
- `stage`
- `status`
- `started_at`
- `finished_at`
- `tool_versions`
- `summary`

## Determinism contract

For a fixed tool version and identical input JSON, the pack output must be byte-identical.

Rules:
- Stable key ordering in serialized output.
- Stable list truncation (top-N limits only, no random sampling).
- String truncation is deterministic.
- Findings include stable `id` values (QA/PRD/Review) for diff-friendly updates.

## Columnar sections

Uniform arrays use a columnar layout:

```
section:
  cols: [col_a, col_b]
  rows:
    - [a1, b1]
    - [a2, b2]
```

## Budgets

`aidd/reports/research/*-context.pack.yaml`:
- Total size target: <= 1200 chars, <= 60 lines
- Matches: max 20 entries, snippet <= 240 chars
- Reuse candidates: max 8 entries
- Call graph edges: max 30 entries
- Import graph entries: max 30 entries
- Recommendations: max 10 entries
- Manual notes: max 10 entries
- Paths/docs/tags/keywords: max 10 entries each

`aidd/reports/qa/*.pack.yaml`:
- Findings: max 20 entries
- Tests executed: max 10 entries

`aidd/reports/prd/*.pack.yaml`:
- Findings: max 20 entries
- Action items: max 10 entries

Override budgets with `AIDD_PACK_LIMITS` (JSON), e.g.
`AIDD_PACK_LIMITS='{"research":{"matches":10},"qa":{"findings":5}}'`.

Budget enforcement runs in CI/tests; reduce top-N, trim snippets, or use `AIDD_PACK_LIMITS` when budgets are exceeded.
QA/PRD budgets are enforced on entry counts (findings/action_items/tests_executed).
Set `AIDD_PACK_ENFORCE_BUDGET=1` to fail pack generation on budget violations.
Research context packs auto-trim when over budget (pack only; full JSON unchanged). Trim order:
matches → call_graph → import_graph → reuse_candidates → manual_notes → profile.recommendations → paths.sample → docs.sample → paths → docs → drop empty columnar sections → drop stats.

## Field policy

Pack includes:
- Ticket metadata (ticket/slug/generated_at/tags/keywords)
- Paths/docs summaries
- Profile summary + recommendations
- Manual notes
- Reuse candidates (top-N)
- Matches (top-N)
- Call/import graph samples (top-N)
- call_graph_full_path (reference to full JSON if present)
- call_graph_full_columnar_path (reference to columnar full graph if present)

Pack excludes:
- code_index (full symbol lists)
- call_graph_full payloads
- raw file contents beyond snippets

## Patch updates (optional)

When `--emit-patch` is enabled and a previous report exists, emit RFC6902 patches to
`aidd/reports/<type>/<ticket>.patch.json`. Operations are limited to `add/remove/replace`,
and list changes are expressed as `replace` of the whole list.
Apply patches with `repo_tools/apply_json_patch.py --input <report.json> --patch <report.patch.json>`.

## Pack-only + field filters (optional)

- `--pack-only` or `AIDD_PACK_ONLY=1`: remove the JSON report after pack is written.
- `AIDD_PACK_ALLOW_FIELDS=...` and `AIDD_PACK_STRIP_FIELDS=...`: comma-separated top-level
  keys to include/remove in the pack (essential metadata keys are preserved).

## Research context pack (MVP)

Top-level keys used by consumers:
- profile.recommendations
- manual_notes
- reuse_candidates (columnar)

Additional top-level keys may include: ticket, slug, generated_at, keywords, tags, paths, docs,
call_graph, import_graph, call_graph_full_path, call_graph_full_columnar_path, call_graph_warning, deep_mode, auto_mode.

Columnar full graph:
- `aidd/reports/research/<ticket>-call-graph-full.cjson`
- format: `cols` + `rows` for edges; `imports` kept as list of objects

Columnar schemas:
- matches: `id, token, file, line, snippet`
- reuse_candidates: `id, path, language, score, has_tests, top_symbols, imports`
- call_graph: `caller, callee, file, line, language`
- import_graph: `import`

## QA pack

Top-level keys:
- ticket, slug_hint, generated_at, status, summary, branch
- counts, tests_summary
- findings (columnar)
- tests_executed (columnar)

Columnar schemas:
- findings: `id, severity, scope, blocking, title, details, recommendation` (scope = iteration_id or n/a)
- tests_executed: `command, status, log, exit_code`

## PRD review pack

Top-level keys:
- ticket, slug, generated_at, status, recommended_status
- findings (columnar)
- action_items

Columnar schemas:
- findings: `id, severity, title, details`

## Review report

Top-level keys:
- ticket, slug, generated_at, updated_at, status, summary, stage, kind
- tests (optional reviewer marker field, e.g. required/optional)
- findings (list of objects)

Finding schema:
- id (stable)
- severity, scope (iteration_id or n/a), blocking, title, details, recommendation
- first_seen_at, last_seen_at

## Hotspots (auto)

<!-- report-stats:start -->
No reports found. Run `python3 repo_tools/report_stats.py --write` after reports exist.
<!-- report-stats:end -->
