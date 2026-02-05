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
- Указывай только реально прочитанные packs/excerpts (1–3 файла).
- Для full-read — кратко зафиксируй причину.

## Output‑контракт (summary)
- `Status`, `Work item key`, `Artifacts updated`, `Tests`, `Blockers/Handoff`, `Next actions`, `AIDD:READ_LOG`.
- Полный формат см. `skills/aidd-core`.

## DocOps (summary)
- Loop stages: не редактировать `aidd/docs/tasklist/**` и `aidd/reports/context/**` (только intents).
- Planning stages: редактирование допустимо; структурные секции — DocOps‑managed.
- Полная политика см. `skills/aidd-core`.

## Loop discipline (summary)
- Loop pack first, no questions in loop-mode, scope guard.
- Полная дисциплина см. `skills/aidd-loop`.
