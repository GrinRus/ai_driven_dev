# RLM File Node Prompt (EN)

You are generating a single RLM node for one source file.
Return strict JSON only (no markdown, no comments).

Required fields:
- schema, schema_version, node_kind="file"
- id (== file_id), file_id, path, rev_sha, lang, prompt_version
- summary (short, 2-4 sentences)
- public_symbols (array of strings)
- key_calls (array of strings)
- framework_roles (array of strings: web|controller|service|repo|job|config|infra)
- test_hooks (array of strings)
- risks (array of strings)
- verification, missing_tokens (leave empty here; verifier will fill)

Rules:
- Use empty arrays when nothing is found.
- Do not invent symbols not present in the file.
- Keep summary concise and factual.
