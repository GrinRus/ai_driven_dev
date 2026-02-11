# Stage Lifecycle

- Set active feature/stage via `set_active_feature.py` and `set_active_stage.py` before stage operations.
- Run `stage_result.py` to persist the stage outcome and handoff semantics.
- Run `status_summary.py` after stage result is written to keep status output single-source.
- Use `prd_check.py` and `tasks_derive.py` as gate/derivation tools, not ad-hoc text edits.
