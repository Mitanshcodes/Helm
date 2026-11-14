// OWNER: P4
// The mapping editor, a read-only table (used by the Captain) and a raw JSON box for advanced edits.
import { useEffect, useState } from "react";
import type { Catalog, Mapping, MappingStatus, Send } from "../types";
import { MappingEditor } from "./MappingEditor";

const label = (name: string) => name.replace(/_/g, " ");

export function MappingTable({ mapping }: { mapping: Mapping }) {
  const rows: [string, string, string][] = [
    ...(mapping.axes ?? []).map((a): [string, string, string] => [`head ${a.source}`, a.target, a.invert ? "axis, inverted" : "axis"]),
    ...(mapping.triggers ?? []).map((t): [string, string, string] => [label(t.source), t.target, "analog"]),
    ...(mapping.buttons ?? []).map((b): [string, string, string] => [label(b.gesture), b.target, b.mode]),
    ...Object.entries(mapping.auto ?? {}).map(([target, v]): [string, string, string] => ["always", target, `held at ${v}`]),
  ];
  if (mapping.pause) rows.push([label(mapping.pause.gesture), "pause", `hold ${mapping.pause.hold_ms / 1000} s`]);
  return (
    <table>
      <thead>
        <tr>
          <th>Input</th>
          <th>Output</th>
          <th>Mode</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([input, target, mode], i) => (
          <tr key={i}>
            <td>{input}</td>
            <td>{target.toUpperCase()}</td>
            <td>{mode}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function MappingView(props: { mapping: Mapping | null; catalog?: Catalog; status: MappingStatus; apply: (m: Mapping) => void; send: Send }) {
  const { mapping, catalog, status, apply, send } = props;
  const [text, setText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);

  useEffect(() => {
    if (mapping) setText(JSON.stringify(mapping, null, 2));
  }, [mapping]);

  const submit = () => {
    try {
      const parsed: unknown = JSON.parse(text);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) throw new Error("A mapping is a JSON object");
      setParseError(null);
      apply(parsed as Mapping);
    } catch (e) {
      setParseError(e instanceof Error ? e.message : "Not valid JSON");
    }
  };

  return (
    <section className="tool">
      {mapping ? (
        <MappingEditor mapping={mapping} catalog={catalog} status={status} apply={apply} send={send} />
      ) : (
        <p className="muted">Build a mapping with the Captain, or paste one below.</p>
      )}
      <details className="json-edit">
        <summary>Edit as JSON</summary>
        <textarea value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} rows={10} aria-label="Mapping JSON" />
        <div className="line">
          <button className="btn primary" disabled={!text.trim()} onClick={submit}>
            Apply
          </button>
          <button className="btn" onClick={() => send({ cmd: "save_profile" })}>Save profile</button>
          {status.applied && !parseError && <span className="result">Applied</span>}
        </div>
        {parseError && <p className="notice">{parseError}</p>}
      </details>
    </section>
  );
}
