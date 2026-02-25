#!/usr/bin/env python3
"""CLI surface for targeted memory slice retrieval."""

from __future__ import annotations

import argparse
import json


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare targeted memory slice request payload.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 ${CLAUDE_PLUGIN_ROOT}/skills/aidd-memory/runtime/memory_slice.py --ticket DEMO-123\n"
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
    parser.add_argument("--query", help="Optional retrieval query.")
    parser.add_argument("--format", choices=("json", "text"), default="json", help="Output format.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = {
        "schema": "aidd.memory.command_stub.v1",
        "status": "not_implemented",
        "command": "memory_slice",
        "ticket": (args.ticket or "").strip(),
        "query": (args.query or "").strip(),
        "reason_code": "memory_runtime_not_implemented",
        "next_action": "Implement W101-5 slice runtime behavior.",
    }
    if args.format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            "status=not_implemented "
            "command=memory_slice "
            "reason_code=memory_runtime_not_implemented"
        )
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
