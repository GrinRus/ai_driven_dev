# RLM Dir Node Prompt (EN, docs-only)

This prompt is a reference for how a directory node should look.
Dir nodes are generated deterministically from child file nodes (no LLM).

Required fields:
- schema, schema_version, node_kind="dir"
- id (== dir_id), dir_id, path
- children_file_ids (truncated list), children_count_total
- summary (short, derived from child nodes)
