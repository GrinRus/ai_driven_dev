---
description: "Создать/обновить OpenAPI контракт для фичи"
argument-hint: "<slug>"
allowed-tools: Read,Edit,Write,Grep,Glob
---
Создай каталог `docs/api/` (если нет). Вызови саб-агента **api-designer** для формирования/обновления `docs/api/$1.yaml` на основе `docs/prd/$1.prd.md`.
Если контракт уже существует — корректно смержи изменения.
