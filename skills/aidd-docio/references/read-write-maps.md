# Read/Write Map Policy

- Validate `readmap.json` and `writemap.json` with `context_map_validate.py` before use.
- Use `context_expand.py` to add boundary entries with audit trail.
- Prefer explicit refs (`path#AIDD:SECTION`, `path@handoff:id`) for deterministic expansion.
- Keep loop-pack regeneration enabled for loop stages unless diagnostics require bypass.
