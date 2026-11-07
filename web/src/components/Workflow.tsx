import { answer, emptyDay, finished, sendNext } from "../lib/day";
import type { Day, Item, Status } from "../lib/day";
import { SCENARIOS } from "../lib/scenarios";
import type { Policy } from "../lib/types";
import { cap } from "../lib/format";
import { Verdict } from "./Verdict";

const STATUS: Record<Status, string> = {
  ordered: "Image ordered",
  waiting: "Waiting for a person",
  declined: "Declined by a person",
  refused: "Refused, nothing ordered",
};

function Card({ item, onYes, onNo }: { item: Item; onYes: () => void; onNo: () => void }) {
  const { scenario: s } = item;
  const who = item.status === "ordered" ? (item.byPolicy ? " by the rulebook" : " after a person said yes") : "";
  return (
    <li className={`card card--${item.decision.action}`}>
      <div className="card-top">
        <h3>{s.place}</h3>
        <Verdict action={item.decision.action} />
      </div>
      <p className="card-what">{cap(s.hazard)}, severity {s.severity}, {s.ageHours}h old, score {item.score.toFixed(2)}</p>
      <p className="fine">{item.decision.reason}</p>
      <p className={`status status--${item.status}`}>{STATUS[item.status]}{who}</p>
      {item.status === "waiting" && (
        <div className="card-actions">
          <button type="button" className="btn btn--small btn--yes" onClick={onYes}>Approve</button>
          <button type="button" className="btn btn--small" onClick={onNo}>Decline</button>
        </div>
      )}
    </li>
  );
}

export function Workflow({ policy, day, onChange }: { policy: Policy; day: Day; onChange: (next: Day) => void }) {
  const done = finished(day);
  const next = SCENARIOS[day.step];
  const sendAll = () => {
    let d = day;
    while (!finished(d)) d = sendNext(d, policy);
    onChange(d);
  };

  return (
    <div className="day">
      <div className="day-bar">
        <button type="button" className="btn btn--primary" disabled={done} onClick={() => onChange(sendNext(day, policy))}>
          {done ? "All events sent" : `Send the next event (${day.step + 1} of ${SCENARIOS.length})`}
        </button>
        <button type="button" className="btn" disabled={done} onClick={sendAll}>Send them all</button>
        <button type="button" className="btn" disabled={day.step === 0} onClick={() => onChange(emptyDay())}>Start over</button>
        <p className="counter" role="status">
          Automatic orders today: <strong>{day.autoUsed} of {policy.auto_daily_cap}</strong>
        </p>
      </div>
      {!done && <p className="fine">Next up: {next.place}, {next.hazard}, severity {next.severity}.</p>}

      {day.items.length === 0 ? (
        <p className="empty">Nothing has arrived yet. Send the first event.</p>
      ) : (
        <ul className="cards">
          {[...day.items].reverse().map((item) => (
            <Card key={item.scenario.id} item={item}
              onYes={() => onChange(answer(day, item.scenario.id, true))}
              onNo={() => onChange(answer(day, item.scenario.id, false))} />
          ))}
        </ul>
      )}
    </div>
  );
}