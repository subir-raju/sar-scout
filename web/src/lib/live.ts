import type { EventBody, EventResult } from "./api";
import { decide, scoreEvent } from "./engine";
import type { Decision, Policy } from "./types";

export interface BrowserAnswer {
  score: number;
  decision: Decision;
}

export function browserAnswer(event: EventBody, result: EventResult, policy: Policy): BrowserAnswer {
  const located = { latitude: event.latitude, longitude: event.longitude };
  const images = result.images_considered.map((image) => ({ ...image, takenAt: Date.parse(image.taken_at) }));
  const score = scoreEvent(
    { ...located, hazard: event.hazard, severity: event.severity, observedAt: Date.parse(event.observed_at) },
    Date.parse(result.decided_at),
    images,
  );
  const decision = decide(policy, { ...located, id: event.id, hazard: event.hazard }, score, result.auto_used_today);
  return { score, decision };
}

/* Same action and same sentence. Scores may differ in the last few decimals (the two languages
   round the exponential slightly differently), which is not a disagreement. */
export function sameAnswer(browser: BrowserAnswer, result: EventResult): boolean {
  if (!result.decision || result.score === null) return false;
  const closeEnough = Math.abs(browser.score - result.score) <= 1e-7 * Math.max(1, Math.abs(result.score));
  return closeEnough
    && browser.decision.action === result.decision.action
    && browser.decision.reason === result.decision.reason;
}