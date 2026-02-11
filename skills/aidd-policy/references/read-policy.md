# Read Policy (Pack-First)

1. Start from pack artifacts (`*.pack.json`, `*.pack.md`) and targeted slices.
2. Use focused evidence reads (`rlm_slice.py`, section markers) before opening full files.
3. Open full files only if slice evidence is insufficient for the decision.
4. Keep `AIDD:READ_LOG` short and reference report paths instead of copying large payloads.

Recommended order:
- `aidd/reports/research/<ticket>-rlm.pack.json`
- `aidd/reports/loops/<ticket>/<scope_key>.loop.pack.md`
- `aidd/reports/context/<ticket>.pack.md`
- specific files/slices needed to resolve blockers
