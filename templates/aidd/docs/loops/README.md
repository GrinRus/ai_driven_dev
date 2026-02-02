# Loop Mode (Ralph)

Loop = 1 work_item → implement → review → (revise)* → ship.

## Правила
- Начинай каждую итерацию с `loop_pack` (тонкий контекст). Не вставляй большие куски логов/диффов — только ссылки на `aidd/reports/**`.
- REVISE повторяет implement на том же work_item: `AIDD:NEXT_3` и чекбокс итерации не меняются, `.active_work_item` остаётся прежним.
- При verdict=REVISE обязателен Fix Plan (см. `review.fix_plan.json`).
- Review **не** расширяет scope. Любая новая работа → `AIDD:OUT_OF_SCOPE_BACKLOG` и `Status: WARN` (или новый work_item в tasklist). `FORBIDDEN` остаётся BLOCKED.
- Fresh context: каждый шаг опирается на pack + ссылки, без “пересказа” больших документов.
- Loop-mode тесты: implement не запускает тесты по умолчанию; нужен `AIDD_LOOP_TESTS=1` или `AIDD_TEST_FORCE=1`. Review тесты не запускает.
- Loop-gating опирается на `stage_result`; отсутствие файла = `BLOCKED`.
- `stage_result` пишется всегда, даже при раннем `BLOCKED` (fail-fast).

## Automation notes
- Loop pack: `aidd/reports/loops/<ticket>/<scope_key>.loop.pack.md`.
- Review pack: `aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md` (`schema: aidd.review_pack.v2`).
- Если review pack старее review report (`review_pack_stale`) — пересоберите pack (или перезапустите review). При наличии loop‑pack/`active_work_item` review‑report авто‑синхронизирует pack.
- Fix Plan (REVISE): `aidd/reports/loops/<ticket>/<scope_key>/review.fix_plan.json`.
- Stage result (loop‑gating): `aidd/reports/loops/<ticket>/<scope_key>/stage.<stage>.result.json`.
- QA stage_result ticket‑scoped: `aidd/reports/loops/<ticket>/<ticket>/stage.qa.result.json`.
- Tests log: `aidd/reports/tests/<ticket>/<scope_key>.jsonl` (skipped → `reason_code` + `reason`).
- CLI logs: `aidd/reports/loops/<ticket>/cli.loop-run.<ts>.log`, `aidd/reports/loops/<ticket>/cli.loop-step.<ts>.log`.
- Config: `aidd/config/gates.json` → `review_pack_v2_required` (warn by default; block when enabled).
- Машинный вывод review pack: `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh --format json`.

## CLI (manual → loop-step → loop-run)
- Manual: `/feature-dev-aidd:implement <ticket>` → `/feature-dev-aidd:review <ticket>`.
- Bash loop: `${CLAUDE_PLUGIN_ROOT}/tools/loop-step.sh --ticket <ticket>` (fresh sessions).
- One-shot: `${CLAUDE_PLUGIN_ROOT}/tools/loop-run.sh --ticket <ticket> --max-iterations 5`.
- Runner по умолчанию: `claude` с вызовом в виде `-p "/feature-dev-aidd:<cmd> <ticket>"` (fresh context). Флаг `--no-session-persistence` используется только если поддерживается CLI.
- Repair from QA (explicit):
  - `--from-qa [manual|auto]` (alias `--repair-from-qa`) разрешён только при `.active_stage=qa` и `stage.qa.result=blocked`.
  - `--work-item-key iteration_id=M3` — явный выбор work_item (приоритет).
  - `--select-qa-handoff` — авто‑выбор единственного blocking QA handoff кандидата.
  - Auto‑mode: `aidd/config/gates.json` → `loop.auto_repair_from_qa=true` (только при 1 кандидате).

## Ralph loop vs AIDD loop-mode
- Ralph plugin использует stop-hook в той же сессии (completion promise).
- AIDD loop-mode использует fresh sessions (runner `claude` + `-p "/feature-dev-aidd:<cmd> <ticket>"`).
- Для max-iterations используйте формат с пробелом: `--max-iterations 5` (без `=`).
