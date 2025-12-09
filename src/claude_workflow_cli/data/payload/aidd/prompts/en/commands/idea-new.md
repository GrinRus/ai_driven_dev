---
description: "Feature initiation: capture idea → clarifications → PRD"
argument-hint: "<TICKET> [slug-hint]"
lang: en
prompt_version: 1.2.0
source_version: 1.2.0
allowed-tools: Read,Edit,Write,Grep,Glob,Bash(python3 tools/set_active_feature.py:*),Bash(claude-workflow analyst:*),Bash(claude-workflow analyst-check:*),Bash(claude-workflow research:*)
model: inherit
disable-model-invocation: false
---

## Context
`/idea-new`registers the active feature, scaffolds a PRD, and hands off to the analyst. Research runs only when context is thin (manual `/researcher` or `claude-workflow research`). It enforces the agent-first flow: analysts and researchers mine the slug-hint (`aidd/docs/.active_feature`),`aidd/docs/research/*.md`,`reports/research/*.json`, and run allowed CLI commands before escalating to the user. The analyst can trigger an extra research pass if context is thin (refining paths/keywords).

## Input Artifacts
- Slug-hint / user notes (argument`[slug-hint]`and`rg &lt;ticket&gt; aidd/docs/**`).
-`aidd/docs/prd.template.md`— used for scaffolding.
-`aidd/docs/research/&lt;ticket&gt;.md`,`reports/research/&lt;ticket&gt;-(context|targets).json`— created/updated automatically; when missing,`aidd/docs/templates/research-summary.md`is used as baseline.
- User-provided`slug-hint`from`/idea-new &lt;ticket&gt; [slug-hint]`— treat it as the primary raw idea; record it in PRD (overview/context) and backlog notes if applicable.

## When to Run
- At the very beginning of a feature lifecycle.
- Rerun only if you intentionally reset the active ticket (use`--force`cautiously).

## Automation & Hooks
-`python3 tools/set_active_feature.py &lt;ticket&gt; [--slug-note ...]`writes`aidd/docs/.active_ticket`,`.active_feature`, and scaffolds`aidd/docs/prd/&lt;ticket&gt;.prd.md`(Status: draft).
-`claude-workflow analyst --ticket &lt;ticket&gt; --auto`launches the analyst; it re-reads slug-hint and artifacts, and requests research only if context is missing.
-`claude-workflow research --ticket &lt;ticket&gt; --auto`is used on demand (when the analyst spots gaps). Extra`--paths/--keywords/--note`flags narrow the scope only when necessary.
-`claude-workflow analyst-check --ticket &lt;ticket&gt;`ensures the dialog block is structured and`Status`is not`draft`.

## What is Edited
-`aidd/docs/.active_ticket`,`aidd/docs/.active_feature`.
-`aidd/docs/prd/&lt;ticket&gt;.prd.md`— filled per template, status updated from draft to READY/BLOCKED.
-`aidd/docs/research/&lt;ticket&gt;.md`— created/updated (baseline recorded when no context is found).
- Auto-generated`reports/research/&lt;ticket&gt;-(context|targets).json`.

## Step-by-step Plan
1. Run`python3 tools/set_active_feature.py "$1" [--slug-note "$2"]`— it updates`aidd/docs/.active_ticket`,`.active_feature`(capturing the slug-hint as the raw user request), and scaffolds the PRD (use`--force`only after confirming you may overwrite the current ticket).
2. Launch the **analyst** agent automatically:`claude-workflow analyst --ticket "$1" --auto`. The agent reads slug-hint (`aidd/docs/.active_feature`), searches for ticket mentions (`rg`), checks existing artifacts, and logs questions.
3. If context is missing (no or stale `aidd/docs/research/$1.md`), trigger research: run `/researcher $1` or`claude-workflow research --ticket "$1" --auto [--paths ... --keywords ...]`. If the CLI reports`0 matches`, expand`aidd/docs/templates/research-summary.md`into`aidd/docs/research/$1.md`, add the “Context empty, baseline required” note, and list all commands/paths that returned nothing.
4. After research, return to the analyst (rerun`claude-workflow analyst --ticket "$1" --auto` if needed) and update the PRD: filled sections,`## Диалог analyst`, links to research/reports; set READY only when context is sufficient (`Status: reviewed` or baseline project).
5. Run`claude-workflow analyst-check --ticket "$1"`and fix any reported mismatches before continuing.
6. Optionally apply preset`feature-prd`or attach notes via`--note @file.md`to pre-populate research/PRD context.

## Fail-fast & Questions
- Missing ticket or slug-hint — stop and request it.
- Do not overwrite a filled PRD unless the user confirms (`--force`).
- If`claude-workflow research --auto`still lacks context after scanning, describe the commands/paths you already used, kick off another research pass with refined scope if needed, and only then ask the user for extra`--paths/--keywords`or`--note` or to run `/researcher`.

## Expected Output
- Active ticket/slug set, PRD scaffolded + filled, Researcher report created/updated, status READY/BLOCKED reflecting dialog state.
- User understands remaining questions if BLOCKED.

## CLI Examples
-`/idea-new ABC-123 checkout-demo`
-`/idea-new ABC-123 --paths src/app --keywords "checkout,pay" --slug-note checkout-demo`
