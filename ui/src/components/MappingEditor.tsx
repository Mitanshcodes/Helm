// OWNER: P4
// Manual mapping: every pad input with a gesture picker and a mode, sticks, pause, and how hard each gesture
// must be made. Edits a local draft; "Apply" sends it to Helm, which validates it.
import { useEffect, useMemo, useState } from "react";
import {
  ALWAYS, FACE_BUTTONS, MORE_BUTTONS, STICK_AXES, TRIGGERS, bindingOf, gestureLabel, setAxis, setBinding, setPause,
  setThreshold, targetLabel, type Mode,
} from "../mappingEdit";
import type { Catalog, Mapping, MappingStatus, Send } from "../types";

const GROUPS: [string, string][] = [
  ["face", "Face"],
  ["learned", "Your moves"],
  ["breath", "Breath"],
];
const HEAD: [string, string][] = [
  ["", "Nothing"],
  ["yaw", "Turn head left / right"],
  ["pitch", "Nod chin up / down"],
  ["roll", "Tilt head to a shoulder"],
];
const HOLDS = [1000, 1500, 2000, 3000];

function GesturePicker(props: { value: string; catalog?: Catalog; allowAlways: boolean; label: string; onChange: (v: string) => void }) {
  const { value, catalog, allowAlways, label, onChange } = props;
  const known = new Set((catalog?.gestures ?? []).map((g) => g.name));
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}>
      <option value="">Nothing</option>
      {allowAlways && <option value={ALWAYS}>Always on</option>}
      {GROUPS.map(([group, title]) => {
        const items = (catalog?.gestures ?? []).filter((g) => g.group === group);
        if (items.length === 0) return null;
        return (
          <optgroup key={group} label={title}>
            {items.map((g) => (
              <option key={g.name} value={g.name} disabled={!g.usable && g.name !== value}>
                {g.label}
                {g.usable ? "" : " (weak for you)"}
              </option>
            ))}
          </optgroup>
        );
      })}
      {value && value !== ALWAYS && !known.has(value) && <option value={value}>{value.replace(/_/g, " ")}</option>}
    </select>
  );
}

function ModePicker(props: { value: Mode; trigger: boolean; disabled: boolean; label: string; onChange: (m: Mode) => void }) {
  const { value, trigger, disabled, label, onChange } = props;
  return (
    <select className="mode" value={value} disabled={disabled} onChange={(e) => onChange(e.target.value as Mode)} aria-label={label}>
      <option value="tap">Tap</option>
      <option value="hold">Hold</option>
      <option value="toggle">On / off</option>
      {trigger && <option value="analog">Analog</option>}
    </select>
  );
}

function Row(props: { target: string; draft: Mapping; catalog?: Catalog; setDraft: (m: Mapping) => void }) {
  const { target, draft, catalog, setDraft } = props;
  const trigger = target === "lt" || target === "rt";
  const b = bindingOf(draft, target);
  const action = catalog?.controls?.[target];
  const name = targetLabel(target);
  const badge = ["A", "B", "X", "Y"].includes(target) ? target : null;
  return (
    <div className={b.gesture ? "map-row" : "map-row empty"}>
      <div className="map-target">
        {badge ? <span className={`badge pad-${badge}`}>{badge}</span> : <span className="map-target-name">{name}</span>}
        {action && <span className="map-action">{action}</span>}
      </div>
      <GesturePicker
        value={b.gesture}
        catalog={catalog}
        allowAlways={trigger}
        label={`Gesture for ${name}`}
        onChange={(g) => setDraft(setBinding(draft, target, g, b.gesture ? b.mode : trigger ? "hold" : "tap", catalog))}
      />
      <ModePicker
        value={b.mode}
        trigger={trigger}
        disabled={!b.gesture || b.gesture === ALWAYS}
        label={`How ${name} is pressed`}
        onChange={(mode) => setDraft(setBinding(draft, target, b.gesture, mode, catalog))}
      />
    </div>
  );
}

export function MappingEditor(props: { mapping: Mapping; catalog?: Catalog; status: MappingStatus; apply: (m: Mapping) => void; send: Send }) {
  const { mapping, catalog, status, apply, send } = props;
  const [draft, setDraft] = useState<Mapping>(mapping);
  const original = JSON.stringify(mapping);
  const dirty = JSON.stringify(draft) !== original;

  useEffect(() => setDraft(JSON.parse(original) as Mapping), [original]); // a new mapping arrived from Helm

  const sensitivity = useMemo(
    () => Object.entries(draft.gestures ?? {}).filter(([, g]) => g.kind !== "breath" && typeof g.on === "number"),
    [draft],
  );
  const pause = draft.pause ?? null;

  return (
    <div className="mapping-editor">
      <div className="map-columns">
        <section className="map-section">
          <h3>Face buttons</h3>
          {FACE_BUTTONS.map((t) => <Row key={t} target={t} draft={draft} catalog={catalog} setDraft={setDraft} />)}
          <h3>Triggers</h3>
          {TRIGGERS.map((t) => <Row key={t} target={t} draft={draft} catalog={catalog} setDraft={setDraft} />)}
          <h3>Sticks</h3>
          {STICK_AXES.map((t) => {
            const axis = draft.axes?.find((a) => a.target === t);
            const action = catalog?.controls?.[t];
            return (
              <div key={t} className={axis ? "map-row" : "map-row empty"}>
                <div className="map-target">
                  <span className="map-target-name">{targetLabel(t)}</span>
                  {action && <span className="map-action">{action}</span>}
                </div>
                <select value={axis?.source ?? ""} onChange={(e) => setDraft(setAxis(draft, t, e.target.value, axis?.invert ?? false))} aria-label={`Head movement for ${targetLabel(t)}`}>
                  {HEAD.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
                </select>
                <label className="toggle invert">
                  <input type="checkbox" checked={axis?.invert ?? false} disabled={!axis} onChange={(e) => setDraft(setAxis(draft, t, axis!.source, e.target.checked))} />
                  <span>Invert</span>
                </label>
              </div>
            );
          })}
        </section>

        <section className="map-section">
          <h3>More buttons</h3>
          {MORE_BUTTONS.map((t) => <Row key={t} target={t} draft={draft} catalog={catalog} setDraft={setDraft} />)}
          <h3>Pause</h3>
          <div className={pause ? "map-row" : "map-row empty"}>
            <div className="map-target">
              <span className="map-target-name">Pause</span>
              <span className="map-action">and resume</span>
            </div>
            <GesturePicker value={pause?.gesture ?? ""} catalog={catalog} allowAlways={false} label="Pause gesture"
              onChange={(g) => setDraft(setPause(draft, g, pause?.hold_ms ?? 2000, catalog))} />
            <select className="mode" value={pause?.hold_ms ?? 2000} disabled={!pause} aria-label="Hold time"
              onChange={(e) => setDraft(setPause(draft, pause!.gesture, Number(e.target.value), catalog))}>
              {HOLDS.map((ms) => <option key={ms} value={ms}>hold {ms / 1000} s</option>)}
            </select>
          </div>
        </section>
      </div>

      {sensitivity.length > 0 && (
        <section className="map-section sensitivity">
          <h3>How hard each gesture must be made</h3>
          <p className="caption">Further right needs a bigger movement: fewer accidental presses.</p>
          <div className="sliders">
            {sensitivity.map(([name, g]) => (
              <label key={name} className="slider">
                <span>{gestureLabel(catalog, name)}</span>
                <input type="range" min={0.3} max={0.95} step={0.05} value={g.on} onChange={(e) => setDraft(setThreshold(draft, name, Number(e.target.value)))} />
                <b>{Math.round((g.on ?? 0) * 100)}%</b>
              </label>
            ))}
          </div>
        </section>
      )}

      <div className="map-footer">
        <button className="btn primary" disabled={!dirty} onClick={() => apply(draft)}>Apply</button>
        <button className="btn" disabled={!dirty} onClick={() => setDraft(JSON.parse(original) as Mapping)}>Undo changes</button>
        <button className="btn" onClick={() => send({ cmd: "save_profile" })}>Save profile</button>
        {dirty ? <span className="hint">Not applied yet</span> : status.applied ? <span className="result">Applied</span> : null}
      </div>
      {status.errors.map((e) => <p key={e} className="notice">{e}</p>)}
    </div>
  );
}
