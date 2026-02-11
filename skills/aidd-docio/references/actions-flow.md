# Actions Flow

- Validate actions payloads with `actions_validate.py` before postflight.
- Apply actions with `actions_apply.py` only after preflight artifacts are present.
- Record apply logs under `aidd/reports/actions/<ticket>/<scope_key>/*.apply.jsonl`.
- Treat unknown action types or schema mismatches as blocking contract errors.
