#!/usr/bin/env python3
"""Switch commit mode inside config/conventions.json and print the result."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

CONFIG_PATH = Path("config/conventions.json")
VALID_MODES = ("ticket-prefix", "conventional", "mixed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--commit-mode",
        choices=VALID_MODES,
        required=True,
        help="Desired commit mode preset.",
    )
    args = parser.parse_args()

    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    data.setdefault("commit", {})["mode"] = args.commit_mode
    CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.commit_mode)


if __name__ == "__main__":
    main()
