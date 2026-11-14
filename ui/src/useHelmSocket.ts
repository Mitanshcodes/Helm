// OWNER: P4
// The dashboard's one data source: latest state and frame (at most one render per animation frame), the
// connection status, and a typed send(). ?mock=1 or VITE_MOCK=1 swaps the socket for the in-browser mock.
import { useCallback, useEffect, useRef, useState } from "react";
import { startMock } from "./mockServer";
import type { Command, Connection, EventMsg, FrameMsg, HelmState, ServerMsg } from "./types";
import { connect, type HelmSocket } from "./ws";

export const MOCK = new URLSearchParams(location.search).has("mock") || import.meta.env.VITE_MOCK === "1";

export function useHelmSocket(onEvent: (event: EventMsg) => void) {
  const [state, setState] = useState<HelmState | null>(null);
  const [frame, setFrame] = useState<FrameMsg | null>(null);
  const [connection, setConnection] = useState<Connection>("connecting");
  const socket = useRef<HelmSocket | null>(null);
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    let latestState: HelmState | null = null;
    let latestFrame: FrameMsg | null = null;
    let raf = 0;
    const flush = () => {
      raf = 0;
      if (latestState) setState(latestState);
      if (latestFrame) setFrame(latestFrame);
    };
    const onMessage = (msg: ServerMsg) => {
      if (msg.type === "event") return handler.current(msg);
      if (msg.type === "state") latestState = msg;
      else latestFrame = msg;
      if (!raf) raf = requestAnimationFrame(flush);
    };
    const s = (MOCK ? startMock : connect)(onMessage, setConnection);
    socket.current = s;
    return () => {
      cancelAnimationFrame(raf);
      s.close();
    };
  }, []);

  const send = useCallback((cmd: Command) => socket.current?.send(cmd), []);
  return { state, frame, connection, send };
}
