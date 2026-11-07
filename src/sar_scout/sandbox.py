import asyncio
import json
import shutil
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from sar_scout.audit import AuditLog
from sar_scout.client import TaskingClient
from sar_scout.mock_service import create_app
from sar_scout.models import Decision, Event, Task, TaskStatus
from sar_scout.orchestrator import Clock, Orchestrator, start_of_day
from sar_scout.policy import Policy, decide
from sar_scout.scoring import ImageRecord, score_event
from sar_scout.store import Store


class SandboxFull(Exception):
    """The visitor has used up this sandbox's event allowance."""


def utc_now() -> datetime:
    """The current UTC time, cut to whole milliseconds.

    JavaScript dates stop at milliseconds. If the server used microseconds, the browser could
    not reproduce the exact instant a score was computed at, and the two would differ by a hair.
    """
    moment = datetime.now(timezone.utc)
    return moment.replace(microsecond=moment.microsecond // 1000 * 1000)


@dataclass(frozen=True)
class EventOutcome:
    """What happened to one submitted event, including the inputs the decision used."""

    duplicate: bool
    decided_at: datetime
    auto_used_today: int
    images: list[ImageRecord]
    score: float | None
    decision: Decision | None
    task: dict[str, Any] | None


class Sandbox:
    def __init__(
        self,
        directory: Path,
        *,
        seed: int = 0,
        fail_rate: float = 0.0,
        fulfill_seconds: float = 6.0,
        max_events: int = 40,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)
        self.max_events = max_events
        self._now = now
        self._clock = Clock()
        self._lock = asyncio.Lock()
        self.store = Store(":memory:")
        self.audit = AuditLog(directory / "audit.jsonl")
        service = create_app(seed=seed, fail_rate=fail_rate,
                             fulfill_seconds=fulfill_seconds)
        self._client = TaskingClient(
            "http://mock-tasking", transport=httpx.ASGITransport(app=service), base_delay=0.02
        )
        self.orchestrator = Orchestrator(
            self.store, self._client, Policy(), self.audit, clock=self._clock
        )

    @contextmanager
    def _frozen(self) -> Iterator[datetime]:
        moment = self._now()
        self._clock.fixed = moment
        try:
            yield moment
        finally:
            self._clock.fixed = None

    async def _advance(self) -> None:
        """Submit whatever is approved, then ask the service how submitted tasks are doing."""
        await self.orchestrator.submit_approved()
        await self.orchestrator.poll_submitted()

    # reading ---------------------------------------------------------------------------
    def task_view(self, task: Task) -> dict[str, Any]:
        event = self.store.get_event(task.event_id)
        view = task.model_dump(mode="json")
        view["event"] = event.model_dump(mode="json") if event else None
        return view

    def tasks(self) -> list[dict[str, Any]]:
        return [self.task_view(task) for task in self.store.list_tasks()]

    def summary(self) -> dict[str, int]:
        return self.orchestrator.summary()

    def audit_entries(self, limit: int = 50) -> tuple[list[dict[str, Any]], int]:
        """The newest ``limit`` audit entries and the total number written."""
        path = self.audit.path
        lines = path.read_text(
            encoding="utf-8").splitlines() if path.exists() else []
        entries = [json.loads(line) for line in lines if line.strip()]
        return entries[-limit:], len(entries)

    def audit_intact(self) -> bool:
        return self.audit.verify()

    # acting ----------------------------------------------------------------------------
    async def submit_event(self, event: Event, policy: Policy) -> EventOutcome:
        async with self._lock:
            existing = self.store.get_event(event.id)
            if existing is None and len(self.store.list_events()) >= self.max_events:
                raise SandboxFull(
                    f"this sandbox already holds {self.max_events} events; reset it to continue"
                )
            with self._frozen() as now:
                images = self.store.delivered_images()
                used = self.store.auto_count_since(start_of_day(now))
                score: float | None = None
                decision: Decision | None = None
                if existing is None:
                    self.orchestrator.policy = policy
                    score = score_event(event, now, images,
                                        self.orchestrator.scoring)
                    decision = decide(policy, event, score, used)
                    self.orchestrator.ingest([event])
            await self._advance()
            task = self.store.get_task(f"task-{event.id}")
            return EventOutcome(
                duplicate=existing is not None,
                decided_at=now,
                auto_used_today=used,
                images=images,
                score=score,
                decision=decision,
                task=self.task_view(task) if task else None,
            )

    async def tick(self) -> None:
        async with self._lock:
            await self._advance()

    async def approve(self, task_id: str) -> dict[str, Any]:
        return await self._human(task_id, approve=True)

    async def reject(self, task_id: str) -> dict[str, Any]:
        return await self._human(task_id, approve=False)

    async def _human(self, task_id: str, *, approve: bool) -> dict[str, Any]:
        async with self._lock:
            task = self.store.get_task(task_id)
            if task is None:
                raise KeyError(task_id)
            if task.status is not TaskStatus.PROPOSED:
                raise ValueError(
                    f"task is {task.status.value}; only proposed tasks wait for a person"
                )
            with self._frozen():
                if approve:
                    self.orchestrator.approve(task_id, actor="visitor")
                else:
                    self.orchestrator.reject(task_id, actor="visitor")
            await self._advance()
            updated = self.store.get_task(task_id)
            assert updated is not None
            return self.task_view(updated)

    async def close(self) -> None:
        async with self._lock:
            await self._client.aclose()
            shutil.rmtree(self.directory, ignore_errors=True)
