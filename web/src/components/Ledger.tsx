import { useState } from "react";
import { firstBroken } from "../lib/audit";
import type { AuditEntry, AuditRecord } from "../lib/audit";

type Tamper = { kind: "edit" | "delete"; index: number } | null;


function altered(entries: AuditEntry[], tamper: Tamper): AuditEntry[] {
  if (!tamper || tamper.index >= entries.length) return entries;
  if (tamper.kind === "delete") return entries.filter((_, i) => i !== tamper.index);
  return entries.map((entry, i) => {
    if (i !== tamper.index) return entry;
    const record: AuditRecord =
      typeof entry.record.action === "string"
        ? { ...entry.record, action: entry.record.action === "deny" ? "auto_submit" : "deny" }
        : { ...entry.record, event: "someone-else" };
    return { ...entry, record };
  });
}

function describe(r: AuditRecord): string {
  const event = String(r.event);
  if (r.type === "decision") return `${event}: ${String(r.action).replace("_", " ")}`;
  if (r.type === "human_approved") return `${event}: a person approved`;
  return `${event}: a person declined`;
}

export function Ledger({ entries }: { entries: AuditEntry[] }) {
  const [tamper, setTamper] = useState<Tamper>(null);
  const [pick, setPick] = useState(0);

  const shown = altered(entries, tamper);
  const bad = firstBroken(shown);
  const index = Math.min(pick, Math.max(0, entries.length - 1));

  if (entries.length === 0) {
    return <p className="empty"></p>;
  }

  return (
    <div className="ledger">
      <div className={`seal ${bad === -1 ? "seal--ok" : "seal--bad"}`} role="status">
        {bad === -1
          ? `Chain intact: all ${shown.length} entries check out.`
          : `Chain broken at entry ${bad + 1}.`}
      </div>

      <div className="tamper">
        <label className="field">
          <select value={index} onChange={(e) => setPick(Number(e.target.value))}>
            {entries.map((e, i) => <option key={e.hash} value={i}>#{i + 1}  {describe(e.record)}</option>)}
          </select>
        </label>
        <button type="button" className="btn" onClick={() => setTamper({ kind: "edit", index })}>Rewrite it</button>
        <button type="button" className="btn" onClick={() => setTamper({ kind: "delete", index })}>Delete it</button>
        <button type="button" className="btn" disabled={!tamper} onClick={() => setTamper(null)}>Put it back</button>
      </div>

      <ol className="chain">
        {shown.map((entry, i) => (
          <li key={entry.hash + i} className={bad !== -1 && i >= bad ? "link link--bad" : "link"}>
            <span className="num">#{i + 1}</span>
            <span className="what">{describe(entry.record)}</span>
            <code title="This entry's fingerprint">{entry.hash.slice(0, 10)}</code>
            <code className="prev" title="The fingerprint of the entry before it">after {entry.prev.slice(0, 10)}</code>
          </li>
        ))}
      </ol>

  
    </div>
  );
}