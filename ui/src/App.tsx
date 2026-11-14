// OWNER: P4
// One page (docs/SPEC.md section 9). Default layout shows everything; ?overlay=1 is the small window beside the
// game; ?quick=1 makes calibration a quick one; ?mock=1 runs with no backend.
import { useCallback, useEffect, useRef, useState } from "react";
import type { CoachResult, Command, EventMsg, Mapping, MappingStatus } from "./types";
import { MOCK, fetchProfiles, useHelmSocket } from "./useHelmSocket";
import { useFireClicks, useSetting, useSpokenPrompts } from "./feedback";
import { JUDGE, ProfileCard } from "./components/ProfileCard";
import { useTeachFlow } from "./teach";
import { CameraView } from "./components/CameraView";
import { CoachPanel } from "./components/CoachPanel";
import { OutputCard, SipPuffCard, StatTiles } from "./components/Controls";
import { Gauges } from "./components/Gauges";
import { GestureRecorder } from "./components/GestureRecorder";
import { MappingView } from "./components/MappingView";
import { StatusBanner, StatusBar } from "./components/StatusBar";
import { Wizard } from "./components/Wizard";
import { TeachPanel } from "./components/TeachPanel";
import { SetupTabs, useSetupTab } from "./components/SetupTabs";

const params = new URLSearchParams(location.search);
const OVERLAY = params.has("overlay");
const QUICK = params.has("quick");
const FACE_STEADY_MS = 1000; // a face must be visible this long before calibration starts by itself
const MAPPING_ACK_MS = 600; // no "error" event within this time means set_mapping was applied
const TOAST_MS = 6000;

export default function App() {
  const [coach, setCoach] = useState<CoachResult | null>(null);
  const [coachBusy, setCoachBusy] = useState(false);
  const [applied, setApplied] = useState<Mapping | null>(null); // last mapping this page knows was applied
  const [mappingStatus, setMappingStatus] = useState<MappingStatus>({ errors: [], applied: false });
  const [toast, setToast] = useState<string | null>(null);
  const pending = useRef<number | undefined>(undefined); // timer of a set_mapping waiting for error-or-silence
  const faceSince = useRef<number | null>(null);
  const autoSent = useRef(false);
  const [profiles, setProfiles] = useState<Record<string, string[]>>({});
  const visitorPending = useRef(false); // "Next visitor" waits for the judge profile before calibrating
  const sendRef = useRef<(cmd: Command) => void>(() => {});
  const [voice, setVoice] = useSetting("voice");
  const [clicks, setClicks] = useSetting("clicks");
  const refreshProfiles = useCallback(() => void fetchProfiles().then(setProfiles), []);
  const teachRef = useRef<ReturnType<typeof useTeachFlow> | null>(null);
  const playerRef = useRef("guest");
  const [tab, setTab] = useSetupTab();

  const onEvent = useCallback((msg: EventMsg) => {
    const data = msg.data;
    if (teachRef.current?.onEvent(msg, playerRef.current)) return;
    if (msg.name === "calibration_done") {
      // Right after a full calibration is when almost everyone wants their own move: offer it in place.
      if (data.mode === "full" && playerRef.current !== JUDGE && !OVERLAY) teachRef.current?.offer();
      return;
    }
    if (msg.name === "coach_result") {
      setCoach(data as unknown as CoachResult);
      setCoachBusy(false);
      setTab("coach"); // show the proposal where it can be accepted
    } else if (msg.name === "profile_loaded") {
      if (visitorPending.current && data.player === JUDGE) {
        visitorPending.current = false;
        sendRef.current({ cmd: "calibrate", mode: "quick" });
      }
      setApplied(null);
      setCoach(null);
      setMappingStatus({ errors: [], applied: false });
    } else if (msg.name === "error") {
      const message = String(data.message ?? "Something went wrong");
      if (data.cmd === "set_mapping") {
        window.clearTimeout(pending.current);
        setMappingStatus({ errors: Array.isArray(data.errors) ? data.errors.map(String) : [message], applied: false });
      } else {
        setCoachBusy(false);
        setToast(message);
      }
    }
  }, [setTab]);

  const { state, frame, connection, send: rawSend } = useHelmSocket(onEvent);

  const send = useCallback(
    (cmd: Command) => {
      if (cmd.cmd === "coach_build" || cmd.cmd === "coach_review") setCoachBusy(true);
      rawSend(cmd);
    },
    [rawSend],
  );

  sendRef.current = send;
  const teach = useTeachFlow(send);
  teachRef.current = teach;
  if (state) playerRef.current = state.profile.player;
  useSpokenPrompts(state, voice);
  useFireClicks(state, clicks);

  useEffect(() => {
    if (connection === "open") refreshProfiles();
  }, [connection, refreshProfiles]);

  const nextVisitor = useCallback(() => {
    if (!state) return;
    const games = profiles[JUDGE] ?? [];
    const game = games.includes(state.profile.game) ? state.profile.game : games[0];
    if (!game) return;
    visitorPending.current = true;
    send({ cmd: "load_profile", player: JUDGE, game });
  }, [state, profiles, send]);

  const applyMapping = useCallback(
    (next: Mapping) => {
      window.clearTimeout(pending.current);
      setMappingStatus({ errors: [], applied: false });
      rawSend({ cmd: "set_mapping", mapping: next });
      pending.current = window.setTimeout(() => {
        setApplied(next);
        setMappingStatus({ errors: [], applied: true });
      }, MAPPING_ACK_MS);
    },
    [rawSend],
  );

  useEffect(() => {
    if (connection === "open") return;
    autoSent.current = false; // a restarted server may have no calibration again
    faceSince.current = null;
    setCoachBusy(false);
    teach.close();
  }, [connection]); // eslint-disable-line react-hooks/exhaustive-deps

  // First calibration starts by itself once a face has been visible for a second. The overlay window never
  // starts it, so two open windows do not both send the command.
  useEffect(() => {
    if (!state || OVERLAY || autoSent.current || connection !== "open") return;
    if (!state.face || state.profile.calibrated || state.progress) {
      faceSince.current = null;
      return;
    }
    const now = performance.now();
    faceSince.current ??= now;
    if (now - faceSince.current >= FACE_STEADY_MS) {
      autoSent.current = true;
      send({ cmd: "calibrate", mode: QUICK ? "quick" : "full" });
    }
  }, [state, connection, send]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), TOAST_MS);
    return () => window.clearTimeout(t);
  }, [toast]);

  const offline = connection !== "open";
  const lost = (
    <div className="lost" role="alert">
      <h2>Can’t reach Helm</h2>
      <p>
        Make sure <code>python -m helm</code> is running. This page keeps trying{MOCK ? "" : " and will reconnect by itself"}.
      </p>
    </div>
  );
  if (!state) return <main className="page">{offline && connection === "closed" ? lost : <p className="starting">Starting Helm…</p>}</main>;

  const mapping = state.mapping ?? applied;
  return (
    <>
      <main className={`page${OVERLAY ? " compact" : ""}${offline ? " dimmed" : ""}`} aria-hidden={offline}>
        <StatusBar
          state={state}
          connection={connection}
          send={send}
          mode={QUICK ? "quick" : "full"}
          compact={OVERLAY}
          onNextVisitor={profiles[JUDGE]?.length ? nextVisitor : undefined}
          onTeach={teach.flow ? undefined : teach.offer}
        />
        <StatusBanner state={state} />
        {state.progress ? (
          <Wizard progress={state.progress} flow={teach.flow} />
        ) : (
          teach.flow &&
          !OVERLAY && (
            <TeachPanel
              state={state}
              flow={teach.flow}
              hasFace={teach.hasFace(state.profile.player)}
              voice={voice}
              begin={teach.begin}
              go={teach.go}
              offer={teach.offer}
              close={teach.close}
            />
          )
        )}
        <div className="dash">
          <div className="dash-camera">
            <CameraView frame={frame} state={state} compact={OVERLAY} />
            {!OVERLAY && <StatTiles state={state} />}
          </div>
          <div className="dash-face">
            <Gauges state={state} mapping={mapping} />
          </div>
          <div className="dash-output">
            <OutputCard state={state} mapping={mapping} />
            <SipPuffCard state={state} mapping={mapping} />
          </div>
        </div>
        {!OVERLAY && (
          <SetupTabs
            tab={tab}
            setTab={setTab}
            tabs={[
              { id: "mapping", label: "Mapping", body: <MappingView mapping={mapping} status={mappingStatus} apply={applyMapping} send={send} /> },
              {
                id: "coach",
                label: "Coach",
                badge: coachBusy ? "working" : coach ? "new" : undefined,
                body: <CoachPanel state={state} send={send} result={coach} busy={coachBusy} apply={applyMapping} />,
              },
              {
                id: "moves",
                label: "Your moves",
                badge: state.gestures.learned.length ? String(state.gestures.learned.length) : undefined,
                body: <GestureRecorder state={state} send={send} busy={state.progress !== null || teach.flow !== null} onTeach={teach.offer} />,
              },
              {
                id: "profile",
                label: "Profile & sound",
                body: (
                  <ProfileCard
                    state={state}
                    send={send}
                    profiles={profiles}
                    voice={voice}
                    setVoice={setVoice}
                    clicks={clicks}
                    setClicks={setClicks}
                  />
                ),
              },
            ]}
          />
        )}
      </main>
      {offline && lost}
      {toast && (
        <button className="toast" role="alert" onClick={() => setToast(null)}>
          {toast}
        </button>
      )}
    </>
  );
}
