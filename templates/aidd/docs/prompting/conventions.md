# Prompting Conventions (AIDD)

Канон выполнения и контракт вывода живут в skills (EN). Этот документ — краткий справочник для пользователей.

## Skill-first канон
- Core policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/SKILL.md`.
- Loop policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/SKILL.md`.
- Не дублируйте алгоритмы из skills в пользовательских документах.

## Stage-local scripts
- Stage‑локальные скрипты живут в `skills/<stage>/scripts/` (wrappers + stage‑only tooling).
- Shared tooling остаётся в `tools/` (hooks/CI используют только `tools/*` или shims).

## Wrapper output policy
- Логи wrapper’ов: `aidd/reports/logs/<stage>/<ticket>/<scope_key>/wrapper.<name>.<timestamp>.log`.
- Stdout ≤ 200 lines или ≤ 50KB; stderr ≤ 50 lines.
- Большие выводы пишите в `aidd/reports/**`, в stdout только путь + короткое summary.

## Evidence read policy (pack-first, rolling)
- Pack-first и read-budget описаны в `skills/aidd-core`.
- Primary research evidence: `aidd/reports/research/<ticket>-rlm.pack.json`.
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.

## AIDD:READ_LOG (обязателен)
- Формат и требования см. `skills/aidd-core` (указывайте только реально прочитанные packs/excerpts).

## Output‑контракт
Полный формат см. `skills/aidd-core`.

## DocOps
Полная политика см. `skills/aidd-core`.

## Loop discipline
Полная дисциплина см. `skills/aidd-loop`.
