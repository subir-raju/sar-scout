import { HAZARDS } from "../lib/types";
import type { Policy } from "../lib/types";
import { DEFAULT_POLICY } from "../lib/scenarios";
import { cap } from "../lib/format";

const LEVELS = [
  { value: 0, name: "Level 0", text: "Only recommends. A person approves everything." },
  { value: 1, name: "Level 1", text: "Orders alone only when the score is high." },
  { value: 2, name: "Level 2", text: "Orders alone anything above the minimum." },
] as const;


export function summarize(p: Policy): string {
  const refuse = `Anything scoring under ${p.min_score} is refused.`;
  const cap_ = `At most ${p.auto_daily_cap} automatic orders a day.`;
  if (p.level === 0) return `${refuse} Nothing is ordered without a person.`;
  const from = p.level === 1 ? p.auto_min_score : p.min_score;
  return `${refuse} From ${from} up it orders alone, if the kind of event is on the list. ${cap_}.`;
}

export function PolicyPanel({ policy, onChange }: { policy: Policy; onChange: (next: Policy) => void }) {
  const set = (patch: Partial<Policy>) => onChange({ ...policy, ...patch });
  const toggleHazard = (hazard: string) =>
    set({
      allow_hazards: policy.allow_hazards.includes(hazard)
        ? policy.allow_hazards.filter((h) => h !== hazard)
        : [...policy.allow_hazards, hazard],
    });
  const zone = DEFAULT_POLICY.deny_zones[0];
  const zoneOn = policy.deny_zones.length > 0;

  return (
    <div className="policy">
      <div className="policy-controls">
        <fieldset className="levels">
          <legend>How much may I do alone?</legend>
          {LEVELS.map((l) => (
            <label key={l.value} className={`level ${policy.level === l.value ? "is-on" : ""}`}>
              <input type="radio" name="level" checked={policy.level === l.value} onChange={() => set({ level: l.value })} />
              <span><strong>{l.name}</strong> {l.text}</span>
            </label>
          ))}
        </fieldset>

        <label className="field"><span>Refuse anything scoring under: <output>{policy.min_score}</output></span>
          <input type="range" min={0.5} max={3} step={0.5} value={policy.min_score}
            onChange={(e) => set({ min_score: Number(e.target.value) })} />
        </label>
        <label className="field"><span>Order alone from a score of: <output>{policy.auto_min_score}</output></span>
          <input type="range" min={1} max={6} step={0.5} value={policy.auto_min_score} disabled={policy.level !== 1}
            onChange={(e) => set({ auto_min_score: Number(e.target.value) })} />
          {policy.level !== 1 && <span className="fine">Only used at level 1.</span>}
        </label>
        <label className="field"><span>Automatic orders per day: <output>{policy.auto_daily_cap}</output></span>
          <input type="range" min={0} max={6} step={1} value={policy.auto_daily_cap}
            onChange={(e) => set({ auto_daily_cap: Number(e.target.value) })} />
        </label>

        <fieldset className="checks">
          <legend>Kinds of event it may order alone</legend>
          {HAZARDS.map((h) => (
            <label key={h}><input type="checkbox" checked={policy.allow_hazards.includes(h)} onChange={() => toggleHazard(h)} /> {cap(h)}</label>
          ))}
        </fieldset>

        <label className="check-one">
          <input type="checkbox" checked={zoneOn} onChange={(e) => set({ deny_zones: e.target.checked ? [zone] : [] })} />
          Never image within {zone.radius_km} km of {zone.latitude}°, {zone.longitude}° (a placeholder restricted zone)
        </label>
      </div>

      <aside className="policy-card" aria-live="polite">
        <h3>In plain words</h3>
        <p>{summarize(policy)}</p>
        <button type="button" className="btn" onClick={() => onChange(DEFAULT_POLICY)}>Back to default values</button>
      </aside>
    </div>
  );
}