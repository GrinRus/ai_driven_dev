#!/usr/bin/env python3
"""CLI surface for append-only memory decision log writes."""

from __future__ import annotations

import argparse
import json


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare decision append request payload for memory log.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/decision_append.py --ticket DEMO-123\n"
            "\n"
            "Outputs:\n"
            "  - JSON status payload to stdout.\n"
            "\n"
            "Exit codes:\n"
            "  0: command executed successfully.\n"
            "  2: runtime surface placeholder (implemented in later Wave 101 tasks).\n"
        ),
    )
    parser.add_argument("--ticket", help="Ticket identifier.")
    parser.add_argument("--format", choices=("json", "text"), default="json", help="Output format.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = {
        "schema": "aidd.memory.command_stub.v1",
        "status": "not_implemented",
        "command": "decision_append",
        "ticket": (args.ticket or "").strip(),
        "reason_code": "memory_runtime_not_implemented",
        "next_action": "Implement W101-4 decision append runtime behavior.",
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            "status=not_implemented "
            "command=decision_append "
            "reason_code=memory_runtime_not_implemented"
        )
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
