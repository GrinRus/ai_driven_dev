## Shared rules core

- First run for each stage uses only `ticket` except `idea-new`, which uses `ticket + IDEA_NOTE`.
- Do not read secrets or print raw secret values.
- Use Python runtime surfaces only: `skills/*/runtime/*.py`.
- For `claude -p` stage commands, add `--verbose --output-format stream-json` in stream mode and `--plugin-dir "$PLUGIN_DIR"` always.
- Run plugin-load healthcheck before stage sequence; `Unknown skill: feature-dev-aidd:*` is `ENV_BLOCKER(plugin_not_loaded)`.
- Treat `refusing to use plugin repository as workspace root` as `ENV_MISCONFIG(cwd_wrong)`.
- Liveness in stream mode uses both main log and stream files; fallback discovery writes `AUDIT_DIR/<step>_stream_paths_run<N>.txt`.
