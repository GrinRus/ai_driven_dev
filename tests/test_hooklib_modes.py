import os
import unittest
from unittest import mock

from hooks import hooklib


class HooklibModeTests(unittest.TestCase):
    def test_default_hooks_mode_fast(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(hooklib.resolve_hooks_mode(), "fast")

    def test_strict_hooks_mode(self) -> None:
        with mock.patch.dict(os.environ, {"AIDD_HOOKS_MODE": "strict"}):
            self.assertEqual(hooklib.resolve_hooks_mode(), "strict")

    def test_invalid_hooks_mode_falls_back_fast(self) -> None:
        with mock.patch.dict(os.environ, {"AIDD_HOOKS_MODE": "weird"}):
            self.assertEqual(hooklib.resolve_hooks_mode(), "fast")


if __name__ == "__main__":
    unittest.main()
