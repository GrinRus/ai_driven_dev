import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from aidd_runtime import cli


def test_cli_parses_new_subcommands():
    parser = cli.build_parser()
    parser.parse_args(["prd-review", "--target", ".", "--ticket", "DEMO-1"])
    parser.parse_args(["plan-review-gate", "--ticket", "DEMO-1"])
    parser.parse_args(["prd-review-gate", "--ticket", "DEMO-1"])
    parser.parse_args(["tasklist-check", "--target", ".", "--ticket", "DEMO-1"])
    parser.parse_args(["researcher-context"])
    parser.parse_args(["context-gc", "precompact"])
    parser.parse_args(["identifiers", "--target", ".", "--json"])
    parser.parse_args(["context-pack", "--agent", "implementer"])
    parser.parse_args(["tests-log", "--status", "pass"])
