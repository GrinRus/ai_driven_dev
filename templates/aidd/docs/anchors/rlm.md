# Anchor: rlm

## Goals
- Provide verified RLM evidence (recursive summaries + verified links).
- Keep packs small and deterministic (pack-first, slice on demand).

## Canonical policy
- Следуй `aidd/AGENTS.md` для Context precedence & safety и Evidence Read Policy (RLM-first).
- Если текущий anchor конфликтует с каноном — STOP и верни BLOCKED с указанием файлов/строк.

## MUST READ FIRST
- `aidd/docs/architecture/profile.md` (allowed deps + invariants)
- `aidd/reports/research/<ticket>-rlm.pack.*`
- `aidd/reports/context/<ticket>-rlm-slice-<sha1>.pack.*` (if needed)
- `aidd/reports/research/<ticket>-context.pack.*`

## MUST UPDATE
- `aidd/docs/research/<ticket>.md` (integration points, reuse, risks, tests)
- `aidd/reports/research/<ticket>-rlm.pack.*`

## MUST NOT
- Dump large JSONL into reports.
- Read full `*-rlm.nodes.jsonl` or `*-rlm.links.jsonl`.

## Pack budgets
- `rlm.pack_budget.max_lines`/`max_chars` в `config/conventions.json` управляют размером `*-rlm.pack.*` (default: `max_lines=240`, `max_chars=12000`).
- Если pack триммится слишком агрессивно — поднимите лимиты или сузьте scope.

## Type Refs Notes
- Для Java включайте в `type_refs` типы из `extends/implements`, record/enum компонентов и публичных API (field/param/return).
