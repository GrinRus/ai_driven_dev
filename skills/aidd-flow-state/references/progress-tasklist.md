# Progress and Tasklist

- Run `progress_cli.py` to enforce checkbox/progress contract before allowing loop continuation.
- Use `tasklist_check.py --fix` for deterministic normalization only when fix mode is explicitly required.
- Keep progress updates append-only and linked to concrete artifacts.
- Treat malformed tasklist/progress records as blocking contract errors.
