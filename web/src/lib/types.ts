export const HAZARDS = ["earthquake", "flood", "landslide", "wildfire"] as const;

export interface DenyZone {
  name: string;
  latitude: number;
  longitude: number;
  radius_km: number;
}

/* The same fields as policy.toml and the Python Policy class. */
export interface Policy {
  level: 0 | 1 | 2;
  min_score: number;
  auto_min_score: number;
  auto_daily_cap: number;
  allow_hazards: string[];
  deny_zones: DenyZone[];
}

export interface ImageRecord {
  latitude: number;
  longitude: number;
  takenAt: number; // milliseconds since 1970
}

export interface ScoreConfig {
  decayHours: number;
  staleRadiusKm: number;
  staleHours: number;
  stalePenalty: number;
}

export type Action = "auto_submit" | "request_approval" | "recommend" | "deny";

export interface Decision {
  event_id: string;
  action: Action;
  reason: string;
  policy_level: number;
  /** Which of the seven checks decided (1 to 7). The Python Decision has no such field. */
  rule: number;
}