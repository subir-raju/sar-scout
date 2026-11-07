import { describe, expect, it } from "vitest";
import type { EventBody, EventResult } from "./api";
import fixture from "../data/live-fixture.json";
import { browserAnswer, sameAnswer } from "./live";
import type { Policy } from "./types";

/* live-fixture.json holds real answers recorded from the Python API
   (python scripts/capture_live_fixture.py). The TypeScript engine has to reproduce each one. */
const cases = fixture as unknown as Array<{ event: EventBody; policy: Policy; result: EventResult }>;

describe("browser engine against recorded Python answers", () => {
  it("covers every kind of outcome", () => {
    const actions = new Set(cases.map((c) => c.result.decision?.action));
    expect(actions).toEqual(new Set(["auto_submit", "request_approval", "deny"]));
    expect(cases.some((c) => c.result.images_considered.length > 0)).toBe(true);
  });

  for (const { event, policy, result } of cases) {
    it(`agrees on ${event.id}`, () => {
      const mine = browserAnswer(event, result, policy);
      expect(mine.decision.action).toBe(result.decision?.action);
      expect(mine.decision.reason).toBe(result.decision?.reason);
      expect(mine.score).toBeCloseTo(result.score ?? NaN, 9);
      expect(sameAnswer(mine, result)).toBe(true);
    });
  }

  it("notices when the two disagree", () => {
    const { event, policy, result } = cases[0];
    const mine = browserAnswer(event, result, policy);
    const changed = { ...mine, decision: { ...mine.decision, reason: "something else" } };
    expect(sameAnswer(changed, result)).toBe(false);
    expect(sameAnswer(mine, { ...result, decision: null })).toBe(false);
  });
});