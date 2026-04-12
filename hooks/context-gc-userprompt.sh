#!/usr/bin/env python3
from __future__ import annotations

from hook_entrypoint import run_hook_module


def main() -> int:
    return run_hook_module(
        hook_prefix="[context-gc-userprompt]",
        module_import_path="hooks.context_gc.userprompt_guard",
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
