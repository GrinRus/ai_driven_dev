# ast-grep rules: web

Place rules for JS/TS/UI stacks here (React/Vue/etc.).
Project-specific patterns belong in `../custom`.

## Basic principles
- Keep rules framework-agnostic where possible; prefer stable APIs.
- Avoid matching long string literals or build output files.
- Keep matches focused to reduce noise in JSONL results.
- Use clear rule ids/messages; add tags for routing in packs.
