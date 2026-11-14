# OWNER: P2
"""Launcher isolation and configuration, without a desktop, camera or controller."""
import sys
from types import SimpleNamespace

import pytest

from helm import overlay


def test_browser_mode_uses_requested_port_and_mock_without_native_gui(monkeypatch):
    urls = []
    monkeypatch.setattr(overlay.webbrowser, "open", lambda url: urls.append(url) or True)
    assert overlay.main(["--browser", "--mock", "--port", "8123"]) == 0
    assert urls == ["http://127.0.0.1:8123/?overlay=1&mock=1"]


def test_native_viewer_uses_separate_gui_and_topmost_window(monkeypatch):
    windows, starts = [], []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "webview", SimpleNamespace(
        create_window=lambda *a, **kw: windows.append((a, kw)),
        start=lambda **kw: starts.append(kw),
    ))
    assert overlay.main([]) == 0
    assert windows[0][0][1] == "http://127.0.0.1:8000/?overlay=1"
    assert windows[0][1]["on_top"] is True
    assert windows[0][1]["min_size"] == (320, 540)
    assert "js_api" not in windows[0][1]
    assert starts == [{"gui": "edgechromium"}]
    assert overlay.main(["--no-top", "--width", "480", "--height", "720"]) == 0
    assert windows[-1][1]["on_top"] is False
    assert windows[-1][1]["width"] == 480


def test_native_unavailable_on_other_platforms(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "darwin")
    assert overlay.main([]) == 1
    assert "--browser" in capsys.readouterr().err


def test_missing_dependency_has_install_instruction(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "webview", None)
    assert overlay.main([]) == 1
    assert "pip install pywebview" in capsys.readouterr().err


def test_failed_engine_has_actionable_fallback(monkeypatch, capsys):
    monkeypatch.setattr(sys, "platform", "win32")
    def fail(**kwargs):
        raise RuntimeError("missing engine")
    monkeypatch.setitem(sys.modules, "webview", SimpleNamespace(create_window=lambda *a, **kw: None, start=fail))
    assert overlay.main([]) == 1
    assert "WebView2" in capsys.readouterr().err


@pytest.mark.parametrize("args", [["--port", "0"], ["--port", "65536"], ["--width", "319"], ["--height", "539"]])
def test_invalid_configuration(args):
    with pytest.raises(SystemExit) as exc:
        overlay.parse_args(args)
    assert exc.value.code == 2
