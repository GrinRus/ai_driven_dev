# Skill Language Policy (SoT)

## Scope
- `skills/aidd-core/**` and `skills/aidd-loop/**` are **English-only**.
- Stage skills under `skills/<stage>/**` are currently **Russian (`lang: ru`)** for runtime compatibility with existing prompts and workflows.
- User-facing templates and READMEs may be in Russian, but must not duplicate executable algorithms that live in core loop skills.

## Transitional policy (Wave 94)
- The repository is in a transitional language mode:
  - core/loop skills: `lang: en` (required),
  - stage skills: `lang: ru` (allowed until dedicated migration wave).
- CI/lint checks must treat this split as canonical and must not fail on stage skill `lang: ru`.

## Enforcement reference
- CI/lint checks reference this file as language SoT.

## EN skills writing checklist
- Write in English only (no Cyrillic characters).
- Use imperative, concise sentences.
- Keep the entrypoint short; push details into core/loop or references.
- Link to `skills/aidd-core` / `skills/aidd-loop` instead of copying canon.
- Keep steps numbered and action-focused.
- Avoid long prose, redundancy, and large inline examples.
