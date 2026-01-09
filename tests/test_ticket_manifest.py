import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import PAYLOAD_ROOT, cli_cmd, ensure_project_root, write_file


def load_manifest(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8").lstrip()
    if raw.startswith("---"):
        raw = "\n".join(raw.splitlines()[1:]).lstrip()
    return json.loads(raw)


class TicketManifestTests(unittest.TestCase):
    def test_set_active_feature_scaffolds_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ticket-manifest-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            template_src = (PAYLOAD_ROOT / "docs" / "tickets" / "template.yaml").read_text(
                encoding="utf-8"
            )
            write_file(root, "docs/tickets/template.yaml", template_src)
            write_file(root, "docs/prd/template.md", "# PRD\n\nStatus: draft\n\nTicket: <ticket>\n")
            env = os.environ.copy()
            result = subprocess.run(
                cli_cmd("set-active-feature", "--target", str(root), "DEMO-1"),
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            manifest_path = root / "docs" / "tickets" / "DEMO-1.yaml"
            self.assertTrue(manifest_path.exists(), "ticket manifest should be created")

            payload = load_manifest(manifest_path)
            self.assertEqual(payload.get("ticket"), "DEMO-1")
            self.assertEqual(payload.get("slug"), "DEMO-1")
            self.assertIn("artifacts", payload)
            self.assertIn("reports", payload)

    def test_slug_hint_is_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ticket-manifest-") as tmpdir:
            root = ensure_project_root(Path(tmpdir))
            template_src = (PAYLOAD_ROOT / "docs" / "tickets" / "template.yaml").read_text(
                encoding="utf-8"
            )
            write_file(root, "docs/tickets/template.yaml", template_src)
            write_file(root, "docs/prd/template.md", "# PRD\n\nStatus: draft\n\nTicket: <ticket>\n")
            env = os.environ.copy()
            result = subprocess.run(
                cli_cmd(
                    "set-active-feature",
                    "--target",
                    str(root),
                    "--slug-note",
                    "demo-slug",
                    "DEMO-2",
                ),
                text=True,
                capture_output=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            manifest_path = root / "docs" / "tickets" / "DEMO-2.yaml"
            payload = load_manifest(manifest_path)
            self.assertEqual(payload.get("ticket"), "DEMO-2")
            self.assertEqual(payload.get("slug"), "demo-slug")


if __name__ == "__main__":
    unittest.main()
