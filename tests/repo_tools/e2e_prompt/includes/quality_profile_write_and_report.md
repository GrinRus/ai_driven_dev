### Шаг 99. Post-run write-safety (quality override)

Сделать:
- `99_plugin_git_status_after.txt`
- `99_project_git_status_after.txt`
- `99_plugin_git_status_diff.txt`
- `99_plugin_new_paths_stat.txt`
- `99_cleanup_policy.txt`
- `99_workspace_layout_check.txt`
- `99_plugin_allowed_delta.txt`
- `99_backlog_wave_integrity_check.txt`
- удалить временный pre-status файл: `rm -f "/tmp/00_git_status_before.${TICKET}.${RUN_TS}.txt"`.

`99_plugin_allowed_delta.txt` должен содержать:
- `allowed_plugin_paths=$BACKLOG_PATH`
- `wave_created=<0|1>`
- `unexpected_plugin_delta=<0|1>`
- `classification=<...>`

`99_backlog_wave_integrity_check.txt` должен содержать:
- `wave_created=<0|1>`
- `wave_id=<WNNN|->`
- `items_count=<int>`
- `all_item_ids_match_wave=0|1`
- `required_fields_present=0|1`
- `classification=<PASS|WARN|FAIL>`

Write-safety classification override:
- `PASS(no_plugin_delta)`: plugin repo delta отсутствует.
- `PASS(backlog_wave_written)`: единственный plugin delta = `BACKLOG_PATH`, wave integrity check = PASS.
- `WARN(backlog_wave_malformed)`: delta только в `BACKLOG_PATH`, но wave format/integrity частично некорректны.
- `WARN(backlog_expected_but_missing)`: systemic findings были, но wave не записана.
- `FAIL(plugin_write_safety_violation)`: изменён любой plugin path кроме `BACKLOG_PATH`.
- `FAIL(backlog_write_unexpected_delta)`: вместе с `BACKLOG_PATH` изменены другие plugin paths.

## 10) Финальный отчёт в чат

Обязательно:
- Таблица inherited steps `PASS/WARN/FAIL` для шагов `0..8` и `99`.
- Quality matrix:
  - `feature_final_state`
  - `code_quality_gate`
  - `artifact_quality_gate`
  - `overall_quality_gate`
- Inherited flow integrity highlights (внутри текущего отчёта, без отдельного evaluation раздела):
  - test contract SoT (`aidd/config/gates.json`) + policy-source scan (`01_gates_snapshot.json`, `01_test_policy_source_scan.txt`)
  - reason-code precedence (`project_contract_missing|tests_cwd_mismatch` как primary; `no_top_level_result` как secondary symptom)
  - runtime path hygiene (python-only runtime surfaces + отсутствие runtime decision dependency на `.claude/settings.json`)
  - topology/cwd evidence (`PRE-RUN invariant` + launcher precheck)
- Выбранная задача: `task_id`, `title`, `generated_slug_hint`, rationale.
- Что `NOT VERIFIED` и почему.
- Top `systemic_aidd_gap`.
- Top `product_output_gap`.
- `wave_id` и item ids, если wave создана.
- Что именно предложено пользователю как дальнейшие доработки.
- Пути к key artifacts в `AUDIT_DIR`.

Последняя строка:
`QUALITY_AUDIT_COMPLETE TST-002 status=<PASS|WARN|FAIL> wave=<WNNN|none> feature_final_state=<REACHED|NOT_REACHED>`
