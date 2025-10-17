from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "prd-review-agent.py"


@pytest.fixture(scope="module")
def prd_review_agent():
    spec = importlib.util.spec_from_file_location("prd_review_agent", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_prd(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "docs" / "prd" / "demo-feature.prd.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def test_analyse_prd_marks_pending_when_action_items(tmp_path, prd_review_agent):
    prd = write_prd(
        tmp_path,
        dedent(
            """\
            # Demo

            ## PRD Review
            Status: approved
            - [ ] sync metrics with ops
            """
        ),
    )

    report = prd_review_agent.analyse_prd("demo-feature", prd)

    assert report.status == "approved"
    assert report.recommended_status == "pending"
    assert report.action_items == ["- [ ] sync metrics with ops"]
    assert not any(f.severity == "critical" for f in report.findings)


def test_analyse_prd_detects_placeholders(tmp_path, prd_review_agent):
    prd = write_prd(
        tmp_path,
        dedent(
            """\
            # Demo

            TBD: заполнить раздел

            ## PRD Review
            Status: pending
            """
        ),
    )

    report = prd_review_agent.analyse_prd("demo-feature", prd)

    assert report.status == "pending"
    assert any(f.severity == "major" for f in report.findings)
    assert report.recommended_status == "pending"


def test_analyse_prd_blocks_on_blocked_status(tmp_path, prd_review_agent):
    prd = write_prd(
        tmp_path,
        dedent(
            """\
            # Demo

            ## PRD Review
            Status: blocked
            """
        ),
    )

    report = prd_review_agent.analyse_prd("demo-feature", prd)

    assert report.status == "blocked"
    assert report.recommended_status == "blocked"
    assert any(f.severity == "critical" for f in report.findings)


def test_cli_writes_json_report(tmp_path):
    prd = write_prd(
        tmp_path,
        dedent(
            """\
            # Demo

            ## PRD Review
            Status: approved
            """
        ),
    )

    report_path = tmp_path / "reports" / "prd" / "demo-feature.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            sys.executable,
            str(MODULE_PATH),
            "--slug",
            "demo-feature",
            "--prd",
            str(prd),
            "--report",
            str(report_path),
        ],
        check=True,
        cwd=tmp_path,
    )

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["slug"] == "demo-feature"
    assert payload["status"] == "approved"
    assert payload["recommended_status"] == "approved"
