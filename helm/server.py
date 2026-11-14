# OWNER: P4
"""FastAPI + WebSocket server and preview encoding (docs/SPEC.md 6.14, 8). Bootstrap stub: state messages only."""
import asyncio
from typing import TYPE_CHECKING

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from helm import config

if TYPE_CHECKING:
    from helm.main import Runtime


def create_app(runtime: "Runtime") -> FastAPI:
    app = FastAPI(title="Helm")

    @app.websocket("/ws")
    async def ws(sock: WebSocket) -> None:
        # TODO(P4): drain runtime.pop_events() each tick, send preview frames at 15 fps (resize, mirror,
        # JPEG, base64, here and never in the pipeline thread), handle incoming commands (reply to bad
        # ones with an "error" event), serve ui/dist at "/", CORS for localhost:5173.
        await sock.accept()
        try:
            while True:
                await sock.send_json(runtime.snapshot())
                await asyncio.sleep(1.0 / config.STATE_HZ)
        except (WebSocketDisconnect, RuntimeError):
            pass

    return app


def run(runtime: "Runtime", host: str = config.SERVER_HOST, port: int = config.SERVER_PORT) -> None:
    import uvicorn

    uvicorn.run(create_app(runtime), host=host, port=port, log_level="warning")
