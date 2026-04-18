#!/usr/bin/env python3
from __future__ import annotations

from hook_entrypoint import run_hook_module


def main() -> int:
    return run_hook_module(
        hook_prefix="[gate-workflow]",
        module_import_path="hooks.gate_workflow",
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
