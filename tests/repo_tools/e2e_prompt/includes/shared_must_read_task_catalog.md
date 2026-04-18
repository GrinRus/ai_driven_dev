## 7) MUST-READ

{{MUST_READ_MANIFEST}}

## 8) Каталог задач для шага 3 (выбрать ровно одну)

Контекст анализа:
- `PROJECT_DIR/README.md`
- `PROJECT_DIR/docs/backlog.md`
- `PROJECT_DIR/backend/src/main/java/**/controller/*Controller.java`
- `PROJECT_DIR/frontend/src/pages/*.tsx`
- `PROJECT_DIR/frontend/src/lib/apiClient.ts`

### FS-GA-01 (L) GitHub Analysis Flow: production-ready UX + canonical payload
- Backend scope:
  - Оркестрация `github-analysis-flow` с шагами `fetch_metadata -> fetch_tree -> analysis -> recommendations`.
  - Typed payload/DTO (`analysisStatus`, `retries`, `recommendationBlocks`, `actions`, `stepProgress`) + OpenAPI sync.
  - Идемпотентное хранение результатов анализа.
- Frontend scope:
  - MCP panel блок GitHub Analysis (URL/ref/PR, режим, валидация).
  - Прогресс шагов, ретраи/ошибки, карточка результата.
  - Review actions: `comment`, `approve`, `request changes`.
- Acceptance criteria:
  - Запуск из UI создаёт flow session и даёт прогресс без ручного рефреша.
  - Результат содержит canonical payload и доступен из истории.
  - Типы консистентны между backend DTO и frontend client.

### FS-MP-02 (L) GitHub/GitLab parity для assisted coding flow
- Backend scope:
  - Provider-aware contract (`github|gitlab`) в registry/orchestrator/pipeline.
  - GitLab MCP stack и маршрутизация URL/MR.
  - Общие метрики/логи/fallback policy.
- Frontend scope:
  - Переключатель provider в UI/CLI.
  - Provider-specific ссылки и `workspace_git_state`.
  - Provider-aware cache/recovery.
- Acceptance criteria:
  - Один flow работает для GitHub и GitLab URL без ручной правки payload.
  - UI корректно показывает provider/ссылки/статусы.
  - Интеграционные тесты покрывают fetch -> state -> analysis.

### FS-RBAC-03 (M) Live RBAC enforcement + admin role operations
- Backend scope:
  - Усиление role enforcement на критичных API.
  - Audit trail для role operations и 403.
  - Стабилизация role guard/interceptor.
- Frontend scope:
  - Live обновление ролей в сессии.
  - Role guards для admin/flow controls.
  - Единая обработка 403.
- Acceptance criteria:
  - Изменения ролей видны без перезагрузки.
  - Backend consistently возвращает 403 без роли.
  - Admin roles audit соответствует действиям.

### FS-ID-04 (L) VK OAuth + Telegram Login Widget profile linking
- Backend scope:
  - `GET /auth/vk`, `POST /auth/vk/callback` (PKCE/state/device_id).
  - Refresh/revoke pipeline для VK tokens.
  - Telegram callback hash validation + anti-replay + profile attach.
- Frontend scope:
  - Link/unlink блок внешних провайдеров + Telegram widget.
  - Статусы линковки/ошибок/expiry.
  - Channel-specific UX подсказки.
- Acceptance criteria:
  - VK/Telegram linking end-to-end.
  - Backend валидирует подписи/state и пишет audit events.
  - E2E покрывает happy path + replay/expired/error.

### FS-GRAPH-05 (L) Code graph IDE navigation (outline + anchors + target path)
- Backend scope:
  - Расширение графа (`CONTAINS`, сигнатуры, docstring, visibility, anchors).
  - Улучшение `graph_neighbors`/`graph_path`/`definition`.
  - Кэш/метрики/fallback для graph queries.
- Frontend scope:
  - UI для outline/anchors/previews.
  - Отображение путей до `goalFqn` + relation filters.
  - Визуальная деградация в fallback mode.
- Acceptance criteria:
  - Из UI можно получить outline и перейти к символу по anchors.
  - Path queries возвращают цель по `targetHint`/`goalFqn`.
  - Метрики показывают latency/hit/miss/fallback reasons.

## 9) Пошаговый flow (для агента)

Логи до `aidd-init` сохраняй в:
- `RUN_TS=$(date -u +%Y%m%dT%H%M%SZ)`
- `AUDIT_DIR=$PROJECT_DIR/.aidd_audit/$TICKET/$RUN_TS`

### Шаг 0. Clean state
