import sys

from tests.helpers import REPO_ROOT

SRC_ROOT = REPO_ROOT
if str(SRC_ROOT) not in sys.path:  # pragma: no cover - test bootstrap
    sys.path.insert(0, str(SRC_ROOT))

import tools


def test_excepthook_suppresses_traceback(monkeypatch, capsys):
    monkeypatch.delenv("AIDD_DEBUG", raising=False)
    err = RuntimeError("BLOCK: something\nmore")
    tools._aidd_excepthook(RuntimeError, err, None)
    captured = capsys.readouterr()
    assert "[aidd] ERROR:" in captured.err
    assert "BLOCK: something more" in captured.err
    assert "Traceback" not in captured.err


def test_excepthook_debug_uses_default(monkeypatch):
    monkeypatch.setenv("AIDD_DEBUG", "1")
    calls = {}

    def fake_hook(exc_type, exc, tb):
        calls["called"] = True
        calls["exc_type"] = exc_type
        calls["exc"] = exc

    monkeypatch.setattr(sys, "__excepthook__", fake_hook, raising=False)
    err = RuntimeError("boom")
    tools._aidd_excepthook(RuntimeError, err, None)
    assert calls.get("called") is True
    assert calls["exc_type"] is RuntimeError
    assert calls["exc"] is err
