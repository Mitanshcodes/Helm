# OWNER: P4
"""server.py: commands call Runtime methods, bad commands get an "error" event, the socket broadcasts."""
import json

import numpy as np
import pytest

pytest.importorskip("fastapi")

from helm.server import create_app, encode_preview, handle_command  # noqa: E402


class FakeRuntime:
    def __init__(self):
        self.calls: list[tuple] = []
        self.events: list[dict] = []
        self.mapping_errors: list[str] = []
        self.frame = None

    def snapshot(self) -> dict:
        return {"type": "state", "fps": np.float32(30.0)}

    def preview(self):
        return self.frame

    def pop_events(self) -> list[dict]:
        events, self.events = self.events, []
        return events

    def start_calibration(self, mode): self.calls.append(("calibrate", mode))
    def record_gesture(self, name): self.calls.append(("record_gesture", name))
    def record_negative(self): self.calls.append(("record_negative",))
    def delete_gesture(self, name): self.calls.append(("delete_gesture", name))
    def load_profile(self, player, game): self.calls.append(("load_profile", player, game))
    def save_profile(self): self.calls.append(("save_profile",))
    def set_paused(self, on): self.calls.append(("pause", on))
    def coach_build(self, game): self.calls.append(("coach_build", game))

    def coach_review(self):
        raise RuntimeError("coach exploded")

    def set_mapping(self, mapping) -> list[str]:
        self.calls.append(("set_mapping", mapping))
        return self.mapping_errors


def send(runtime, **msg):
    return handle_command(runtime, json.dumps(msg))


def test_every_command_calls_its_runtime_method():
    rt = FakeRuntime()
    commands = [
        ({"cmd": "calibrate", "mode": "quick"}, ("calibrate", "quick")),
        ({"cmd": "record_gesture", "name": "left_smirk"}, ("record_gesture", "left_smirk")),
        ({"cmd": "record_negative"}, ("record_negative",)),
        ({"cmd": "delete_gesture", "name": "left_smirk"}, ("delete_gesture", "left_smirk")),
        ({"cmd": "set_mapping", "mapping": {"axes": []}}, ("set_mapping", {"axes": []})),
        ({"cmd": "load_profile", "player": "sam", "game": "SuperTuxKart"}, ("load_profile", "sam", "SuperTuxKart")),
        ({"cmd": "save_profile"}, ("save_profile",)),
        ({"cmd": "pause", "on": True}, ("pause", True)),
        ({"cmd": "coach_build", "game": "SuperTuxKart"}, ("coach_build", "SuperTuxKart")),
    ]
    for msg, expected in commands:
        assert send(rt, **msg) is None, msg
        assert rt.calls[-1] == expected


@pytest.mark.parametrize("text", [
    "not json",
    "[1, 2]",
    '{"mode": "full"}',
    '{"cmd": "fly"}',
    '{"cmd": "calibrate", "mode": "slow"}',
    '{"cmd": "record_gesture"}',
    '{"cmd": "record_gesture", "name": "none"}',
    '{"cmd": "record_gesture", "name": "has space"}',
    '{"cmd": "delete_gesture", "name": 3}',
    '{"cmd": "set_mapping", "mapping": "x"}',
    '{"cmd": "load_profile", "player": "../etc", "game": "SuperTuxKart"}',
    '{"cmd": "pause", "on": "yes"}',
    '{"cmd": "coach_build"}',
])
def test_bad_commands_get_an_error_event_and_call_nothing(text):
    rt = FakeRuntime()
    reply = handle_command(rt, text)
    assert reply["type"] == "event" and reply["name"] == "error" and reply["data"]["message"]
    assert rt.calls == []


def test_rejected_mapping_returns_the_validation_errors():
    rt = FakeRuntime()
    rt.mapping_errors = ["target A driven twice"]
    reply = send(rt, cmd="set_mapping", mapping={})
    assert reply["data"]["cmd"] == "set_mapping"
    assert reply["data"]["errors"] == ["target A driven twice"]


def test_a_runtime_exception_becomes_an_error_event():
    reply = send(FakeRuntime(), cmd="coach_review")
    assert reply["name"] == "error" and "coach exploded" in reply["data"]["message"]


def test_preview_is_resized_and_mirrored():
    cv2 = pytest.importorskip("cv2")
    bgr = np.zeros((480, 640, 3), np.uint8)
    bgr[:, :320] = 255                                       # left half white
    landmarks = np.array([[0.25, 0.5], [1.0, 0.0]], np.float32)
    msg = encode_preview(bgr, landmarks)
    import base64

    image = cv2.imdecode(np.frombuffer(base64.b64decode(msg["jpeg"]), np.uint8), cv2.IMREAD_COLOR)
    assert image.shape == (240, 320, 3)
    assert image[120, 40].mean() < 30 and image[120, 280].mean() > 225   # white is now on the right
    assert msg["landmarks"] == [[0.75, 0.5], [0.0, 0.0]]
    assert landmarks[0, 0] == 0.25                           # the caller's array is untouched
    assert encode_preview(bgr, None)["landmarks"] is None


def test_socket_broadcasts_state_events_frames_and_error_replies():
    pytest.importorskip("httpx")
    pytest.importorskip("cv2")
    from fastapi.testclient import TestClient

    rt = FakeRuntime()
    rt.events = [{"type": "event", "name": "calibration_done", "data": {"mode": "quick"}}]
    rt.frame = (np.zeros((480, 640, 3), np.uint8), None)
    with TestClient(create_app(rt)).websocket_connect("/ws") as sock:
        sock.send_text('{"cmd": "pause", "on": true}')
        sock.send_text('{"cmd": "nope"}')
        seen: dict[str, dict] = {}
        for _ in range(40):
            msg = sock.receive_json()
            seen.setdefault(msg["name"] if msg["type"] == "event" else msg["type"], msg)
            if {"state", "frame", "calibration_done", "error"} <= seen.keys():
                break
    assert seen["state"]["fps"] == 30.0                      # numpy scalars are serialized
    assert seen["frame"]["jpeg"]
    assert seen["calibration_done"]["data"] == {"mode": "quick"}
    assert "nope" in seen["error"]["data"]["message"]
    assert ("pause", True) in rt.calls


def test_profiles_route_lists_players_and_games(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from helm import profiles

    monkeypatch.setattr(profiles, "list_profiles", lambda: {"judge": ["SuperTuxKart"]})
    assert TestClient(create_app(FakeRuntime())).get("/api/profiles").json() == {"judge": ["SuperTuxKart"]}


def test_profiles_route_returns_empty_on_failure(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from helm import profiles

    def broken():
        raise OSError("disk gone")

    monkeypatch.setattr(profiles, "list_profiles", broken)
    assert TestClient(create_app(FakeRuntime())).get("/api/profiles").json() == {}
