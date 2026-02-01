# Loop Mode (Ralph)

Loop = 1 work_item → implement → review → (revise)* → ship.

## Правила
- Начинай каждую итерацию с `loop_pack` (тонкий контекст). Не вставляй большие куски логов/диффов — только ссылки на `aidd/reports/**`.
- Review **не** расширяет scope. Любая новая работа → `AIDD:OUT_OF_SCOPE_BACKLOG` и `Status: BLOCKED` (или новый work_item в tasklist).
- Fresh context: каждый шаг опирается на pack + ссылки, без “пересказа” больших документов.
- Loop-mode тесты: implement не запускает тесты по умолчанию; нужен `AIDD_LOOP_TESTS=1` или `AIDD_TEST_FORCE=1`. Review тесты не запускает.
- Loop-gating опирается на `stage_result`; отсутствие файла = `BLOCKED`.

## Automation notes
- Loop pack: `aidd/reports/loops/<ticket>/<scope_key>.loop.pack.md`.
- Review pack: `aidd/reports/loops/<ticket>/<scope_key>/review.latest.pack.md` (`schema: aidd.review_pack.v2`).
- Stage result (loop‑gating): `aidd/reports/loops/<ticket>/<scope_key>/stage.<stage>.result.json`.
- Config: `aidd/config/gates.json` → `review_pack_v2_required` (warn by default; block when enabled).
- Машинный вывод review pack: `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh --format json`.

## CLI (manual → loop-step → loop-run)
- Manual: `/feature-dev-aidd:implement <ticket>` → `/feature-dev-aidd:review <ticket>`.
- Bash loop: `${CLAUDE_PLUGIN_ROOT}/tools/loop-step.sh --ticket <ticket>` (fresh sessions).
- One-shot: `${CLAUDE_PLUGIN_ROOT}/tools/loop-run.sh --ticket <ticket> --max-iterations 5`.
- Runner по умолчанию: `claude -p` (fresh context). Флаг `--no-session-persistence` используется только если поддерживается CLI.

## Ralph loop vs AIDD loop-mode
- Ralph plugin использует stop-hook в той же сессии (completion promise).
- AIDD loop-mode использует fresh sessions (runner `claude -p`).
- Для max-iterations используйте формат с пробелом: `--max-iterations 5` (без `=`).
