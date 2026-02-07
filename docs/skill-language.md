# Skill Language Policy (SoT)

## Scope
- `skills/aidd-core/**`, `skills/aidd-loop/**`, and `skills/<stage>/**` are **English-only**.
- User-facing templates and READMEs may be in Russian, but must not duplicate executable algorithms that live in skills.

## Enforcement reference (W91-7)
- CI/lint checks reference this file to enforce the EN-only skills policy.

## EN skills writing checklist
- Write in English only (no Cyrillic characters).
- Use imperative, concise sentences.
- Keep the entrypoint short; push details into core/loop or references.
- Link to `skills/aidd-core` / `skills/aidd-loop` instead of copying canon.
- Keep steps numbered and action-focused.
- Avoid long prose, redundancy, and large inline examples.
