import { describe, expect, it } from "vitest";
import { firstBroken } from "./audit";
import { answer, emptyDay, finished, sendNext } from "./day";
import type { Day } from "./day";
import { DEFAULT_POLICY, SCENARIOS } from "./scenarios";

const runAll = (policy = DEFAULT_POLICY): Day => {
  let day = emptyDay();
  while (!finished(day)) day = sendNext(day, policy);
  return day;
};

describe("the made-up morning", () => {
  it("plays out as the page describes", () => {
    const day = runAll();
    expect(day.items.map((i) => i.decision.action)).toEqual([
      "auto_submit",      // Tokyo, strong earthquake
      "auto_submit",      // Jakarta flood
      "request_approval", // Dhaka, score between the two limits
      "request_approval", // Santiago, landslide is not on the list
      "deny",             // Istanbul, too weak
      "deny",             // the restricted zone
      "auto_submit",      // Lagos flood: the third automatic order
      "deny",             // Tokyo aftershock: the area already has an image
      "request_approval", // Manila: would go alone, but the daily limit is used up
    ]);
    expect(day.autoUsed).toBe(3);
  });

  it("writes one log entry per decision, and the log verifies", () => {
    const day = runAll();
    expect(day.entries).toHaveLength(SCENARIOS.length);
    expect(firstBroken(day.entries)).toBe(-1);
  });

  it("lets a person answer a waiting event, once", () => {
    let day = runAll();
    day = answer(day, "s3", true);
    expect(day.items[2].status).toBe("ordered");
    expect(day.entries).toHaveLength(SCENARIOS.length + 1);
    const again = answer(day, "s3", false);
    expect(again).toBe(day);
  });

  it("uses the limits you set", () => {
    const strict = { ...DEFAULT_POLICY, auto_daily_cap: 0 };
    expect(runAll(strict).autoUsed).toBe(0);
  });
});