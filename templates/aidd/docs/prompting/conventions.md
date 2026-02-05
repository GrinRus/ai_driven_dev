# Prompting Conventions (AIDD)

Канон выполнения и контракт вывода живут в skills (EN). Этот документ — краткий справочник для пользователей.

## Skill-first канон
- Core policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/SKILL.md`.
- Loop policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/SKILL.md`.
- Не дублируйте алгоритмы из skills в пользовательских документах.

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
