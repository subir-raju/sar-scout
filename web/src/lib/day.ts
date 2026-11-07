import { appendEntry } from "./audit";
import type { AuditEntry } from "./audit";
import { decide, scoreEvent } from "./engine";
import { HOUR } from "./engine";
import { SCENARIOS, arrivalTime } from "./scenarios";
import type { Scenario } from "./scenarios";
import type { Decision, ImageRecord, Policy } from "./types";

export type Status = "ordered" | "waiting" | "declined" | "refused";

export interface Item {
  scenario: Scenario;
  score: number;
  decision: Decision;
  status: Status;
  byPolicy: boolean; // ordered by the rulebook alone, not by a person
}

export interface Day {
  step: number;          // how many of the scenarios have arrived
  items: Item[];
  images: ImageRecord[]; // areas that already have an order, which lowers later scores
  autoUsed: number;
  entries: AuditEntry[];
}

export const emptyDay = (): Day => ({ step: 0, items: [], images: [], autoUsed: 0, entries: [] });
export const finished = (day: Day) => day.step >= SCENARIOS.length;

export function sendNext(day: Day, policy: Policy): Day {
  const scenario = SCENARIOS[day.step];
  if (!scenario) return day;
  const now = arrivalTime(scenario);
  const where = { latitude: scenario.latitude, longitude: scenario.longitude };
  const score = scoreEvent(
    { ...where, hazard: scenario.hazard, severity: scenario.severity, observedAt: now - scenario.ageHours * HOUR },
    now,
    day.images,
  );
  const decision = decide(policy, { id: scenario.id, hazard: scenario.hazard, ...where }, score, day.autoUsed);

  const ordered = decision.action === "auto_submit";
  const status: Status = ordered ? "ordered" : decision.action === "deny" ? "refused" : "waiting";
  const item: Item = { scenario, score, decision, status, byPolicy: ordered };

  return {
    step: day.step + 1,
    items: [...day.items, item],
    images: ordered ? [...day.images, { ...where, takenAt: now }] : day.images,
    autoUsed: day.autoUsed + (ordered ? 1 : 0),
    // Records hold only whole numbers and strings: see canonical() in audit.ts.
    entries: appendEntry(day.entries, {
      type: "decision",
      event: scenario.id,
      action: decision.action,
      reason: decision.reason,
      level: decision.policy_level,
      score: score.toFixed(2),
      at: new Date(now).toISOString(),
    }),
  };
}

/* A person answers an event that was waiting. */
export function answer(day: Day, id: string, yes: boolean): Day {
  const item = day.items.find((i) => i.scenario.id === id);
  if (!item || item.status !== "waiting") return day;
  const now = arrivalTime(item.scenario);
  const where = { latitude: item.scenario.latitude, longitude: item.scenario.longitude };
  return {
    ...day,
    items: day.items.map((i) => (i === item ? { ...i, status: yes ? "ordered" : "declined" } : i)),
    images: yes ? [...day.images, { ...where, takenAt: now }] : day.images,
    entries: appendEntry(day.entries, {
      type: yes ? "human_approved" : "human_declined",
      event: id,
      at: new Date(now).toISOString(),
    }),
  };
}