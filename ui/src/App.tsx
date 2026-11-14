// OWNER: P4
// One page, styled as a single green LCD screen (docs/SPEC.md section 9). ?overlay=1 is the small window beside
// the game; ?quick=1 makes calibration a quick one; ?mock=1 runs with no backend.
// While calibration or teaching is on screen, everything the player does not need is blurred and unreachable,
// and a card over the moves panel is the only thing to look at.
import { useCallback, useEffect, useRef, useState } from "react";
import type { CoachResult, Command, EventMsg, Mapping, MappingStatus } from "./types";
import { MOCK, fetchProfiles, useHelmSocket } from "./useHelmSocket";
import { useFireClicks, useSetting, useSpokenPrompts } from "./feedback";
import { HoldClock, buildRows, holdSeconds } from "./moves";
import { useTeachFlow } from "./teach";
import { JUDGE, ProfileCard } from "./components/ProfileCard";
import { Blur } from "./components/Blur";
import { CalibrationCard, CalibrationDone, cameraHint, useCalibrationTrack, type CalMode, type BreathResult } from "./components/CalibrationCard";
import { DevControls } from "./components/DevControls";
import { CameraView, StatStamps } from "./components/CameraView";
import { CoachPanel } from "./components/CoachPanel";
import { GestureRecorder } from "./components/GestureRecorder";
import { Intro } from "./components/Intro";
import { MappingView } from "./components/MappingView";
import { MessageBox } from "./components/MessageBox";
import { ControllerCard, MovesPanel } from "./components/MovesPanel";
import { OptionsBar, useOptions } from "./components/OptionsBar";
import { SetupTabs, useSetupTab } from "./components/SetupTabs";
import { Header, StatusStamp, statusOf } from "./components/StatusBar";
import { TeachPanel } from "./components/TeachPanel";
import { Wizard } from "./components/Wizard";

const params = new URLSearchParams(location.search);
const QUICK = params.has("quick");
const FACE_STEADY_MS = 1000; // a face must be visible this long before calibration starts by itself
const MAPPING_ACK_MS = 600; // no "error" event within this time means set_mapping was applied
const TOAST_MS = 6000;
const DONE_CARD_MS = 2200; // "CALIBRATION DONE" stays this long before the dashboard unlocks

export default function App() {
  const [coach, setCoach] = useState<CoachResult | null>(null);
  const [coachBusy, setCoachBusy] = useState(false);
  const [applied, setApplied] = useState<Mapping | null>(null); // last mapping this page knows was applied
  const [mappingStatus, setMappingStatus] = useState<MappingStatus>({ errors: [], applied: false });
  const [toast, setToast] = useState<string | null>(null);
  const [intro, setIntro] = useState(true); // the intro plays on every page load (and on REPLAY INTRO)
  const [doneAt, setDoneAt] = useState(-Infinity);
  const [, rerender] = useState(0);
  const pending = useRef<number | undefined>(undefined); // timer of a set_mapping waiting for error-or-silence
  const faceSince = useRef<number | null>(null);
  const autoSent = useRef(false);
  const [entrance, setEntrance] = useState(0); // bumped when the intro ends: replays the dashboard's entrance
  const calMode = useRef<CalMode>(QUICK ? "quick" : "full"); // the running (or last) calibration
  const [breathResult, setBreathResult] = useState<BreathResult | null>(null);
  const offerTeach = useRef(false); // offer "teach a move" once the done card is gone
  const [profiles, setProfiles] = useState<Record<string, string[]>>({});
  const visitorPending = useRef(false); // "Next player" waits for the guest profile before calibrating
  const sendRef = useRef<(cmd: Command) => void>(() => {});
  const [voice, setVoice] = useSetting("voice");
  const [clicks, setClicks] = useSetting("clicks");
  const [options, setOptions] = useOptions();
  const refreshProfiles = useCallback(() => void fetchProfiles().then(setProfiles), []);
  const teachRef = useRef<ReturnType<typeof useTeachFlow> | null>(null);
  const playerRef = useRef("guest");
  const [tab, setTab] = useSetupTab();
  const heading = useRef<HTMLHeadingElement>(null);
  const pauseClock = useRef(new HoldClock());

  const onEvent = useCallback((msg: EventMsg) => {
    const data = msg.data;
    if (teachRef.current?.onEvent(msg, playerRef.current)) return;
    if (msg.name === "breath_calibration_done") {
      // Comes after the face steps when a breath sensor is attached, or alone from "Measure my breath".
      setBreathResult({ puff: Number(data.max_puff_mv ?? 0), sip: Number(data.max_sip_mv ?? 0) });
      setDoneAt(performance.now());
      return;
    }
    if (msg.name === "calibration_done") {
      setBreathResult(null);
      setDoneAt(performance.now());
      // Right after a full calibration is when almost everyone wants their own move: offer it in place.
      offerTeach.current = data.mode === "full" && playerRef.current !== JUDGE;
      return;
    }
    if (msg.name === "coach_result") {
      setCoach(data as unknown as CoachResult);
      setCoachBusy(false);
      setTab("coach"); // show the proposal where it can be accepted
    } else if (msg.name === "profile_loaded") {
      if (visitorPending.current && data.player === JUDGE) {
        visitorPending.current = false;
        calMode.current = "quick";
        sendRef.current({ cmd: "calibrate", mode: "quick" });
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
  }, [setTab]);

  const { state, frame, connection, send: rawSend } = useHelmSocket(onEvent);

  const send = useCallback(
    (cmd: Command) => {
      if (cmd.cmd === "coach_build" || cmd.cmd === "coach_review") setCoachBusy(true);
      if (cmd.cmd === "calibrate") calMode.current = cmd.mode;
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

  const nextPlayer = useCallback(() => {
    if (!state) return;
    const games = profiles[JUDGE] ?? [];
    const game = games.includes(state.profile.game) ? state.profile.game : games[0];
    if (!game) return;
    teach.close();
    visitorPending.current = true;
    send({ cmd: "load_profile", player: JUDGE, game });
  }, [state, profiles, send, teach]);

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

  // First calibration starts by itself once a face has been visible for a second, after the intro.
  useEffect(() => {
    if (!state || intro || autoSent.current || connection !== "open") return;
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
  }, [state, connection, send, intro]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), TOAST_MS);
    return () => window.clearTimeout(t);
  }, [toast]);

  const endIntro = useCallback(() => {
    setIntro(false);
    setEntrance((n) => n + 1); // the dashboard slides in, section by section
    window.setTimeout(() => heading.current?.focus(), 0); // screen readers start at "your moves -> the buttons"
  }, []);

  // Replay runs the whole intro again; it never recalibrates.
  const replayIntro = useCallback(() => setIntro(true), []);

  // The "CALIBRATION DONE" card ends: unlock the dashboard and put focus on the moves, or offer a new move.
  const now = performance.now();
  const showingDone = now - doneAt < DONE_CARD_MS && !state?.progress;
  const wasShowingDone = useRef(false);
  useEffect(() => {
    if (wasShowingDone.current && !showingDone) {
      if (offerTeach.current) teachRef.current?.offer();
      else heading.current?.focus();
      offerTeach.current = false;
    }
    wasShowingDone.current = showingDone;
  }, [showingDone]);
  useEffect(() => {
    if (doneAt === -Infinity) return;
    const t = window.setTimeout(() => rerender((n) => n + 1), DONE_CARD_MS + 50); // re-render once it has passed
    return () => window.clearTimeout(t);
  }, [doneAt]);

  const teaching = teach.flow !== null && (teach.flow.stage === "face" || teach.flow.stage === "move");
  const calibrating = Boolean(state?.progress) && !teaching;
  const track = useCalibrationTrack(state, calibrating);
  const status = statusOf(state, connection === "open", teaching);

  const offline = connection !== "open";
  const lost = (
    <div className="lost paper-card" role="alert">
      <h2 className="title">can't reach helm</h2>
      <p>
        Make sure <code>python -m helm</code> is running. This page keeps trying{MOCK ? "" : " and will reconnect by itself"}.
      </p>
    </div>
  );
  if (!state)
    return (
      <main className="screen">
        <StatusStamp status={status} />
        {offline && connection === "closed" ? lost : <p className="starting">starting helm…</p>}
      </main>
    );

  const mapping = state.mapping ?? applied;
  const hold = holdSeconds(mapping);
  const pauseGesture = mapping?.pause?.gesture;
  const pauseHeld = pauseGesture
    ? pauseClock.current.seconds(state.face ? state.activations?.[pauseGesture] ?? 0 : 0, state.thresholds?.[pauseGesture]?.on ?? 0.85, now)
    : 0;
  const rows = buildRows(state, mapping, pauseHeld);

  let card: JSX.Element | null = null;
  if (state.progress && teaching) card = <Wizard progress={state.progress} flow={teach.flow} />;
  else if (state.progress)
    card = (
      <CalibrationCard
        state={state}
        progress={state.progress}
        mode={calMode.current}
        track={track}
        onSkip={calMode.current === "full" && !state.progress.step.startsWith("breath") ? () => send({ cmd: "calibrate", mode: "quick" }) : undefined}
      />
    );
  else if (showingDone) card = <CalibrationDone state={state} mode={calMode.current} track={track} breath={breathResult} />;
  else if (teach.flow)
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
        mapping={mapping}
        apply={applyMapping}
      />
    );
  const setup = card !== null;

  return (
    <>
      <main className={`screen${offline ? " dimmed" : ""}${entrance ? (entrance % 2 ? " enter-a" : " enter-b") : ""}`} aria-hidden={offline || intro || undefined}>
        <Header
          state={state}
          status={status}
          setup={setup}
          hold={hold}
          canSkip={calibrating && calMode.current === "full" && !state.progress?.step.startsWith("breath")}
          onNextPlayer={profiles[JUDGE]?.length ? nextPlayer : undefined}
          onPause={() => send({ cmd: "pause", on: !state.paused })}
          onRecalibrate={() => send({ cmd: "calibrate", mode: QUICK ? "quick" : "full" })}
          onSkip={() => send({ cmd: "calibrate", mode: "quick" })}
        />
        <section className="moves-section" aria-label="Your moves and the buttons">
          <div className="stack">
            <Blur on={setup} className="moves-body">
              <MovesPanel
                ref={heading}
                state={state}
                rows={rows}
                onTeach={teach.offer}
                teachBusy={setup}
                onMeasureBreath={() => send({ cmd: "calibrate", mode: "breath" })}
              />
              <MessageBox state={state} mapping={mapping} doneAt={doneAt} hold={hold} />
            </Blur>
            {card && <div className="card-slot">{card}</div>}
          </div>
        </section>
        <div className="bottom-row">
          <section className="camera-col" aria-label="Camera">
            <CameraView frame={frame} state={state} compact={false} hint={calibrating ? cameraHint(state.progress) : null} />
          </section>
          <Blur on={setup} as="section" className="paper-card controller-card">
            <ControllerCard state={state} mapping={mapping} />
          </Blur>
          <Blur on={setup}>
            <StatStamps state={state} />
          </Blur>
        </div>
        <OptionsBar
          options={options}
          set={setOptions}
          sound={voice || clicks}
          setSound={(on) => {
            setVoice(on);
            setClicks(on);
          }}
          onReplayIntro={replayIntro}
        />
        <Blur on={setup}>
          <SetupTabs
            tab={tab}
            setTab={setTab}
            tabs={[
              { id: "mapping", label: "Mapping", body: <MappingView mapping={mapping} catalog={state.catalog} status={mappingStatus} apply={applyMapping} send={send} /> },
              {
                id: "coach",
                label: "Coach",
                badge: coachBusy ? "…" : coach ? "NEW" : undefined,
                body: <CoachPanel state={state} send={send} result={coach} busy={coachBusy} apply={applyMapping} />,
              },
              {
                id: "moves",
                label: "Your moves",
                badge: state.gestures.learned.length ? String(state.gestures.learned.length) : undefined,
                body: <GestureRecorder state={state} send={send} busy={setup} onTeach={teach.offer} mapping={mapping} apply={applyMapping} />,
              },
              { id: "profile", label: "Profile", body: <ProfileCard state={state} send={send} profiles={profiles} /> },
              { id: "dev", label: "Dev", badge: state.dev?.recording ? "REC" : undefined, body: <DevControls state={state} send={send} /> },
            ]}
          />
        </Blur>
      </main>
      {intro && <Intro camera={frame !== null} face={state.face} engine={connection === "open"} onDone={endIntro} />}
      {offline && lost}
      {toast && (
        <button className="toast paper-card" role="alert" onClick={() => setToast(null)}>
          {toast}
        </button>
      )}
    </>
  );
}
