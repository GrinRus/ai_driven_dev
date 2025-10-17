---
description: "Ревью PRD и фиксация статуса готовности"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(python3 scripts/prd-review-agent.py:*)
---
1) Подготовь контекст: `docs/prd/$1.prd.md`, `docs/plan/$1.md`, связанные ADR/таски.
2) Вызови саб-агента **prd-reviewer**. Передай ему выявленные риски, уточнения и критерии, которые нужно проверить.
3) Обнови раздел `## PRD Review` в `docs/prd/$1.prd.md`: выстави `Status: approved|blocked|pending`, добавь summary, findings и action items (чеклист).
4) Перенеси блокирующие action items в `docs/tasklist/$1.md`, назначь владельцев и сроки закрытия.
5) Зафиксируй результат в логах:
!bash -lc 'python3 scripts/prd-review-agent.py --slug "$1" --report "reports/prd/$1.json" --emit-text'
