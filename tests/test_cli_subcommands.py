import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from claude_workflow_cli import cli


def test_cli_parses_new_subcommands():
    parser = cli.build_parser()
    parser.parse_args(["prd-review", "--target", ".", "--ticket", "DEMO-1"])
    parser.parse_args(["plan-review-gate", "--ticket", "DEMO-1"])
    parser.parse_args(["prd-review-gate", "--ticket", "DEMO-1"])
    parser.parse_args(["researcher-context"])
    parser.parse_args(["context-gc", "precompact"])
