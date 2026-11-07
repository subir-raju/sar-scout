// Checks the TypeScript engine against numbers produced by the Python code.
import { describe, expect, it } from "vitest";
import parity from "../data/parity.json";
import { decide, haversineKm, pyFloat, scoreEvent } from "./engine";
import type { Policy } from "./types";

const ms = (iso: string) => Date.parse(iso);
const close = (a: number, b: number) => Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(b));

describe("against the Python reference", () => {
  it("scores match Python", () => {
    for (const c of parity.scores) {
      const event = { ...c.event, observedAt: ms(c.event.observed_at) };
      const images = c.images.map((i) => ({ ...i, takenAt: ms(i.taken_at) }));
      const got = scoreEvent(event, ms(c.now), images);
      expect(close(got, c.score), `${c.event.id}: ${got} vs ${c.score}`).toBe(true);
    }
  });

  it("decisions and reason text match Python", () => {
    for (const c of parity.decisions) {
      const got = decide(c.policy as Policy, c.event, c.score, c.used);
      expect(got.action).toBe(c.action);
      expect(got.reason).toBe(c.reason);
      expect(got.policy_level).toBe(c.level);
    }
  });
});

describe("pieces", () => {
  const policy: Policy = {
    level: 1, min_score: 1, auto_min_score: 2, auto_daily_cap: 3,
    allow_hazards: ["earthquake", "flood"],
    deny_zones: [{ name: "zone", latitude: 0, longitude: 0, radius_km: 50 }],
  };
  const where = { id: "e", hazard: "earthquake", latitude: 40, longitude: 10 };

  it("measures distance on a sphere", () => {
    expect(haversineKm(0, 0, 0, 0)).toBe(0);
    expect(haversineKm(0, 0, 0, 1)).toBeCloseTo(111.2, 1);
  });

  it("prints whole numbers the way Python does", () => {
    expect(pyFloat(2)).toBe("2.0");
    expect(pyFloat(2.5)).toBe("2.5");
  });

  it("names the rule that decided", () => {
    expect(decide(policy, where, 0.5, 0).rule).toBe(1);
    expect(decide(policy, { ...where, latitude: 0, longitude: 0 }, 5, 0).rule).toBe(2);
    expect(decide(policy, { ...where, hazard: "wildfire" }, 5, 0).rule).toBe(3);
    expect(decide({ ...policy, level: 0 }, where, 5, 0).rule).toBe(4);
    expect(decide(policy, where, 1.5, 0).rule).toBe(5);
    expect(decide(policy, where, 5, 3).rule).toBe(6);
    expect(decide(policy, where, 5, 0)).toMatchObject({ rule: 7, action: "auto_submit" });
  });
});