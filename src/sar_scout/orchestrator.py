from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from sar_scout.audit import AuditLog
from sar_scout.client import RequestRejected, TaskingClient, TransientError
from sar_scout.models import DecisionAction, Event, Task, TaskStatus, transition_task
from sar_scout.policy import Policy, decide
from sar_scout.scoring import ScoringConfig, score_event
from sar_scout.store import Store


class Clock:
    """Injectable clock, so tests and replays control the passage of time."""

    def __init__(self, fixed: datetime | None = None) -> None:
        self.fixed = fixed

    def __call__(self) -> datetime:
        return self.fixed or datetime.now(timezone.utc)


def start_of_day(moment: datetime) -> datetime:
    return moment.replace(hour=0, minute=0, second=0, microsecond=0)


class Orchestrator:
    def __init__(
        self,
        store: Store,
        client: TaskingClient,
        policy: Policy,
        audit: AuditLog,
        *,
        clock: Clock | None = None,
        scoring: ScoringConfig | None = None,
        max_attempts: int = 3,
        base_window_hours: int = 12,
    ) -> None:
        self.store = store
        self.client = client
        self.policy = policy
        self.audit = audit
        self.clock = clock or Clock()
        self.scoring = scoring or ScoringConfig()
        self.max_attempts = max_attempts
        self.base_window_hours = base_window_hours

    def _log(self, kind: str, **fields: Any) -> None:
        self.audit.append(
            {"ts": self.clock().isoformat(), "kind": kind, **fields})

    # 1. ingest and decide -------------------------------------------------------
    def ingest(self, events: Iterable[Event]) -> list[Task]:
        now = self.clock()
        created: list[Task] = []
        for event in sorted(events, key=lambda e: e.observed_at):
            if self.store.get_event(event.id):
                continue  # already processed, so ingestion is idempotent
            self.store.save_event(event)
            value = score_event(
                event, now, self.store.delivered_images(), self.scoring)
            used_today = self.store.auto_count_since(start_of_day(now))
            decision = decide(self.policy, event, value, used_today)
            self._log(
                "decision",
                event_id=event.id,
                action=decision.action.value,
                level=decision.policy_level,
                score=round(value, 3),
                reason=decision.reason,
            )
            if decision.action is DecisionAction.DENY:
                continue
            task = Task(
                id=f"task-{event.id}",
                event_id=event.id,
                score=value,
                reason=decision.reason,
                window_hours=self.base_window_hours,
                created_at=now,
                updated_at=now,
            )
            if decision.action is DecisionAction.AUTO_SUBMIT:
                task = task.model_copy(update={"auto": True})
                task = transition_task(task, TaskStatus.APPROVED, now=now)
            self.store.save_task(task)
            created.append(task)
        return created

    # 2. the human gate ------------------------------------------------------------
    def approve(self, task_id: str, actor: str = "human") -> Task:
        task = transition_task(self._require(
            task_id), TaskStatus.APPROVED, now=self.clock())
        self.store.save_task(task)
        self._log("human_approved", task_id=task.id, actor=actor)
        return task

    def reject(self, task_id: str, actor: str = "human") -> Task:
        task = transition_task(self._require(
            task_id), TaskStatus.CANCELLED, now=self.clock())
        self.store.save_task(task)
        self._log("human_rejected", task_id=task.id, actor=actor)
        return task

    def _require(self, task_id: str) -> Task:
        task = self.store.get_task(task_id)
        if task is None:
            raise KeyError(f"unknown task {task_id}")
        return task

    # 3. submit ---------------------------------------------------------------------
    async def submit_approved(self) -> None:
        for task in self.store.list_tasks(TaskStatus.APPROVED):
            await self._submit(task)

    async def _submit(self, task: Task) -> None:
        event = self.store.get_event(task.event_id)
        if event is None:
            self._finish(task, TaskStatus.FAILED, "event missing from store")
            return
        while task.attempts < self.max_attempts:
            attempt = task.attempts
            window = self.base_window_hours * 2**attempt  # relax the window on each retry
            try:
                remote = await self.client.create_task(
                    event.latitude, event.longitude, window, f"{task.id}-a{attempt}"
                )
            except TransientError as exc:
                self._log("submit_deferred", task_id=task.id, error=str(exc))
                return  # stays APPROVED and is picked up again next cycle
            except RequestRejected as exc:
                self._finish(task, TaskStatus.FAILED,
                             f"request rejected: {exc}")
                return
            task = task.model_copy(
                update={"attempts": attempt + 1, "window_hours": window})
            if remote.status == "REJECTED":
                self.store.save_task(task)
                self._log("remote_rejected", task_id=task.id,
                          attempt=attempt, window=window)
                continue
            task = task.model_copy(update={"remote_id": remote.id})
            task = transition_task(
                task, TaskStatus.SUBMITTED, now=self.clock())
            self.store.save_task(task)
            self._log("submitted", task_id=task.id,
                      remote_id=remote.id, window=window)
            return
        self._finish(task, TaskStatus.FAILED,
                     "no feasible acquisition after relaxing the window")

    def _finish(self, task: Task, status: TaskStatus, reason: str) -> None:
        task = transition_task(task.model_copy(
            update={"reason": reason}), status, now=self.clock())
        self.store.save_task(task)
        self._log("finished", task_id=task.id,
                  status=status.value, reason=reason)

    # 4. poll -------------------------------------------------------------------------
    async def poll_submitted(self) -> None:
        for task in self.store.list_tasks(TaskStatus.SUBMITTED):
            if task.remote_id is None:
                self._finish(task, TaskStatus.FAILED,
                             "submitted task has no remote id")
                continue
            try:
                remote = await self.client.get_task(task.remote_id)
            except TransientError:
                continue
            except RequestRejected as exc:
                self._finish(task, TaskStatus.FAILED, f"poll rejected: {exc}")
                continue
            if remote.status == "FULFILLED":
                self._finish(task, TaskStatus.FULFILLED, "imagery ready")
            elif remote.status in {"REJECTED", "CANCELLED"}:
                self._finish(task, TaskStatus.FAILED,
                             f"remote status {remote.status}")

    # one full cycle ---------------------------------------------------------------------
    async def run_once(self, events: Iterable[Event]) -> dict[str, int]:
        self.ingest(events)
        await self.submit_approved()
        await self.poll_submitted()
        return self.summary()

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for task in self.store.list_tasks():
            counts[task.status.value] = counts.get(task.status.value, 0) + 1
        return counts
