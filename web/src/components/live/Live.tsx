import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, liveApi } from "../../lib/api";
import type { Api, AuditView, EventBody, EventResult, ServerTask } from "../../lib/api";
import { HOUR } from "../../lib/engine";
import { cap } from "../../lib/format";
import { browserAnswer } from "../../lib/live";
import type { BrowserAnswer } from "../../lib/live";
import { HAZARDS } from "../../lib/types";
import type { Policy } from "../../lib/types";
import { useBackend } from "../../useBackend";
import { Compare } from "./Compare";
import { AuditPanel, TaskCard, TaskList } from "./ServerPanels";

const PLACES = [
  { name: "Tokyo, Japan", lat: 35.7, lon: 139.7 },
  { name: "Jakarta, Indonesia", lat: -6.2, lon: 106.8 },
  { name: "Dhaka, Bangladesh", lat: 23.8, lon: 90.4 },
  { name: "Santiago, Chile", lat: -33.4, lon: -70.6 },
  { name: "Istanbul, Türkiye", lat: 41.0, lon: 28.9 },
  { name: "Lagos, Nigeria", lat: 6.5, lon: 3.4 },
];

interface Shown {
  event: EventBody;
  label: string;
  result: EventResult;
  mine: BrowserAnswer;
}

function where(choice: string, policy: Policy) {
  const [kind, index] = choice.split(":");
  if (kind === "z") {
    const zone = policy.deny_zones[Number(index)];
    if (zone) return { name: `inside ${zone.name}`, lat: zone.latitude, lon: zone.longitude };
  }
  return PLACES[Number(index)] ?? PLACES[0];
}

/* A short fingerprint of where every task stands, to notice when something moved. */
const progress = (list: ServerTask[]) => list.map((t) => `${t.id}:${t.status}`).join(",");

/* A readable name for an event the page no longer remembers sending. */
function nameFor(event: { latitude: number; longitude: number }, policy: Policy): string {
  const same = (lat: number, lon: number) => lat === event.latitude && lon === event.longitude;
  const place = PLACES.find((p) => same(p.lat, p.lon));
  if (place) return place.name;
  const zone = policy.deny_zones.find((z) => same(z.latitude, z.longitude));
  if (zone) return `inside ${zone.name}`;
  return `${event.latitude.toFixed(1)}, ${event.longitude.toFixed(1)}`;
}

function LiveSection({ api, policy }: { api: Api; policy: Policy }) {
  const { phase, health, check } = useBackend(api);
  const [place, setPlace] = useState("p:0");
  const [hazard, setHazard] = useState("earthquake");
  const [severity, setSeverity] = useState(4);
  const [age, setAge] = useState(3);
  const [shown, setShown] = useState<Shown | null>(null);
  const [tasks, setTasks] = useState<ServerTask[]>([]);
  const [audit, setAudit] = useState<AuditView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const labels = useRef(new Map<string, string>());
  const counter = useRef(0);
  const latest = useRef(tasks);
  latest.current = tasks;

  const refresh = useCallback(async () => {
    const [list, log] = await Promise.all([api.tasks(), api.audit(8)]);
    setTasks(list.tasks);
    setAudit(log);
  }, [api]);

  /* Runs one action with the buttons locked, and turns a failure into a message. */
  const run = useCallback(async (job: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    try {
      await job();
    } catch (problem) {
      setError(problem instanceof ApiError ? problem.message : "Something went wrong.");
      if (problem instanceof ApiError && problem.status === 0) void check();
    } finally {
      setBusy(false);
    }
  }, [check]);

  // Pick up where this browser left off, if its sandbox is still there.
  useEffect(() => {
    if (phase === "online") refresh().catch(() => undefined);
  }, [phase, refresh]);

  // While something is on its way to the satellite service, ask for news every few seconds.
  const waiting = tasks.some((t) => t.status === "approved" || t.status === "submitted");
  useEffect(() => {
    if (phase !== "online" || !waiting) return;
    const timer = setInterval(async () => {
      if (document.hidden) return;
      try {
        const list = await api.tick();
        const changed = progress(list.tasks) !== progress(latest.current);
        setTasks(list.tasks);
        if (changed) setAudit(await api.audit(8)); // the log only grows when a task moves on
      } catch {
        /* the next round will try again */
      }
    }, 2500);
    return () => clearInterval(timer);
  }, [api, phase, waiting]);

  const labelOfEvent = (eventId: string) => {
    const known = labels.current.get(eventId);
    if (known) return known;
    const event = tasks.find((t) => t.event_id === eventId)?.event;
    return event ? nameFor(event, policy) : "an earlier event"; // e.g. after a page reload
  };
  const labelOfTask = (task: ServerTask) => `${labelOfEvent(task.event_id)}, ${task.event?.hazard ?? ""} ${task.event?.severity ?? ""}`;

  const send = () => run(async () => {
    const spot = where(place, policy);
    counter.current += 1;
    const event: EventBody = {
      id: `web-${Date.now().toString(36)}-${counter.current}`,
      hazard, severity,
      latitude: spot.lat, longitude: spot.lon,
      observed_at: new Date(Date.now() - age * HOUR).toISOString(),
    };
    labels.current.set(event.id, spot.name);
    const result = await api.sendEvent(event, policy);
    setShown({ event, label: spot.name, result, mine: browserAnswer(event, result, policy) });
    await refresh();
  });

  const answer = (taskId: string, yes: boolean) => run(async () => {
    await (yes ? api.approve(taskId) : api.reject(taskId));
    await refresh();
  });

  const startOver = () => run(async () => {
    await api.reset();
    labels.current.clear();
    setShown(null);
    setTasks([]);
    setAudit(null);
  });

  const current = shown?.result.task ? tasks.find((t) => t.id === shown.result.task?.id) ?? shown.result.task : null;
  const dot = <span className={`dot dot--${phase}`} aria-hidden="true" />;

  return (
    <section className="block" id="live" aria-labelledby="h-live">
      <div className="wrap">
   
        <p className="live-status" role="status">
          {dot}
          {phase === "checking" && "Connecting to the backend."}
          {phase === "online" && `Connected to the Python backend, version ${health?.version}.`}
          {phase === "offline" && "The backend is not answering right now."}
          {phase === "offline" && <button type="button" className="btn btn--small" onClick={() => void check()}>Try again</button>}
        </p>

        {phase === "online" && (
          <div className="live">
            <form className="try-in" onSubmit={(e) => { e.preventDefault(); void send(); }}>
              <label className="field">Where
                <select value={place} onChange={(e) => setPlace(e.target.value)}>
                  {PLACES.map((p, i) => <option key={p.name} value={`p:${i}`}>{p.name}</option>)}
                  {policy.deny_zones.map((z, i) => <option key={`${z.name}-${i}`} value={`z:${i}`}>Inside {z.name}</option>)}
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
                <input type="range" min={0} max={48} step={1} value={age} onChange={(e) => setAge(Number(e.target.value))} />
              </label>
              <button type="submit" className="btn btn--primary" disabled={busy}>
                {busy ? "Waiting for the server…" : "Send to the backend"}
              </button>
              <p className="fine">
                Uses the limits from the simulator: autonomy level {policy.level}, acts alone from a score
                of {policy.level === 1 ? policy.auto_min_score : policy.min_score}, {policy.auto_daily_cap} a day.
              </p>
            </form>

            <div className="live-out">
              {error && <p className="badge badge--bad live-error" role="alert">{error}</p>}
              {shown ? (
                <>
                  <Compare mine={shown.mine} result={shown.result} />
                  {current ? (
                    <TaskCard task={current} label={shown.label} busy={busy} onApprove={(id) => void answer(id, true)} onReject={(id) => void answer(id, false)} />
                  ) : (
                    <p className="task-card task-note">The server refused it, so no task was created. That refusal is in the log below.</p>
                  )}
                </>
              ) : (
                <p className="empty">Choose an event and send it. You will see the page's answer and the server's, side by side.</p>
              )}
              <h3>All tasks in your sandbox</h3>
              <TaskList tasks={tasks} labelOf={labelOfTask} />
              <AuditPanel audit={audit} labelOf={labelOfEvent} />
              <div className="live-foot">
                <p className="fine">
                  This sandbox is private to your browser and deleted after 30 minutes without use. Nothing here is sent to a real satellite.
                </p>
                <button type="button" className="btn btn--small" disabled={busy} onClick={() => void startOver()}>Clear my sandbox</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

/* Shows only when the site was built with the address of a backend (VITE_API_URL). */
export function Live({ policy }: { policy: Policy }) {
  return liveApi ? <LiveSection api={liveApi} policy={policy} /> : null;
}