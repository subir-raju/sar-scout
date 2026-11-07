/* TypeScript port of the scoring and policy code in src/sar_scout/ (scoring.py, policy.py).
   The Python code is the reference; engine.test.ts checks this file against numbers the Python
   code produced (src/data/parity.json). */
import type { Action, Decision, ImageRecord, Policy, ScoreConfig } from "./types";

export const HOUR = 3600 * 1000;
const EARTH_RADIUS_KM = 6371.0088;

/* ---------- distance ---------- */
const rad = (deg: number) => (deg * Math.PI) / 180;

export function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const p1 = rad(lat1);
  const p2 = rad(lat2);
  const dp = p2 - p1;
  const dl = rad(lon2 - lon1);
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * EARTH_RADIUS_KM * Math.asin(Math.min(1, Math.sqrt(a)));
}

/* ---------- scoring ---------- */
// A judgement call, not a measurement: how well radar suits each hazard.
export const HAZARD_SUITABILITY: Record<string, number> = {
  flood: 1.3, landslide: 1.1, earthquake: 1.0, wildfire: 0.8,
};

export const DEFAULT_SCORING: ScoreConfig = {
  decayHours: 48, staleRadiusKm: 150, staleHours: 72, stalePenalty: 0.2,
};

type Located = { latitude: number; longitude: number };
type Scorable = Located & { hazard: string; severity: number; observedAt: number };

function staleness(event: Located, nowMs: number, images: ImageRecord[], cfg: ScoreConfig): number {
  for (const image of images) {
    const recent = (nowMs - image.takenAt) / HOUR <= cfg.staleHours;
    const near =
      haversineKm(event.latitude, event.longitude, image.latitude, image.longitude) <=
      cfg.staleRadiusKm;
    if (recent && near) return cfg.stalePenalty;
  }
  return 1;
}

export interface ScoreParts {
  ageHours: number;
  severity: number;
  suitability: number;
  freshness: number;
  stale: number;
  total: number;
}

/* The four factors and their product, so the page can show its working. */
export function scoreParts(
  event: Scorable, nowMs: number, images: ImageRecord[] = [], config: Partial<ScoreConfig> = {},
): ScoreParts {
  const cfg = { ...DEFAULT_SCORING, ...config };
  const ageHours = Math.max(0, (nowMs - event.observedAt) / HOUR);
  const severity = 2 ** (event.severity - 2);
  const suitability = HAZARD_SUITABILITY[event.hazard] ?? 1;
  const freshness = Math.exp(-ageHours / cfg.decayHours);
  const stale = staleness(event, nowMs, images, cfg);
  return { ageHours, severity, suitability, freshness, stale, total: severity * suitability * freshness * stale };
}

export function scoreEvent(
  event: Scorable, nowMs: number, images: ImageRecord[] = [], config: Partial<ScoreConfig> = {},
): number {
  return scoreParts(event, nowMs, images, config).total;
}

/* ---------- policy ---------- */
// Python prints whole floats as "1.0"; mirror that so reason text matches character for character.
export const pyFloat = (x: number): string => (Number.isInteger(x) ? x.toFixed(1) : String(x));

/* Seven checks, in a fixed order. The first one that applies decides. */
export function decide(
  policy: Policy,
  event: Located & { id: string; hazard: string },
  score: number,
  autoUsedToday: number,
): Decision {
  const make = (rule: number, action: Action, reason: string): Decision => ({
    event_id: event.id, action, reason, policy_level: policy.level, rule,
  });

  if (score < policy.min_score) {
    return make(1, "deny", `score ${score.toFixed(2)} below minimum ${pyFloat(policy.min_score)}`);
  }
  for (const zone of policy.deny_zones) {
    const distance = haversineKm(event.latitude, event.longitude, zone.latitude, zone.longitude);
    if (distance <= zone.radius_km) return make(2, "deny", `inside deny zone '${zone.name}'`);
  }
  if (!policy.allow_hazards.includes(event.hazard)) {
    return make(3, "request_approval", `hazard '${event.hazard}' is not allow-listed`);
  }
  if (policy.level === 0) return make(4, "recommend", "level 0: recommendations only");

  const threshold = policy.level === 1 ? policy.auto_min_score : policy.min_score;
  if (score < threshold) {
    return make(5, "request_approval", `score ${score.toFixed(2)} below auto threshold ${pyFloat(threshold)}`);
  }
  if (autoUsedToday >= policy.auto_daily_cap) {
    return make(6, "request_approval", `daily auto cap ${policy.auto_daily_cap} reached`);
  }
  return make(7, "auto_submit", `score ${score.toFixed(2)} >= ${pyFloat(threshold)}, within daily cap`);
}