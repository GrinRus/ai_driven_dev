# ast-grep rules: mobile

Place rules for mobile stacks here (Swift/Kotlin Android, etc.).
Project-specific patterns belong in `../custom`.

## Basic principles
- Prefer stable SDK/framework types and annotations.
- Keep rules narrow to avoid large match volumes.
- Avoid app-specific identifiers; use `../custom` for those.
- Use clear rule ids/messages; add tags for routing in packs.
