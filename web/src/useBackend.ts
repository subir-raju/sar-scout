import { useCallback, useEffect, useState } from "react";
import type { Api, Health } from "./lib/api";

export type Phase = "checking" | "online" | "offline";

const TRIES = 3;
const GAP_MS = 2500;
const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/* Asks the backend whether it is up. A server that was idle can take a few seconds to answer
   the first request, so it tries a few times before giving up. Call check() to try again. */
export function useBackend(api: Api) {
  const [phase, setPhase] = useState<Phase>("checking");
  const [health, setHealth] = useState<Health | null>(null);

  const check = useCallback(async () => {
    setPhase("checking");
    for (let attempt = 1; attempt <= TRIES; attempt++) {
      try {
        setHealth(await api.health());
        setPhase("online");
        return;
      } catch {
        if (attempt < TRIES) await wait(GAP_MS);
      }
    }
    setPhase("offline");
  }, [api]);

  useEffect(() => {
    void check();
  }, [check]);

  return { phase, health, check };
}