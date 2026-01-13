#!/usr/bin/env python3
from __future__ import annotations

import sys


def main() -> int:
    try:
        from claude_workflow_cli.tools import tasklist_check
    except Exception as exc:
        print(f"[tasklist-check] FAIL: {exc}", file=sys.stderr)
        return 2
    return tasklist_check.main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
