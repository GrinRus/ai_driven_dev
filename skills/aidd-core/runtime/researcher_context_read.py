#!/usr/bin/env python3
"""Deprecated: legacy researcher context read helpers.

Research context artifacts were removed in Wave 90. Keep this module as a
compatibility stub so accidental imports fail with a clear message.
"""

from __future__ import annotations


def _deprecated(*_args, **_kwargs):
    raise RuntimeError(
        "researcher_context_read.py is deprecated; use RLM pack/slice via "
        "skills/aidd-rlm/runtime/* and researcher/runtime/research.py."
    )


scan_matches = _deprecated
iter_files = _deprecated
collect_deep_context = _deprecated
collect_code_index = _deprecated
iter_code_files = _deprecated
summarise_code_file = _deprecated
score_reuse_candidates = _deprecated
