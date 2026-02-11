#!/usr/bin/env python3
"""Deprecated: legacy researcher context pack helpers.

Research context artifacts were removed in Wave 90. Keep this module as a
compatibility stub so accidental imports fail with a clear message.
"""

from __future__ import annotations


def _deprecated(*_args, **_kwargs):
    raise RuntimeError(
        "researcher_context_pack.py is deprecated; use RLM artifacts "
        "(rlm-targets/manifest/worklist/pack)."
    )


write_targets = _deprecated
collect_context = _deprecated
write_context = _deprecated
build_project_profile = _deprecated
detect_src_layers = _deprecated
detect_tests = _deprecated
is_excluded_test_path = _deprecated
detect_configs = _deprecated
detect_logging_artifacts = _deprecated
baseline_recommendations = _deprecated
