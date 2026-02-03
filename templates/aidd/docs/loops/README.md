# Loop Mode (Ralph)

Loop = 1 work_item → implement → review → (revise)* → ship.

## Правила
- Начинай каждую итерацию с `loop_pack` (тонкий контекст). Не вставляй большие куски логов/диффов — только ссылки на `aidd/reports/**`.
- Review **не** расширяет scope. Любая новая работа → `AIDD:OUT_OF_SCOPE_BACKLOG` и `Status: BLOCKED` (или новый work_item в tasklist).
- Fresh context: каждый шаг опирается на pack + ссылки, без “пересказа” больших документов.
- Loop-mode тесты: implement не запускает тесты по умолчанию; нужен `AIDD_LOOP_TESTS=1` или `AIDD_TEST_FORCE=1`. Review тесты не запускает.

## Automation notes
- `review.latest.pack.md` содержит front‑matter `schema: aidd.review_pack.v1` и `verdict`.
- Машинный вывод: `${CLAUDE_PLUGIN_ROOT}/tools/review-pack.sh --format json`.

## CLI (manual → loop-step → loop-run)
- Manual: `/feature-dev-aidd:implement <ticket>` → `/feature-dev-aidd:review <ticket>`.
- Bash loop: `${CLAUDE_PLUGIN_ROOT}/tools/loop-step.sh --ticket <ticket>` (fresh sessions).
- One-shot: `${CLAUDE_PLUGIN_ROOT}/tools/loop-run.sh --ticket <ticket> --max-iterations 5`.
- Runner по умолчанию: `claude -p --no-session-persistence` (fresh context).

## Ralph loop vs AIDD loop-mode
- Ralph plugin использует stop-hook в той же сессии (completion promise).
- AIDD loop-mode использует fresh sessions (`claude -p --no-session-persistence`).
- Для max-iterations используйте формат с пробелом: `--max-iterations 5` (без `=`).
