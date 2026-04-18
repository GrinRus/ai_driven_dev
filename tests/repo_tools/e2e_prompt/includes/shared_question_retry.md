## 6) Универсальный шаблон обработки вопросов (обязательно)

Используй этот шаблон для всех stage-команд:

1. Запусти первую попытку по R0/R0.1.
2. Если stage задаёт вопросы/возвращает BLOCK из-за отсутствия ответов:
   - retry-триггер разрешён только по текущему stage-return;
   - для `idea-new` и `plan-new` retry-триггер также валиден, если top-level `success|WARN` явно требует закрыть `Q*`;
   - не считать trigger-ом `Q*`/`AIDD:ANSWERS`/`Question` внутри вложенных артефактов;
   - количество `Q<N>` в retry определяется только актуальным top-level stage-return последнего run; примеры payload не фиксируют число вопросов;
   - извлеки вопросы в `AUDIT_DIR/<step>_questions.txt`;
   - дополнительно сохрани `AUDIT_DIR/<step>_questions_raw.txt` и `AUDIT_DIR/<step>_questions_normalized.txt`;
   - если source содержит `TBD`/пустые значения в `AIDD:ANSWERS`, нормализуй в `Q<N>=<token>` или `Q<N>="короткий текст"`;
   - выполни **ровно один** retry;
   - если для части актуальных `Q<N>` нет сопоставленных ответов, фиксируй `question_retry_incomplete` и не публикуй partial compact payload как completed retry;
   - рекомендуемый шаблон: `AIDD:ANSWERS Q1=C; Q2=B; Q3=C; Q4=A; Q5=C`.
3. Retry формат:
   - `idea-new`: `ticket + IDEA_NOTE + AIDD:ANSWERS`;
   - остальные stage: `ticket + AIDD:ANSWERS`;
   - в CLI передавай только нормализованный one-line payload.
4. Если после retry всё ещё BLOCKED:
   - зафиксируй `WARN`/`FAIL` с причиной;
   - продолжай по сценарию, где это возможно.
5. Если причина BLOCKED связана с unresolved `Q*` или `PRD Status != READY`:
   - сначала пройди `/feature-dev-aidd:review-spec <ticket>`;
   - затем findings-sync cycle при необходимости;
   - если после findings-sync `Status != READY`, классифицируй как `NOT VERIFIED (findings_sync_not_converged)` + `prompt-flow gap`.
6. Если stage-return содержит `Unknown skill`, классифицировать как `ENV_BLOCKER(plugin_not_loaded)` и остановить аудит.
7. Если stage-return уводит в ручной preflight или ручную запись `stage.*.result.json`, классифицировать как `prompt-flow drift (non-canonical stage orchestration)` и manual path не выполнять.
8. Если nested runtime-команда использует non-canonical путь `python3 skills/...`, классифицировать как `prompt-flow drift (runtime_cli_contract_mismatch)`.

Примечание: вопросы — часть happy path, а не исключение.
