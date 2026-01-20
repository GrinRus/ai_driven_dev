# ast-grep rules: common

Add cross-stack rules here (logging, TODO markers, etc.).
For project-specific patterns, add a `custom` rule pack in `../custom`.

## Basic principles
- Keep rules generic and reusable; avoid project-specific identifiers.
- Prefer stable APIs, annotations, and types over string literals.
- Keep packs small and focused; split by concern if they grow.
- Use clear rule ids/messages; add tags when it helps filtering.
- Avoid overly broad matches that would flood JSONL output.
