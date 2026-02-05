# AGENTS

Единая точка входа для runtime‑агентов AIDD (workspace). Dev‑гайд репозитория: `AGENTS.md` в корне плагина.

## Skill-first канон
- Core policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-core/SKILL.md`.
- Loop policy: `${CLAUDE_PLUGIN_ROOT}/skills/aidd-loop/SKILL.md`.
- Этот документ — пользовательский обзор; не дублируйте алгоритмы из skills.

## Базовые правила
- Все артефакты находятся в `aidd/**` (paths от root).
- Саб‑агенты не меняют `aidd/docs/.active.json`.
- Pack‑first/read‑budget и output‑контракт — см. `skills/aidd-core`.

## Evidence read policy (summary)
- Primary evidence (research): `aidd/reports/research/<ticket>-rlm.pack.json`.
- Slice on demand: `${CLAUDE_PLUGIN_ROOT}/tools/rlm-slice.sh --ticket <ticket> --query "<token>"`.

## Question format (from aidd-core)
```
Question N (Blocker|Clarification): ...
Why: ...
Options: A) ... B) ...
Default: ...
```

## Ответы пользователя
Ответы давайте в рамках той же команды (без смены стадии). Если ответы приходят в чате, попросите блок:
```
## AIDD:ANSWERS
- Answer 1: ...
- Answer 2: ...
```
