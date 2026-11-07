import { HOUR } from "./engine";
import type { Policy } from "./types";

export const DEFAULT_POLICY: Policy = {
  level: 1,
  min_score: 1,
  auto_min_score: 2,
  auto_daily_cap: 3,
  allow_hazards: ["earthquake", "flood"],
  deny_zones: [{ name: "example-restricted-zone", latitude: 0, longitude: 0, radius_km: 50 }],
};

export const PLACES = [
  { name: "Tokyo, Japan", lat: 35.7, lon: 139.7 },
  { name: "Jakarta, Indonesia", lat: -6.2, lon: 106.8 },
  { name: "Dhaka, Bangladesh", lat: 23.8, lon: 90.4 },
  { name: "Santiago, Chile", lat: -33.4, lon: -70.6 },
  { name: "Istanbul, Türkiye", lat: 41.0, lon: 28.9 },
  { name: "Lagos, Nigeria", lat: 6.5, lon: 3.4 },
];

/* A made-up morning. Each event arrives some hours after START, already a few hours old. */
export const START = Date.UTC(2026, 5, 1, 6, 0);

export interface Scenario {
  id: string;
  place: string;
  hazard: string;
  severity: number;
  latitude: number;
  longitude: number;
  ageHours: number;     // how old the event is when it arrives
  arrivesAfter: number; // hours after START
}

export const SCENARIOS: Scenario[] = [
  { id: "s1", place: "Tokyo, Japan", hazard: "earthquake", severity: 5, latitude: 35.7, longitude: 139.7, ageHours: 2, arrivesAfter: 0 },
  { id: "s2", place: "Jakarta, Indonesia", hazard: "flood", severity: 3, latitude: -6.2, longitude: 106.8, ageHours: 5, arrivesAfter: 1 },
  { id: "s3", place: "Dhaka, Bangladesh", hazard: "flood", severity: 2, latitude: 23.8, longitude: 90.4, ageHours: 6, arrivesAfter: 2 },
  { id: "s4", place: "Santiago, Chile", hazard: "landslide", severity: 4, latitude: -33.4, longitude: -70.6, ageHours: 4, arrivesAfter: 3 },
  { id: "s5", place: "Istanbul, Türkiye", hazard: "earthquake", severity: 1, latitude: 41.0, longitude: 28.9, ageHours: 10, arrivesAfter: 4 },
  { id: "s6", place: "Inside the restricted zone", hazard: "earthquake", severity: 5, latitude: 0, longitude: 0, ageHours: 1, arrivesAfter: 5 },
  { id: "s7", place: "Lagos, Nigeria", hazard: "flood", severity: 5, latitude: 6.5, longitude: 3.4, ageHours: 3, arrivesAfter: 6 },
  { id: "s8", place: "Tokyo, Japan (aftershock)", hazard: "earthquake", severity: 4, latitude: 35.8, longitude: 139.8, ageHours: 1, arrivesAfter: 7 },
  { id: "s9", place: "Manila, Philippines", hazard: "earthquake", severity: 4, latitude: 14.6, longitude: 121.0, ageHours: 2, arrivesAfter: 8 },
];

export const arrivalTime = (s: Scenario) => START + s.arrivesAfter * HOUR;