# ast-grep rules: jvm

Place rules for JVM stacks here (Java/Kotlin/Spring/etc.).
Project-specific patterns belong in `../custom`.

## Basic principles
- Prefer stable annotations/types (e.g., controllers, tests, security).
- Avoid project-specific class names; keep them in `../custom`.
- Keep packs focused to limit JSONL output size.
- Use clear rule ids/messages; add tags for routing in packs.
