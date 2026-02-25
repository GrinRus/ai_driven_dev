from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from tests.helpers import ensure_gates_config, ensure_project_root, write_active_feature, write_json

from aidd_runtime import prd_review_cli


def _make_args(ticket: str) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        ticket=ticket,
        slug_hint=None,
        pack_only=False,
        report=f"aidd/reports/prd/{ticket}.json",
    )


class ReviewSpecAstPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="review-spec-ast-")
        self.tmp_path = Path(self._tmpdir.name)
        self.workspace = self.tmp_path / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.project_root = ensure_project_root(self.workspace)
        ensure_gates_config(self.project_root)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def _seed_common(self, ticket: str) -> None:
        write_active_feature(self.project_root, ticket)
        write_json(
            self.project_root,
            f"reports/prd/{ticket}.json",
            {"ticket": ticket, "status": "ready", "findings": []},
        )

    def test_prd_review_cli_optional_ast_missing_does_not_block(self) -> None:
        ticket = "review-ast-soft"
        self._seed_common(ticket)
        ensure_gates_config(
            self.project_root,
            {
                "ast_index": {
                    "mode": "auto",
                    "required": False,
                }
            },
        )

        old_cwd = Path.cwd()
        os.chdir(self.workspace)
        stderr = io.StringIO()
        try:
            with mock.patch.object(prd_review_cli.prd_review, "parse_args", return_value=_make_args(ticket)):
                with mock.patch.object(prd_review_cli, "validate_research", return_value=None):
                    with mock.patch.object(
                        prd_review_cli.runtime,
                        "resolve_feature_context",
                        return_value=types.SimpleNamespace(resolved_ticket=ticket, slug_hint=ticket),
                    ):
                        with mock.patch.object(prd_review_cli.prd_review, "run", return_value=0) as run_mock:
                            with contextlib.redirect_stderr(stderr):
                                code = prd_review_cli.main([])
        finally:
            os.chdir(old_cwd)

        self.assertEqual(code, 0)
        self.assertIn("reason_code=ast_index_pack_missing_warn", stderr.getvalue())
        manifest = self.project_root / "reports" / "context" / f"{ticket}-memory-slices.review-spec.{ticket}.pack.json"
        self.assertTrue(manifest.exists(), "review-spec should materialize stage memory slice manifest")
        run_mock.assert_called_once()

    def test_prd_review_cli_required_ast_missing_blocks(self) -> None:
        ticket = "review-ast-hard"
        self._seed_common(ticket)
        ensure_gates_config(
            self.project_root,
            {
                "ast_index": {
                    "mode": "required",
                    "required": True,
                }
            },
        )

        old_cwd = Path.cwd()
        os.chdir(self.workspace)
        stderr = io.StringIO()
        try:
            with mock.patch.object(prd_review_cli.prd_review, "parse_args", return_value=_make_args(ticket)):
                with mock.patch.object(prd_review_cli, "validate_research", return_value=None):
                    with mock.patch.object(
                        prd_review_cli.runtime,
                        "resolve_feature_context",
                        return_value=types.SimpleNamespace(resolved_ticket=ticket, slug_hint=ticket),
                    ):
                        with mock.patch.object(prd_review_cli.prd_review, "run", return_value=0) as run_mock:
                            with contextlib.redirect_stderr(stderr):
                                code = prd_review_cli.main([])
        finally:
            os.chdir(old_cwd)

        self.assertEqual(code, 2)
        self.assertIn("reason_code=ast_index_pack_missing", stderr.getvalue())
        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
