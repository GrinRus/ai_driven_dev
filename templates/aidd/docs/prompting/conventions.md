# Prompting Conventions (AIDD)

Единый канон для промптов/команд/агентов: термины, статусы, контракт вывода и правила артефактов.

## Термины и источники истины
- **Artifact status**: `READY|WARN|BLOCKED|PENDING|DRAFT` (по типу артефакта).
- **Review verdict**: `SHIP|REVISE|BLOCKED` (только для review pack).
- **Stage result**: `blocked|continue|done` — **машинная истина для loop-gating**.
- **work_item_key**: логический ключ итерации (`iteration_id=I1` или `id=review:F6`).
- **scope_key**: безопасный для пути ключ (sanitize от `work_item_key`; для ticket‑scoped стадий = ticket).

## Evidence read policy (pack/excerpt-first)
- Порядок чтения: loop pack → review pack (если есть) → excerpt.
- Запрещено читать full PRD/Plan/Tasklist/Research целиком, если excerpt достаточен.
- `Context read` перечисляет только packs/excerpts (без простыней).

## Output‑контракт (lint‑ready)
Subagents implement/review/qa обязаны:
- `Status: READY|WARN|BLOCKED|PENDING` (implementer) или `Status: READY|WARN|BLOCKED` (reviewer/qa).
- `Work item key: ...`.
- `Artifacts updated: ...`.
- `Tests: run|skipped|not-required <profile/summary/evidence>`.
- `Blockers/Handoff: ...` (если пусто — `none`).
- `Next actions: ...`.
- `Context read: <packs/excerpts only>`.

Команды implement/review/qa обязаны выводить тот же core (без `Context read`).

Опционально (stage‑dependent): `Checkbox updated: ...`.

## BLOCKED правила
BLOCKED означает одно из:
- отсутствуют обязательные артефакты/статусы;
- `FORBIDDEN` нарушает boundaries;
- нет обязательных команд тестов или `tests_required=hard` без evidence;
- не закрыты вопросы/hand‑off’ы, требующие решения.

## WARN правила
WARN означает:
- out‑of‑scope (`OUT_OF_SCOPE|NO_BOUNDARIES_DEFINED`) → handoff + `reason_code=out_of_scope_warn|no_boundaries_defined_warn`;
- `tests_required=soft` и нет evidence → implement: `WARN`, review: `REVISE`, qa: `WARN` + handoff “run tests”.

## Parallel‑ready артефакты (per‑work‑item)
Используйте **scope_key** в путях:
- loop pack: `aidd/reports/loops/<ticket>/<scope_key>.loop.pack.md`
- review pack: `aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md`
- fix plan: `aidd/reports/loops/<ticket>/<scope_key>/review.fix_plan.json`
- stage result: `aidd/reports/loops/<ticket>/<scope_key>/stage.<stage>.result.json`
- review report: `aidd/reports/reviewer/<ticket>/<scope_key>.json`
- tests log: `aidd/reports/tests/<ticket>/<scope_key>.jsonl`

Ticket‑scoped стадии (QA) используют `scope_key=<ticket>`.

## Granularity policy (tasklist)
Итерация должна быть “в одно окно” и не дробиться в песок:
- Steps: **3–7**
- Expected paths: **1–3** группы
- Size budget (ориентир): `max_files 3–8`, `max_loc 80–400`
- Микро‑шаги (“rename/format/лог”) — только как sub‑steps, не отдельная итерация.

## Loop дисциплина
- Loop‑gating опирается на `stage_result` (review pack / tasklist = evidence).
- В loop‑mode вопросы в чат **нельзя**: фиксируйте blocker/handoff в артефактах.
