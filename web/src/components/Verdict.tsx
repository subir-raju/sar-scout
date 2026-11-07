import type { Action } from "../lib/types";

export const VERDICT: Record<Action, { text: string; tone: "auto" | "ask" | "refuse" }> = {
  auto_submit: { text: "Orders it alone", tone: "auto" },
  request_approval: { text: "Asks a person", tone: "ask" },
  recommend: { text: "Recommends only", tone: "ask" },
  deny: { text: "Says no", tone: "refuse" },
};

export function Verdict({ action }: { action: Action }) {
  const v = VERDICT[action];
  return <span className={`verdict verdict--${v.tone}`}>{v.text}</span>;
}