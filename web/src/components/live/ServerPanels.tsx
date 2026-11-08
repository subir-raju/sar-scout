import type { AuditView, ServerAuditEntry, ServerStatus, ServerTask } from "../../lib/api";

const STATUS_TEXT: Record<ServerStatus, string> = {
  proposed: "Waiting for a person",
  approved: "Approved",
  submitted: "Sent to the satellite service",
  fulfilled: "Image ready",
  failed: "Failed",
  cancelled: "Declined",
};

export function StatusChip({ status }: { status: ServerStatus }) {
  return <span className={`chip chip--${status}`}>{STATUS_TEXT[status]}</span>;
}

function explain(task: ServerTask): string {
  switch (task.status) {
    case "proposed":
      return "You have to decide now.";
    case "approved":
    case "submitted":
      return "Ordered from the satellite service. The page checks again every few seconds.";
    case "fulfilled":
      return task.attempts > 1
        ? `The service refused the first request. The system will try again with a wider window of ${task.window_hours} hours.`
        : "The service reports the image is ready.";
    case "failed":
      return task.reason;
    case "cancelled":
      return "You declined it. Nothing was ordered.";
  }
}

export function TaskCard({ task, label, busy, onApprove, onReject }: {
  task: ServerTask; label: string; busy: boolean;
  onApprove: (id: string) => void; onReject: (id: string) => void;
}) {
  const who = task.auto ? "Approved by the policy" : task.status === "proposed" || task.status === "cancelled" ? "" : "Approved by you";
  return (
    <div className="task-card">
      <div className="task-head">
        <h3>The task on the server</h3>
        <StatusChip status={task.status} />
      </div>
      <p className="task-what">{label}, severity {task.event?.severity ?? "?"}, score {task.score.toFixed(2)}</p>
      <p className="task-note">{explain(task)}{who && ` ${who}.`}</p>
      {task.status === "proposed" && (
        <div className="task-actions">
          <button type="button" className="btn btn--small btn--yes" disabled={busy} onClick={() => onApprove(task.id)}>Approve</button>
          <button type="button" className="btn btn--small" disabled={busy} onClick={() => onReject(task.id)}>Decline</button>
        </div>
      )}
    </div>
  );
}

export function TaskList({ tasks, labelOf }: { tasks: ServerTask[]; labelOf: (task: ServerTask) => string }) {
  const newest = [...tasks].reverse().slice(0, 6);
  if (newest.length === 0) return <p className="empty">No tasks yet. Events that score too low never become tasks.</p>;
  return (
    <ul className="live-tasks">
      {newest.map((task) => (
        <li key={task.id}>
          <span>{labelOf(task)}</span>
          <StatusChip status={task.status} />
        </li>
      ))}
    </ul>
  );
}

function describe(entry: ServerAuditEntry, labelOf: (eventId: string) => string): string {
  const text = (key: string) => String(entry[key] ?? "");
  const place = (taskId: string) => labelOf(taskId.replace(/^task-/, ""));
  switch (entry.kind) {
    case "decision":
      return `${text("action").replace("_", " ")}: ${labelOf(text("event_id"))}`;
    case "human_approved":
      return `you approved ${place(text("task_id"))}`;
    case "human_rejected":
      return `you declined ${place(text("task_id"))}`;
    case "submitted":
      return `ordered ${place(text("task_id"))}`;
    case "remote_rejected":
      return `service refused ${place(text("task_id"))}, widening the window`;
    case "submit_deferred":
      return `service busy, will retry ${place(text("task_id"))}`;
    case "finished":
      return `${place(text("task_id"))} ${text("status")}`;
    default:
      return entry.kind;
  }
}

export function AuditPanel({ audit, labelOf }: { audit: AuditView | null; labelOf: (eventId: string) => string }) {
  const rows = audit ? [...audit.entries].reverse().slice(0, 6) : [];
  return (
    <div className="audit">
      <div className="audit-head">
        <h3>The server's audit log</h3>
        {audit && (
          <span className={`badge ${audit.intact ? "badge--ok" : "badge--bad"}`}>
            {audit.intact ? `Chain intact, ${audit.total} entries` : "Chain broken"}
          </span>
        )}
      </div>
      {rows.length === 0 ? (
        <p className="empty">Every decision and every step after it is written here, each entry sealed with the one before.</p>
      ) : (
        <ul className="audit-list">
          {rows.map((entry) => (
            <li key={entry.hash}>
              <span className="hash">{entry.hash.slice(0, 6)}</span>
              <span className="what">{describe(entry, labelOf)}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}