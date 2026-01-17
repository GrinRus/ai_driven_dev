import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from tools import context_pack
from tools import identifiers
from tools import plan_review_gate
from tools import prd_review
from tools import prd_review_gate
from tools import researcher_context
from tools import tasklist_check
from tools import tests_log


def test_cli_parses_new_subcommands():
    prd_review.parse_args(["--target", ".", "--ticket", "DEMO-1"])
    plan_review_gate.parse_args(["--ticket", "DEMO-1"])
    prd_review_gate.parse_args(["--ticket", "DEMO-1"])
    tasklist_check.parse_args(["--target", ".", "--ticket", "DEMO-1"])
    researcher_context._build_parser().parse_args([])
    identifiers.parse_args(["--target", ".", "--json"])
    context_pack.parse_args(["--agent", "implementer"])
    tests_log.parse_args(["--status", "pass"])
