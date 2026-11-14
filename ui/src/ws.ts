// OWNER: P4
// Socket client: connects to the Python server and reconnects by itself, backing off while it is away.
import type { Command, Connection, ServerMsg } from "./types";

const WS_URL = import.meta.env.DEV ? "ws://localhost:8000/ws" : `ws://${location.host}/ws`;
const RETRY_MIN_MS = 400;
const RETRY_MAX_MS = 4000;

export interface HelmSocket {
  send(cmd: Command): void;
  close(): void;
}

export type OnMessage = (msg: ServerMsg) => void;
export type OnStatus = (connection: Connection) => void;

export function connect(onMessage: OnMessage, onStatus: OnStatus): HelmSocket {
  let ws: WebSocket | null = null;
  let closed = false;
  let timer: number | undefined;
  let retry = RETRY_MIN_MS;

  const open = () => {
    ws = new WebSocket(WS_URL);
    ws.onopen = () => {
      retry = RETRY_MIN_MS;
      onStatus("open");
    };
    ws.onmessage = (e) => onMessage(JSON.parse(e.data) as ServerMsg);
    ws.onclose = () => {
      if (closed) return;
      onStatus("closed");
      timer = window.setTimeout(open, retry);
      retry = Math.min(RETRY_MAX_MS, retry * 1.6);
    };
  };
  onStatus("connecting");
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
