# OWNER: P4
"""Bootstrap check for server.py. TODO(P4): commands call Runtime methods, bad commands get an "error" event."""
import pytest

pytest.importorskip("fastapi")


def test_app_has_the_websocket_route():
    from helm.server import create_app

    class FakeRuntime:
        def snapshot(self) -> dict:
            return {"type": "state"}

    app = create_app(FakeRuntime())
    assert "/ws" in [route.path for route in app.routes]
