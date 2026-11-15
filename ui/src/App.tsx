// OWNER: P4
// The dashboard, printed like a riso zine page (docs/SPEC.md section 9). ?overlay=1 is the small window beside
// the game; ?quick=1 makes calibration a quick one; ?mock=1 runs with no backend.
//
//   intro -> "who's at the helm?" (profile picker: Default, saved players, New profile) -> dashboard
//
// The dashboard, top to bottom: the wordmark and Recalibrate; the camera; the move cards beside the controller
// (so a fired move and the pressed button are seen together); the Anchor (every setting behind five buttons);
// the stats. Calibration, teaching and Anchor pages open in front of the dashboard, which blurs behind them:
// calibration and teaching as "focus mode", the instructions over a big camera.
import { useCallback, useEffect, useRef, useState } from "react";
import type { CoachResult, Command, EventMsg, Mapping, MappingStatus } from "./types";
import { MOCK, fetchProfiles, useHelmSocket } from "./useHelmSocket";
import { useFireClicks, useSetting, useSpokenPrompts } from "./feedback";
import { HoldClock, buildRows } from "./moves";
import { spokenTake, useTeachFlow } from "./teach";
import { ProfileCard } from "./components/ProfileCard";
import { CalibrationCard, CalibrationDone, cameraHint, useCalibrationTrack, type CalMode, type BreathResult, type CustomResult, type FaceIdResult } from "./components/CalibrationCard";
import { DevControls } from "./components/DevControls";
import { CameraView, StatStamps } from "./components/CameraView";
import { CoachPanel, type CaptainUndo } from "./components/CoachPanel";
import { GestureRecorder } from "./components/GestureRecorder";
import { Intro } from "./components/Intro";
import { MappingView } from "./components/MappingView";
import { MessageBox } from "./components/MessageBox";
import { ControllerCard, MovesPanel } from "./components/MovesPanel";
import { OptionsBar, useOptions } from "./components/OptionsBar";
import { ProfilePicker } from "./components/ProfilePicker";
import { Anchor, AnchorPanel, type AnchorPage, type TabId } from "./components/SetupTabs";
import { TopBar } from "./components/StatusBar";
import { SteeringCard } from "./components/SteeringCard";
import { Fleet } from "./components/Fleet";
import { TeachPanel } from "./components/TeachPanel";
import { Wizard } from "./components/Wizard";

const params = new URLSearchParams(location.search);
const QUICK = params.has("quick");
const FACE_STEADY_MS = 1000; // a face must be visible this long before a first calibration starts by itself
const MAPPING_ACK_MS = 600; // no "error" event within this time means set_mapping was applied
const TOAST_MS = 6000;
const DONE_CARD_MS = 3200; // "CALIBRATION DONE" stays this long before the dashboard comes back
const CUSTOM_MOVE = "nod_up"; // the calibration's last move: the engine trains its own model on the nods (put on X)

type Screen = "intro" | "pick" | "dash";

export default function App() {
  const [coach, setCoach] = useState<CoachResult | null>(null);
  const [coachBusy, setCoachBusy] = useState(false);
  const [captainSteps, setCaptainSteps] = useState<string[]>([]); // what the Captain is doing, live
  const [captainUndo, setCaptainUndo] = useState<CaptainUndo | null>(null);
  const [applied, setApplied] = useState<Mapping | null>(null); // last mapping this page knows was applied
  const [mappingStatus, setMappingStatus] = useState<MappingStatus>({ errors: [], applied: false });
  const [toast, setToast] = useState<string | null>(null);
  const [screen, setScreen] = useState<Screen>("intro"); // the intro plays on every page load (and on REPLAY INTRO)
  const picked = useRef(false); // a profile was chosen on this page: replaying the intro returns to the dashboard
  const [panel, setPanel] = useState<TabId | null>(null); // the open Anchor page
  const loading = useRef<string | null>(null); // the profile asked for and not loaded yet
  const [loadedFor, setLoadedFor] = useState<string | null>(null); // the profile this page loaded
  const [doneAt, setDoneAt] = useState(-Infinity);
  const [, rerender] = useState(0);
  const pending = useRef<number | undefined>(undefined); // timer of a set_mapping waiting for error-or-silence
  const faceSince = useRef<number | null>(null);
  const autoSent = useRef(false);
  const [entrance, setEntrance] = useState(0); // bumped when the dashboard appears: replays its entrance
  const calMode = useRef<CalMode>(QUICK ? "quick" : "full"); // the running (or last) calibration
  const [breathResult, setBreathResult] = useState<BreathResult | null>(null);
  const [customResult, setCustomResult] = useState<CustomResult | null>(null); // the nod the calibration taught
  const [faceId, setFaceId] = useState<FaceIdResult | null>(null); // Face ID learned during this calibration
  const [profiles, setProfiles] = useState<Record<string, string[]>>({});
  const sendRef = useRef<(cmd: Command) => void>(() => {});
  const [voice, setVoice] = useSetting("voice");
  const [clicks, setClicks] = useSetting("clicks");
  const [options, setOptions] = useOptions();
  const refreshProfiles = useCallback(() => void fetchProfiles().then(setProfiles), []);
  const teachRef = useRef<ReturnType<typeof useTeachFlow> | null>(null);
  const playerRef = useRef("guest");
  const pauseClock = useRef(new HoldClock());
  const main = useRef<HTMLElement>(null);

  const onEvent = useCallback((msg: EventMsg) => {
    const data = msg.data;
    if (msg.name === "gesture_trained" && data.calibration) {
      // The nod from the calibration's last step was trained: its accuracy for the "done" card.
      setCustomResult({ name: String(data.name), accuracy: typeof data.accuracy === "number" ? data.accuracy : null });
      return;
    }
    if (teachRef.current?.onEvent(msg, playerRef.current)) return;
    if (msg.name === "profile_deleted" || msg.name === "profiles_reset") {
      const deleted = Array.isArray(data.deleted) ? data.deleted.length : 0;
      setToast(msg.name === "profile_deleted" ? `Deleted ${String(data.player)}. You're on Default now.`
        : `Reset: deleted ${deleted} profile${deleted === 1 ? "" : "s"} and every Face ID.`);
      switchRef.current();                         // back to the profile screen, with the list refreshed
      return;
    }
    if (msg.name === "face_id_forgotten") {
      setToast(data.had ? "Face ID is off for this profile: anyone can control it. Recalibrate to learn your face again." : "This profile had no Face ID.");
      return;
    }
    if (msg.name === "face_id_done") {
      if (!data.saved && data.reason && data.reason !== "cancelled") setToast(String(data.reason));
      const released = Array.isArray(data.released) ? data.released.map(String) : [];
      if (data.saved && released.length) setToast(`Your face was also locked to ${released.join(", ")}; Face ID is now only on this profile.`);
      setFaceId({ saved: Boolean(data.saved), reason: String(data.reason ?? "") });
      return;
    }
    if (msg.name === "breath_calibration_done") {
      // Comes after the face steps when a breath sensor is attached, or alone from "Measure my breath".
      setBreathResult({ puff: Number(data.max_puff_mv ?? 0), sip: Number(data.max_sip_mv ?? 0) });
      setDoneAt(performance.now());
      return;
    }
    if (msg.name === "calibration_done") {
      setBreathResult(null);
      setCustomResult(Number(data.nod_takes ?? 0) >= 2 ? { name: CUSTOM_MOVE, accuracy: null } : null);
      setDoneAt(performance.now());
      return;
    }
    if (msg.name === "captain_step") {
      const text = String(data.text ?? "");
      setCaptainSteps((steps) => (data.start ? [text] : [...steps, text]));
      return;
    }
    if (msg.name === "coach_result") {
      setCoach(data as unknown as CoachResult);
      setCoachBusy(false);
      setPanel("captain"); // show the proposal where it can be accepted
    } else if (msg.name === "profile_loaded") {
      const player = String(data.player);
      if (loading.current === player) {
        loading.current = null;
        setLoadedFor(player); // an uncalibrated profile now starts its full setup once a face is steady
      }
      setApplied(null);
      setCoach(null);
      setMappingStatus({ errors: [], applied: false });
    } else if (msg.name === "profile_reloaded") {
      setToast(`Applied your edits to ${String(data.file)}`);
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
  }, []);

  const { state, frame, connection, send: rawSend } = useHelmSocket(onEvent);

  const send = useCallback(
    (cmd: Command) => {
      if (cmd.cmd === "coach_build" || cmd.cmd === "coach_review" || cmd.cmd === "coach_ask") {
        setCoachBusy(true);
        setCoach(null);
        setCaptainSteps([]);
      }
      if (cmd.cmd === "calibrate") {
        calMode.current = cmd.mode;
        setFaceId(null); // Face ID (named profiles) reports after this calibration's head-movement steps
      }
      rawSend(cmd);
    },
    [rawSend],
  );

  sendRef.current = send;
  const teach = useTeachFlow(send);
  teachRef.current = teach;
  if (state) playerRef.current = state.profile.player;
  const teaching = teach.flow !== null && (teach.flow.stage === "face" || teach.flow.stage === "move");
  useSpokenPrompts(state, voice, (p) => (teaching && teach.flow ? spokenTake(p, teach.flow.name) : undefined));
  useFireClicks(state, clicks);

  useEffect(() => {
    if (connection === "open") refreshProfiles();
  }, [connection, refreshProfiles]);

  const pick = useCallback(
    (player: string) => {
      teach.close();
      setPanel(null);
      autoSent.current = false;
      faceSince.current = null;
      loading.current = player;
      setLoadedFor(null);
      send({ cmd: "load_profile", player, game: state?.profile.game ?? "SuperTuxKart" });
      picked.current = true;
      setScreen("dash");
      setEntrance((n) => n + 1);
    },
    [send, state?.profile.game, teach],
  );

  const closePanel = useCallback(() => setPanel(null), []); // stable: the open page focuses Close once
  const switchRef = useRef<() => void>(() => {});

  const switchProfile = useCallback(() => {
    setPanel(null);
    teach.close();
    refreshProfiles();
    setScreen("pick");
  }, [refreshProfiles, teach]);
  switchRef.current = switchProfile;

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

  // A profile with no calibration starts its full setup by itself once a face has been steady for a second.
  useEffect(() => {
    if (!state || screen !== "dash" || autoSent.current || connection !== "open") return;
    if (loadedFor === null || state.profile.player !== loadedFor) return;
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
  }, [state, connection, send, screen, loadedFor]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), TOAST_MS);
    return () => window.clearTimeout(t);
  }, [toast]);

  const endIntro = useCallback(() => {
    setScreen(picked.current ? "dash" : "pick");
    if (picked.current) setEntrance((n) => n + 1);
  }, []);

  const now = performance.now();
  const showingDone = now - doneAt < DONE_CARD_MS && !state?.progress;
  useEffect(() => {
    if (doneAt === -Infinity) return;
    const t = window.setTimeout(() => rerender((n) => n + 1), DONE_CARD_MS + 50); // re-render once it has passed
    return () => window.clearTimeout(t);
  }, [doneAt]);

  const calibrating = Boolean(state?.progress) && !teaching;
  const track = useCalibrationTrack(state, calibrating);

  // Focus mode: what is in front of the dashboard, and whether the big camera shows under it.
  let card: JSX.Element | null = null;
  let withCamera = true;
  if (state?.progress && teaching) card = <Wizard progress={state.progress} flow={teach.flow} />;
  else if (state?.progress)
    card = (
      <CalibrationCard
        state={state}
        progress={state.progress}
        mode={calMode.current}
        track={track}
        onSkip={calMode.current === "full" && !state.progress.step.startsWith("breath") ? () => send({ cmd: "calibrate", mode: "quick" }) : undefined}
      />
    );
  else if (state && showingDone)
    card = <CalibrationDone state={state} mode={calMode.current} track={track} breath={breathResult} custom={calMode.current === "full" ? customResult : null}
      faceId={calMode.current === "full" ? faceId : null} />;
  else if (state && teach.flow) {
    withCamera = teach.flow.stage === "ready_face";
    card = (
      <TeachPanel
        state={state}
        flow={teach.flow}
        hasFace={teach.hasFace(state.profile.player)}
        voice={voice}
        begin={teach.begin}
        go={teach.go}
        offer={teach.offer}
        close={teach.close}
        mapping={state.mapping ?? applied}
        apply={applyMapping}
      />
    );
  }
  const focus = screen === "dash" && card !== null;
  const front = focus || (screen === "dash" && panel !== null);

  useEffect(() => {
    main.current?.toggleAttribute("inert", front); // React 18 has no inert prop
  }, [front, screen]);

  const offline = connection !== "open";
  const lost = (
    <div className="lost paper-card" role="alert">
      <h2 className="title">can't reach helm</h2>
      <p>
        Make sure <code>python -m helm</code> is running. This page keeps trying{MOCK ? "" : " and will reconnect by itself"}.
      </p>
    </div>
  );
  const toastEl = toast && (
    <button className="toast paper-card" role="alert" onClick={() => setToast(null)}>
      {toast}
    </button>
  );
  const intro = screen === "intro" && <Intro camera={frame !== null} face={state?.face ?? false} engine={connection === "open"} onDone={endIntro} />;

  if (!state || !picked.current) {
    return (
      <>
        {screen !== "intro" && <ProfilePicker profiles={profiles} ready={Boolean(state) && !offline} onPick={pick} state={state} frame={frame} send={send} />}
        {intro}
        {screen !== "intro" && offline && connection === "closed" && lost}
        {toastEl}
      </>
    );
  }
  if (screen === "pick") {
    return (
      <>
        <ProfilePicker profiles={profiles} ready={!offline} onPick={pick} state={state} frame={frame} send={send} />
        {offline && lost}
        {toastEl}
      </>
    );
  }

  const mapping = state.mapping ?? applied;
  const pauseGesture = mapping?.pause?.gesture;
  const pauseHeld = pauseGesture
    ? pauseClock.current.seconds(state.face ? state.activations?.[pauseGesture] ?? 0 : 0, state.thresholds?.[pauseGesture]?.on ?? 0.85, now)
    : 0;
  const rows = buildRows(state, mapping, pauseHeld);
  const busy = state.progress !== null || teach.flow !== null;
  const openTeach = () => {
    setPanel(null);
    teach.offer();
  };

  const pages: AnchorPage[] = [
    {
      id: "mapping",
      label: "Mapping",
      blurb: "Which move presses which button",
      body: <MappingView mapping={mapping} catalog={state.catalog} status={mappingStatus} apply={applyMapping} send={send} />,
    },
    {
      id: "captain",
      label: "Captain",
      blurb: "Let the AI map your moves",
      badge: coachBusy ? "…" : coach ? "NEW" : undefined,
      body: <CoachPanel state={state} send={send} result={coach} busy={coachBusy} steps={captainSteps} apply={applyMapping}
        undo={captainUndo} setUndo={setCaptainUndo} />,
    },
    {
      id: "moves",
      label: "Your moves",
      blurb: "Moves Helm learned from you",
      badge: state.gestures.learned.length ? String(state.gestures.learned.length) : undefined,
      body: <GestureRecorder state={state} send={send} busy={busy} onTeach={openTeach} mapping={mapping} apply={applyMapping} />,
    },
    {
      id: "profile",
      label: "Profile",
      blurb: "Who's playing · switch · save",
      body: <ProfileCard state={state} send={send} onSwitch={switchProfile} busy={busy} />,
    },
    {
      id: "dev",
      label: "Dev",
      blurb: "Debug recordings for the team",
      badge: state.dev?.recording ? "REC" : undefined,
      body: <DevControls state={state} send={send} />,
    },
  ];
  const openPage = pages.find((p) => p.id === panel);

  return (
    <>
      <main
        ref={main}
        className={`screen${offline ? " dimmed" : ""}${front ? " behind" : ""}${entrance ? (entrance % 2 ? " enter-a" : " enter-b") : ""}`}
        aria-hidden={offline || front || screen === "intro" || undefined}
      >
        <TopBar
          busy={busy}
          onRecalibrate={() => {
            setPanel(null);
            send({ cmd: "calibrate", mode: QUICK ? "quick" : "full" });
          }}
        />
        <div className="camera-row">
          <Fleet />
          <section aria-label="Camera">
            <CameraView frame={frame} state={state} size="hero" />
          </section>
        </div>
        <div className="play-row">
          <section className="moves-col" aria-label="Your moves">
            <MovesPanel state={state} rows={rows} onTeach={openTeach} teachBusy={busy} />
            <MessageBox state={state} mapping={mapping} doneAt={doneAt} hold={(mapping?.pause?.hold_ms ?? 2000) / 1000} />
          </section>
          <div className="pad-col">
            <section className="paper-card controller-card" aria-label="The controller">
              <ControllerCard state={state} mapping={mapping} />
            </section>
            <SteeringCard state={state} mapping={mapping} apply={applyMapping} send={send} />
          </div>
        </div>
        <Anchor pages={pages} open={setPanel} />
        <div className="foot-row">
          <StatStamps state={state} />
          <OptionsBar
            options={options}
            set={setOptions}
            sound={voice || clicks}
            setSound={(on) => {
              setVoice(on);
              setClicks(on);
            }}
            onReplayIntro={() => setScreen("intro")}
          />
        </div>
      </main>
      {focus && (
        <div className="layer stage-layer">
          <div className="stage">
            <div className="instructions">
              <span className="instructions-label">instructions</span>
              {card}
            </div>
            {withCamera && <CameraView frame={frame} state={state} size="stage" hint={calibrating ? cameraHint(state.progress) : null} />}
          </div>
        </div>
      )}
      {!focus && openPage && <AnchorPanel page={openPage} close={closePanel} />}
      {intro}
      {offline && lost}
      {toastEl}
    </>
  );
}
