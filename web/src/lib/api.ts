/* Client for the Python API (src/sar_scout/api.py) */
import type { Action } from "./types";

export type ServerStatus = "proposed" | "approved" | "submitted" | "fulfilled" | "failed" | "cancelled";

export interface Health {
  status: string;
  version: string;
  tasking: string;
  sandboxes: number;
}

export interface ServerEvent {
  id: string;
  source: string;
  hazard: string;
  latitude: number;
  longitude: number;
  severity: number;
  observed_at: string;
}

export interface ServerTask {
  id: string;
  event_id: string;
  status: ServerStatus;
  created_at: string;
  updated_at: string;
  score: number;
  reason: string;
  auto: boolean;
  attempts: number;
  window_hours: number;
  remote_id: string | null;
  event: ServerEvent | null;
}

export interface ServerDecision {
  event_id: string;
  action: Action;
  reason: string;
  policy_level: number;
}

export interface EventBody {
  id: string;
  hazard: string;
  latitude: number;
  longitude: number;
  severity: number;
  observed_at: string;
}

export interface EventResult {
  duplicate: boolean;
  decided_at: string;
  auto_used_today: number;
  images_considered: Array<{ latitude: number; longitude: number; taken_at: string }>;
  score: number | null;
  decision: ServerDecision | null;
  task: ServerTask | null;
  summary: Record<string, number>;
}

export interface TaskList {
  tasks: ServerTask[];
  summary: Record<string, number>;
}

export interface ServerAuditEntry {
  ts: string;
  kind: string;
  prev: string;
  hash: string;
  [field: string]: unknown;
}

export interface AuditView {
  entries: ServerAuditEntry[];
  total: number;
  intact: boolean;
}

/** status 0 means the request never got an answer (offline, blocked, timed out). */
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

const SESSION_KEY = "sar-scout-session";
let memorySession: string | null = null;

function randomId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID().replaceAll("-", "");
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
}

/* A random id that names this visitor's private sandbox. Kept in the browser so a reload
   returns to the same one; if storage is blocked it lasts until the tab closes. */
export function sessionId(): string {
  try {
    const saved = localStorage.getItem(SESSION_KEY);
    if (saved) return saved;
    const fresh = randomId();
    localStorage.setItem(SESSION_KEY, fresh);
    return fresh;
  } catch {
    memorySession ??= randomId();
    return memorySession;
  }
}

export interface ApiOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
  session?: () => string;
  timeoutMs?: number;
}

export function createApi({ baseUrl, fetchImpl, session = sessionId, timeoutMs = 10_000 }: ApiOptions) {
  const root = baseUrl.replace(/\/+$/, "");

  async function call<T>(method: "GET" | "POST", path: string, body?: unknown, withSession = true): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const headers: Record<string, string> = {};
    if (withSession) headers["X-Session-Id"] = session();
    if (body !== undefined) headers["Content-Type"] = "application/json";
    try {
      let response: Response;
      try {
        response = await (fetchImpl ?? fetch)(`${root}${path}`, {
          method, headers, signal: controller.signal,
          body: body === undefined ? undefined : JSON.stringify(body),
        });
      } catch {
        throw new ApiError("Could not reach the backend.", 0);
      }
      if (!response.ok) throw new ApiError(await errorText(response), response.status);
      return (await response.json()) as T;
    } finally {
      clearTimeout(timer);
    }
  }

  return {
    health: () => call<Health>("GET", "/api/health", undefined, false),
    sendEvent: (event: EventBody, policy: unknown) => call<EventResult>("POST", "/api/events", { event, policy }),
    tasks: () => call<TaskList>("GET", "/api/tasks"),
    tick: () => call<TaskList>("POST", "/api/tick"),
    approve: (taskId: string) => call<ServerTask>("POST", `/api/tasks/${encodeURIComponent(taskId)}/approve`),
    reject: (taskId: string) => call<ServerTask>("POST", `/api/tasks/${encodeURIComponent(taskId)}/reject`),
    audit: (limit = 8) => call<AuditView>("GET", `/api/audit?limit=${limit}`),
    reset: () => call<{ status: string }>("POST", "/api/reset"),
  };
}

export type Api = ReturnType<typeof createApi>;

async function errorText(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return "The backend did not accept those values.";
  } catch {
    /* not JSON */
  }
  return `The backend answered ${response.status}.`;
}

/* Set VITE_API_URL when building to turn the live panel on. Without it the page runs alone. */
export const API_URL: string = (import.meta.env.VITE_API_URL ?? "").trim();
export const liveApi: Api | null = API_URL ? createApi({ baseUrl: API_URL }) : null;