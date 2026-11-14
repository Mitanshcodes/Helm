# OWNER: P4
"""FastAPI + WebSocket server and preview encoding (docs/SPEC.md 6.14, 8)."""
import asyncio
import base64
import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from helm import config

if TYPE_CHECKING:
    from helm.main import Runtime

log = logging.getLogger("helm.server")

UI_DIST = Path(__file__).resolve().parent.parent / "ui" / "dist"
_GESTURE_NAME = re.compile(r"^[A-Za-z0-9_]{1,32}$")
_PROFILE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,32}$")      # becomes a folder or file name under profiles/


def _jsonable(value):
    """json.dumps fallback for numpy scalars and arrays that slip into a snapshot or an event."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _dumps(message: dict) -> str:
    return json.dumps(message, default=_jsonable)


def _error(message: str, **data) -> dict:
    return {"type": "event", "name": "error", "data": {"message": message, **data}}


def encode_preview(bgr: np.ndarray, landmarks: np.ndarray | None) -> dict:
    """The "frame" message: resized, mirrored JPEG as base64, landmark x mirrored to match."""
    import cv2

    small = cv2.flip(cv2.resize(bgr, config.PREVIEW_SIZE, interpolation=cv2.INTER_AREA), 1)
    ok, jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, config.PREVIEW_JPEG_QUALITY])
    if not ok:
        raise ValueError("JPEG encoding failed")
    points = None
    if landmarks is not None:
        mirrored = np.asarray(landmarks, np.float32).copy()
        mirrored[:, 0] = 1.0 - mirrored[:, 0]
        points = np.round(mirrored, 3).tolist()
    return {"type": "frame", "jpeg": base64.b64encode(jpeg.tobytes()).decode("ascii"), "landmarks": points}


def handle_command(runtime: "Runtime", text: str) -> dict | None:
    """Run one dashboard command (docs/SPEC.md 8). Returns an "error" event to send back, or None. Never raises."""
    try:
        msg = json.loads(text)
    except (ValueError, TypeError):
        return _error("Command is not valid JSON")
    if not isinstance(msg, dict) or not isinstance(msg.get("cmd"), str):
        return _error('Command needs a "cmd" string')
    cmd = msg["cmd"]

    def name_of(key: str, pattern: re.Pattern) -> str | None:
        value = msg.get(key)
        return value if isinstance(value, str) and pattern.match(value) else None

    try:
        if cmd == "calibrate":
            if msg.get("mode") not in ("full", "quick"):
                return _error('calibrate needs "mode": "full" or "quick"', cmd=cmd)
            runtime.start_calibration(msg["mode"])
        elif cmd == "record_gesture":
            name = name_of("name", _GESTURE_NAME)
            if name is None or name == "none":
                return _error("Gesture names use letters, digits and underscores, and cannot be \"none\"", cmd=cmd)
            runtime.record_gesture(name)
        elif cmd == "record_negative":
            runtime.record_negative()
        elif cmd == "delete_gesture":
            name = name_of("name", _GESTURE_NAME)
            if name is None:
                return _error('delete_gesture needs a gesture "name"', cmd=cmd)
            runtime.delete_gesture(name)
        elif cmd == "set_mapping":
            if not isinstance(msg.get("mapping"), dict):
                return _error('set_mapping needs a "mapping" object', cmd=cmd)
            errors = runtime.set_mapping(msg["mapping"])
            if errors:
                return _error("Mapping rejected", cmd=cmd, errors=list(errors))
        elif cmd == "load_profile":
            player, game = name_of("player", _PROFILE_NAME), name_of("game", _PROFILE_NAME)
            if player is None or game is None:
                return _error('load_profile needs "player" and "game" names', cmd=cmd)
            runtime.load_profile(player, game)
        elif cmd == "save_profile":
            runtime.save_profile()
        elif cmd == "pause":
            if not isinstance(msg.get("on"), bool):
                return _error('pause needs "on": true or false', cmd=cmd)
            runtime.set_paused(msg["on"])
        elif cmd == "coach_build":
            game = name_of("game", _PROFILE_NAME)
            if game is None:
                return _error('coach_build needs a "game" name', cmd=cmd)
            runtime.coach_build(game)
        elif cmd == "coach_review":
            runtime.coach_review()
        else:
            return _error(f"Unknown command: {cmd}", cmd=cmd)
    except Exception as e:
        log.exception("command %s failed", cmd)
        return _error(f"{type(e).__name__}: {e}", cmd=cmd)
    return None


class _Hub:
    """One broadcast loop for every connected dashboard, so events reach all of them (default and overlay)."""

    def __init__(self, runtime: "Runtime"):
        self.runtime = runtime
        self.clients: dict[WebSocket, list[dict]] = {}     # socket -> replies waiting for the next tick
        self._task: asyncio.Task | None = None
        self._seen_errors: set[str] = set()

    def add(self, sock: WebSocket) -> list[dict]:
        replies: list[dict] = []
        self.clients[sock] = replies
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
        return replies

    def remove(self, sock: WebSocket) -> None:
        self.clients.pop(sock, None)

    async def _send(self, messages: list[str]) -> None:
        for sock, replies in list(self.clients.items()):
            try:
                for text in messages:
                    await sock.send_text(text)
                while replies:
                    await sock.send_text(_dumps(replies.pop(0)))
            except Exception:                              # client went away; its receive loop cleans up too
                self.remove(sock)

    def _log_once(self, e: Exception) -> None:
        key = f"{type(e).__name__}: {e}"
        if key not in self._seen_errors:
            self._seen_errors.add(key)
            log.exception("broadcast error (logged once): %s", key)

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        period = 1.0 / config.STATE_HZ
        frame_every = max(1, round(config.STATE_HZ / config.PREVIEW_FPS))
        tick, last_preview, next_t = 0, None, loop.time()
        while self.clients:
            messages: list[str] = []
            try:
                messages.append(_dumps(self.runtime.snapshot()))
                messages += [_dumps(event) for event in self.runtime.pop_events()]
            except Exception as e:
                self._log_once(e)
            await self._send(messages)                     # state goes out before any preview work
            if tick % frame_every == 0:
                try:
                    preview = self.runtime.preview()
                    if preview is not None and preview is not last_preview:   # encode each camera frame once
                        last_preview = preview
                        await self._send([_dumps(await asyncio.to_thread(encode_preview, *preview))])
                except Exception as e:
                    self._log_once(e)
            tick += 1
            next_t += period
            delay = next_t - loop.time()
            if delay < 0:                                  # fell behind: drop the missed ticks, do not catch up
                next_t, delay = loop.time(), 0.0
            await asyncio.sleep(delay)


def create_app(runtime: "Runtime") -> FastAPI:
    app = FastAPI(title="Helm")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])
    hub = _Hub(runtime)

    @app.websocket("/ws")
    async def ws(sock: WebSocket) -> None:
        await sock.accept()
        replies = hub.add(sock)
        try:
            while True:
                reply = handle_command(runtime, await sock.receive_text())
                if reply is not None:
                    replies.append(reply)
        except WebSocketDisconnect:
            pass
        except Exception:
            log.debug("dashboard socket closed with an error", exc_info=True)
        finally:
            hub.remove(sock)

    if (UI_DIST / "index.html").exists():                  # built dashboard: the demo needs one process
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=UI_DIST, html=True), name="ui")

    return app


def run(runtime: "Runtime", host: str = config.SERVER_HOST, port: int = config.SERVER_PORT) -> None:
    import uvicorn

    uvicorn.run(create_app(runtime), host=host, port=port, log_level="warning")
