from __future__ import annotations

import sys
from importlib import resources
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from claude_workflow_cli import cli


def test_payload_root_release_fallback_to_bundled():
    payload_resource = resources.files(cli.PAYLOAD_PACKAGE) / "payload"
    with resources.as_file(payload_resource) as bundled_path:
        bundled_root = Path(bundled_path)
        with mock.patch(
            "claude_workflow_cli.cli._ensure_remote_payload",
            side_effect=cli.PayloadError("network error"),
        ) as mocked_fetch:
            with cli._payload_root("latest") as resolved_path:
                assert resolved_path.resolve() == bundled_root.resolve()
        mocked_fetch.assert_called_once()
