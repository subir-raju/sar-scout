import type { EventResult } from "../../lib/api";
import type { BrowserAnswer } from "../../lib/live";
import { sameAnswer } from "../../lib/live";
import type { Action } from "../../lib/types";

const SAYS: Record<Action, string> = {
  auto_submit: "Acts alone",
  request_approval: "Asks a person",
  recommend: "Recommends only",
  deny: "Refuses",
};

function Side({ title, where, score, action, reason }: {
  title: string; where: string; score: number; action: Action; reason: string;
}) {
  return (
    <div className={`side is-${action}`}>
      <h3>{title}</h3>
      <p className="side-where">{where}</p>
      <p className="side-score">Score {score.toFixed(2)}</p>
      <p className="side-says">{SAYS[action]}</p>
      <p className="side-reason">{reason}</p>
    </div>
  );
}

/* The same event */
export function Compare({ mine, result }: { mine: BrowserAnswer; result: EventResult }) {
  if (!result.decision || result.score === null) return null;
  const agree = sameAnswer(mine, result);
  return (
    <div className="compare" aria-live="polite">
      <div className="duel">
        <Side
          title="In your browser" where="TypeScript, running on this page"
          score={mine.score} action={mine.decision.action} reason={mine.decision.reason}
        />
        <Side
          title="On the server" where="Python, the same code as the command line tool"
          score={result.score} action={result.decision.action} reason={result.decision.reason}
        />
      </div>
      {agree ? (
        <p className="badge badge--ok">Same answer</p>
      ) : (
        <p className="badge badge--bad">
          Different answers.
        </p>
      )}
    </div>
  );
}