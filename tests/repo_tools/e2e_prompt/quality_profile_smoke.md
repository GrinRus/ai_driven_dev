Задача: **быстрый quality health-check AIDD e2e flow (TST-002, smoke)**.

Роль: ты — один quality-аудитор-агент. Выполни smoke execution через canonical base prompt и сделай только облегчённую quality-проверку артефактов.

## 0) Базовый prompt и приоритет

Обязательно прочитай:
- `$PLUGIN_DIR/docs/e2e/aidd_test_flow_prompt_ralph_script.txt`

Наследование:
- base prompt = execution spine;
- этот prompt добавляет quality-step после inherited шага 8;
- post-run write-safety (step 99) выполняется после quality-step.

## 1) Переменные

- `BASE_PROMPT=$PLUGIN_DIR/docs/e2e/aidd_test_flow_prompt_ralph_script.txt`
- `BACKLOG_PATH=$PLUGIN_DIR/docs/backlog.md`
- `PROFILE=smoke`
- `WAVE_WRITE_MODE=disabled`
- `BACKLOG_SCOPE=aidd-only`
- `QUALITY_GATE_POLICY=strict`
- `QUALITY_TOP_FINDINGS_LIMIT=<int>` (default: `8`)
- `QUALITY_FINAL_MARKER=QUALITY_AUDIT_COMPLETE`

## 2) Режим smoke

- Выполнить inherited smoke flow из base prompt.
- После inherited шага 8 выполнить `step 9` в `artifact-lite` режиме.
- `wave_created` всегда `0`.
- В `BACKLOG_PATH` не писать.

## 3) Дополнительные правила smoke quality

- findings всё равно классифицировать на:
  - `systemic_aidd_gap`
  - `product_output_gap`
  - `env_or_runner_gap`
- для smoke не делать deep code review;
- использовать только evidence из inherited artifacts/logs;
- если final feature state не достигнут, `overall_quality_gate=FAIL`.

## 4) MUST-READ

{{MUST_READ_MANIFEST}}

## 5) Выполнение inherited flow

1. Прочитай `BASE_PROMPT`.
2. Выполни inherited smoke шаги по base prompt.
3. Не завершай run после шага 8.
4. Выполни шаг 9 (quality-lite).
5. Затем выполни step 99 base prompt.

## 6) Шаг 9 (Quality-lite)

Сформируй:
- `AUDIT_DIR/09_quality_sources.txt`
- `AUDIT_DIR/09_final_state_check.txt`
- `AUDIT_DIR/09_artifact_scorecard.json`
- `AUDIT_DIR/09_quality_findings.md`
- `AUDIT_DIR/09_quality_findings.json`
- `AUDIT_DIR/09_user_improvement_plan.md`
- `AUDIT_DIR/09_quality_gate.txt`

Smoke-specific contract:
- `code_quality_gate=NOT_RUN` допустим;
- `wave_created=0` обязательно;
- `wave_id=-` обязательно;
- `backlog_candidates` можно считать, но backlog write запрещён.

`09_quality_gate.txt` должен включать:
- `feature_final_state=<REACHED|NOT_REACHED>`
- `code_quality_gate=<NOT_RUN|PASS|WARN|FAIL>`
- `artifact_quality_gate=<PASS|WARN|FAIL>`
- `systemic_aidd_findings=<int>`
- `product_output_findings=<int>`
- `env_or_runner_findings=<int>`
- `wave_created=0`
- `wave_id=-`
- `overall_quality_gate=<PASS|WARN|FAIL>`
- `reason_code=<->`

## 7) Override для шага 99

Write-safety в smoke:
- plugin repo write для quality-аудита запрещён;
- `BACKLOG_PATH` менять нельзя;
- любой plugin delta -> `FAIL(plugin_write_safety_violation)`.

Сохрани:
- `AUDIT_DIR/99_plugin_allowed_delta.txt`

`99_plugin_allowed_delta.txt`:
- `allowed_plugin_paths=-`
- `wave_created=0`
- `unexpected_plugin_delta=<0|1>`
- `classification=<PASS|FAIL>`

## 8) Финальный отчёт и marker

Вывести:
- inherited step matrix;
- quality-lite matrix (`final_state`, `artifact_quality_gate`, `overall_quality_gate`);
- top systemic/product findings;
- пути к ключевым `09_*` артефактам.

Финальные machine-friendly строки (dual marker policy):
- `QUALITY_AUDIT_COMPLETE <TICKET> status=<PASS|WARN|FAIL> wave=<none> feature_final_state=<REACHED|NOT_REACHED>`
- `AUDIT_COMPLETE <TICKET>`
