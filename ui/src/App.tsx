// OWNER: P4
// One page. Bootstrap stub: live state from the socket, placeholder panels (docs/SPEC.md section 9).
import { useEffect, useRef, useState } from "react";
import { connect } from "./ws";
import type { Command, FrameMsg, HelmState } from "./types";
import { CameraView } from "./components/CameraView";
import { CoachPanel } from "./components/CoachPanel";
import { Gauges } from "./components/Gauges";
import { GestureRecorder } from "./components/GestureRecorder";
import { MappingView } from "./components/MappingView";
import { StatusBar } from "./components/StatusBar";
import { Wizard } from "./components/Wizard";

export default function App() {
  const [state, setState] = useState<HelmState | null>(null);
  const [frame, setFrame] = useState<FrameMsg | null>(null);
  const [online, setOnline] = useState(false);
  const socket = useRef<{ send(cmd: Command): void } | null>(null);
  const send = (cmd: Command) => socket.current?.send(cmd);

  useEffect(() => {
    const s = connect((msg) => {
      if (msg.type === "state") setState(msg);
      else if (msg.type === "frame") setFrame(msg);
      // TODO(P4): handle "event" messages (calibration_done, gesture_trained, coach_result, error).
    }, setOnline);
    socket.current = s;
    return () => s.close();
  }, []);

  // TODO(P4): auto-start calibration once a face has been visible for one second (?quick=1 for quick mode).
  const overlay = new URLSearchParams(location.search).has("overlay");

  if (!online || !state) return <main className="reconnecting">Reconnecting…</main>;

  return (
    <main className={overlay ? "app overlay" : "app"}>
      <StatusBar state={state} />
      {state.progress && <Wizard progress={state.progress} />}
      <CameraView frame={frame} />
      <Gauges state={state} />
      {!overlay && (
        <>
          <GestureRecorder state={state} send={send} />
          <MappingView state={state} send={send} />
          <CoachPanel state={state} send={send} />
        </>
      )}
    </main>
  );
}
