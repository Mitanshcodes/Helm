// OWNER: P4
// Socket client: connects to the Python server and reconnects by itself.
import type { Command, ServerMsg } from "./types";

const WS_URL = import.meta.env.DEV ? "ws://localhost:8000/ws" : `ws://${location.host}/ws`;
const RETRY_MS = 1000;

export interface HelmSocket {
  send(cmd: Command): void;
  close(): void;
}

export function connect(onMessage: (msg: ServerMsg) => void, onStatus: (online: boolean) => void): HelmSocket {
  let ws: WebSocket | null = null;
  let closed = false;
  let timer: number | undefined;

  const open = () => {
    ws = new WebSocket(WS_URL);
    ws.onopen = () => onStatus(true);
    ws.onmessage = (e) => onMessage(JSON.parse(e.data) as ServerMsg);
    ws.onclose = () => {
      onStatus(false);
      if (!closed) timer = window.setTimeout(open, RETRY_MS);
    };
  };
  open();

  return {
    send(cmd) {
      if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(cmd));
    },
    close() {
      closed = true;
      window.clearTimeout(timer);
      ws?.close();
    },
  };
}
