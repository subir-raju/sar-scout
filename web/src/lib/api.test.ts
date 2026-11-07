import { describe, expect, it } from "vitest";
import { ApiError, createApi, sessionId } from "./api";

interface Seen { url: string; init: RequestInit }

function fakeFetch(reply: () => Response | Promise<Response>) {
  const seen: Seen[] = [];
  const impl = (async (url: string, init: RequestInit) => {
    seen.push({ url, init });
    return reply();
  }) as unknown as typeof fetch;
  return { impl, seen };
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

describe("api client", () => {
  it("sends the session header and a JSON body", async () => {
    const { impl, seen } = fakeFetch(() => json({ tasks: [], summary: {} }));
    const api = createApi({ baseUrl: "https://api.example/", fetchImpl: impl, session: () => "abc123abc123abc123" });
    await api.sendEvent(
      { id: "e1", hazard: "flood", latitude: 1, longitude: 2, severity: 3, observed_at: "2026-01-01T00:00:00Z" },
      { level: 1 },
    );
    expect(seen[0].url).toBe("https://api.example/api/events");
    const headers = seen[0].init.headers as Record<string, string>;
    expect(headers["X-Session-Id"]).toBe("abc123abc123abc123");
    expect(headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(seen[0].init.body as string).policy).toEqual({ level: 1 });
  });

  it("keeps the health check free of custom headers so browsers skip the preflight", async () => {
    const { impl, seen } = fakeFetch(() => json({ status: "ok", version: "1", tasking: "mock", sandboxes: 0 }));
    await createApi({ baseUrl: "https://api.example", fetchImpl: impl }).health();
    expect(seen[0].init.headers).toEqual({});
  });

  it("turns an error response into an ApiError with the server's message", async () => {
    const { impl } = fakeFetch(() => json({ detail: "this sandbox already holds 40 events" }, 429));
    const api = createApi({ baseUrl: "https://api.example", fetchImpl: impl });
    await expect(api.tasks()).rejects.toMatchObject({ status: 429, message: "this sandbox already holds 40 events" });
  });

  it("does not show raw validation details to visitors", async () => {
    const { impl } = fakeFetch(() => json({ detail: [{ loc: ["body"], msg: "bad" }] }, 422));
    const api = createApi({ baseUrl: "https://api.example", fetchImpl: impl });
    await expect(api.tasks()).rejects.toThrow("did not accept");
  });

  it("reports an unreachable server as status 0", async () => {
    const impl = (async () => { throw new TypeError("Failed to fetch"); }) as unknown as typeof fetch;
    const api = createApi({ baseUrl: "https://api.example", fetchImpl: impl });
    const error = await api.health().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(0);
  });

  it("gives up on a server that never answers", async () => {
    const impl = ((_: string, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
      })) as unknown as typeof fetch;
    const api = createApi({ baseUrl: "https://api.example", fetchImpl: impl, timeoutMs: 20 });
    await expect(api.health()).rejects.toMatchObject({ status: 0 });
  });

  it("escapes task ids in the path", async () => {
    const { impl, seen } = fakeFetch(() => json({}));
    await createApi({ baseUrl: "https://api.example", fetchImpl: impl }).approve("task-a/b");
    expect(seen[0].url).toBe("https://api.example/api/tasks/task-a%2Fb/approve");
  });
});

describe("session id", () => {
  it("is stable and matches what the server accepts", () => {
    const first = sessionId();
    expect(sessionId()).toBe(first);
    expect(first).toMatch(/^[A-Za-z0-9_-]{16,64}$/);
  });
});