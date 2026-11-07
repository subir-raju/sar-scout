import { useState } from "react";
import { HOUR, decide, scoreParts } from "../lib/engine";
import { cap } from "../lib/format";
import { PLACES, START } from "../lib/scenarios";
import { HAZARDS } from "../lib/types";
import type { Policy } from "../lib/types";
import { Verdict } from "./Verdict";

const NOW = START;

/* The seven checks, in the order the code runs them. */
function rulesFor(p: Policy): string[] {
  return [
    `Is the score at least ${p.min_score}?`,
    "Is it outside every no-go zone?",
    "Is this kind of event on the list?",
    "Is the autonomy level above 0?",
    `Is the score high enough to go alone (${p.level === 1 ? p.auto_min_score : p.min_score} or more)?`,
    `Is today's limit of ${p.auto_daily_cap} still open?`,
    "Then order it without asking.",
  ];
}

function Bar({ label, note, value, max, shown }: { label: string; note: string; value: number; max: number; shown: string }) {
  return (
    <li className="factor">
      <div className="factor-top"><span>{label}</span><strong>{shown}</strong></div>
      <div className="bar" aria-hidden="true"><div style={{ width: `${Math.min(100, (value / max) * 100)}%` }} /></div>
      <p className="fine">{note}</p>
    </li>
  );
}

export function Playground({ policy }: { policy: Policy }) {
  const [place, setPlace] = useState("p:0");
  const [hazard, setHazard] = useState("earthquake");
  const [severity, setSeverity] = useState(4);
  const [age, setAge] = useState(3);
  const [imaged, setImaged] = useState(false);
  const [used, setUsed] = useState(0);

  const [kind, index] = place.split(":");
  const zone = kind === "z" ? policy.deny_zones[Number(index)] : undefined;
  const spot = zone
    ? { latitude: zone.latitude, longitude: zone.longitude }
    : { latitude: PLACES[Number(index)]?.lat ?? 0, longitude: PLACES[Number(index)]?.lon ?? 0 };

  const event = { ...spot, hazard, severity, observedAt: NOW - age * HOUR };
  const images = imaged ? [{ ...spot, takenAt: NOW - 20 * HOUR }] : [];
  const parts = scoreParts(event, NOW, images);
  const decision = decide(policy, { id: "try", hazard, ...spot }, parts.total, used);
  const rules = rulesFor(policy);

  return (
    <div className="try">
      <form className="try-in" onSubmit={(e) => e.preventDefault()}>
        <label className="field">Where
          <select value={place} onChange={(e) => setPlace(e.target.value)}>
            {PLACES.map((p, i) => <option key={p.name} value={`p:${i}`}>{p.name}</option>)}
            {policy.deny_zones.map((z, i) => <option key={z.name} value={`z:${i}`}>Inside {z.name}</option>)}
          </select>
        </label>
        <label className="field">Kind of event
          <select value={hazard} onChange={(e) => setHazard(e.target.value)}>
            {HAZARDS.map((h) => <option key={h} value={h}>{cap(h)}</option>)}
          </select>
        </label>
        <label className="field"><span>Severity: <output>{severity}</output> out of 5</span>
          <input type="range" min={1} max={5} step={1} value={severity} onChange={(e) => setSeverity(Number(e.target.value))} />
        </label>
        <label className="field"><span>Hours since it happened: <output>{age}h</output></span>
          <input type="range" min={0} max={72} step={1} value={age} onChange={(e) => setAge(Number(e.target.value))} />
        </label>
        <label className="field"><span>Automatic orders already used today: <output>{used}</output></span>
          <input type="range" min={0} max={6} step={1} value={used} onChange={(e) => setUsed(Number(e.target.value))} />
        </label>
        <label className="check-one">
          <input type="checkbox" checked={imaged} onChange={(e) => setImaged(e.target.checked)} />
          This area was already imaged 20 hours ago
        </label>
      </form>

      <div className="try-out" aria-live="polite">
        <ul className="factors">
          <Bar label="Severity" value={parts.severity} max={8} shown={`× ${parts.severity}`}
            note="Doubles with every step up: severity 3 counts twice as much as 2." />
          <Bar label="Radar suits this event" value={parts.suitability} max={1.3} shown={`× ${parts.suitability}`}
            note="A judgement call. Radar sees through cloud, so floods score highest." />
          <Bar label="Freshness" value={parts.freshness} max={1} shown={`× ${parts.freshness.toFixed(2)}`}
            note="Halves roughly every 33 hours. Old news is worth less." />
          <Bar label="Not imaged already" value={parts.stale} max={1} shown={`× ${parts.stale}`}
            note="A recent image of the same area cuts the score to a fifth." />
        </ul>

        <div className={`result result--${decision.action}`}>
          <div className="result-top">
            <span className="score">{parts.total.toFixed(2)}</span>
            <Verdict action={decision.action} />
          </div>
          <p>{decision.reason}</p>
        </div>

        <ol className="rules">
          {rules.map((text, i) => {
            const n = i + 1;
            const state = n < decision.rule ? "passed" : n === decision.rule ? "decided" : "skipped";
            return <li key={n} className={`rule rule--${state}`}>{text}</li>;
          })}
        </ol>
      </div>
    </div>
  );
}