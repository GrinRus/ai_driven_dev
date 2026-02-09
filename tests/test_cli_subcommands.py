import sys

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

from aidd_runtime import context_pack
from aidd_runtime import identifiers
from aidd_runtime import implement_run
from aidd_runtime import plan_review_gate
from aidd_runtime import prd_review
from aidd_runtime import prd_review_gate
from aidd_runtime import qa_run
from aidd_runtime import rlm_targets
from aidd_runtime import review_run
from aidd_runtime import spec_interview
from aidd_runtime import tasklist_check
from aidd_runtime import tasks_new
from aidd_runtime import tests_log


def test_cli_parses_new_subcommands():
    prd_review.parse_args(["--ticket", "DEMO-1"])
    plan_review_gate.parse_args(["--ticket", "DEMO-1"])
    prd_review_gate.parse_args(["--ticket", "DEMO-1"])
    tasklist_check.parse_args(["--ticket", "DEMO-1"])
    rlm_targets.parse_args(["--ticket", "DEMO-1"])
    spec_interview.parse_args(["--ticket", "DEMO-1"])
    tasks_new.parse_args(["--ticket", "DEMO-1"])
    implement_run.parse_args(["--ticket", "DEMO-1"])
    review_run.parse_args(["--ticket", "DEMO-1"])
    qa_run.parse_args(["--ticket", "DEMO-1"])
    identifiers.parse_args(["--json"])
    context_pack.parse_args(["--agent", "implementer"])
    tests_log.parse_args(["--status", "pass"])
