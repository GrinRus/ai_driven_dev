from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "tests" / "repo_tools" / "entrypoints_bundle.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("entrypoints_bundle", SCRIPT_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"unable to load module from {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EntrypointsBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_module()

    def test_parse_args_default_root_points_to_repo_root(self) -> None:
        args = self.module.parse_args([])
        self.assertEqual(Path(args.root).resolve(), REPO_ROOT)
        self.assertTrue((Path(args.root) / ".claude-plugin" / "plugin.json").exists())


if __name__ == "__main__":
    unittest.main()
