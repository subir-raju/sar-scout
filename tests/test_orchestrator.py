from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

from sar_scout import TaskStatus
from sar_scout.audit import AuditLog
from sar_scout.client import TaskingClient
from sar_scout.mock_service import create_app
from sar_scout.orchestrator import Clock, Orchestrator
from sar_scout.policy import Policy
from sar_scout.store import Store


async def no_sleep(_: float) -> None:
    return None


def build(
    tmp_path: Path,
    now: datetime,
    *,
    policy: Policy | None = None,
    db: str = ":memory:",
    **mock,
):
    transport = httpx.ASGITransport(app=create_app(**mock))
    client = TaskingClient("http://mock", transport=transport, sleep=no_sleep)
    store = Store(db)
    orchestrator = Orchestrator(
        store,
        client,
        policy or Policy(level=1),
        AuditLog(tmp_path / "audit.jsonl"),
        clock=Clock(now),
    )
    return orchestrator, store


async def test_big_event_is_auto_submitted_and_fulfilled(tmp_path, now, make_event) -> None:
    orchestrator, store = build(tmp_path, now, accept_override=True)

    summary = await orchestrator.run_once([make_event(severity=5)])

    assert summary == {"fulfilled": 1}
    assert store.list_tasks()[0].auto is True


async def test_medium_event_waits_for_a_human_then_runs(tmp_path, now, make_event) -> None:
    orchestrator, _ = build(tmp_path, now, accept_override=True)
    # score 2.0: above the minimum, below the auto threshold
    event = make_event(severity=3)

    assert await orchestrator.run_once([event]) == {"proposed": 1}
    orchestrator.approve("task-ev1")

    assert await orchestrator.run_once([event]) == {"fulfilled": 1}


async def test_rejected_task_is_never_submitted(tmp_path, now, make_event) -> None:
    orchestrator, _ = build(tmp_path, now, accept_override=True)
    await orchestrator.run_once([make_event(severity=3)])
    orchestrator.reject("task-ev1")

    assert await orchestrator.run_once([]) == {"cancelled": 1}


async def test_low_value_event_creates_no_task(tmp_path, now, make_event) -> None:
    orchestrator, store = build(tmp_path, now)
    stale_event = make_event(severity=1, observed_at=now - timedelta(days=3))

    await orchestrator.run_once([stale_event])

    assert store.list_tasks() == []


async def test_window_is_relaxed_then_the_task_fails(tmp_path, now, make_event) -> None:
    orchestrator, store = build(tmp_path, now, accept_override=False)

    await orchestrator.run_once([make_event(severity=5)])

    task = store.list_tasks()[0]
    assert task.status is TaskStatus.FAILED
    assert task.attempts == 3
    log = (tmp_path / "audit.jsonl").read_text()
    # windows of 12h, 24h and 48h were all tried
    assert log.count("remote_rejected") == 3


async def test_daily_cap_limits_auto_submissions(tmp_path, now, make_event) -> None:
    orchestrator, store = build(
        tmp_path, now, policy=Policy(level=2, auto_daily_cap=2), accept_override=True
    )
    events = [make_event(id=f"e{i}", severity=5,
                         latitude=i * 20.0) for i in range(4)]

    await orchestrator.run_once(events)

    tasks = store.list_tasks()
    assert sum(task.auto for task in tasks) == 2
    assert sum(task.status is TaskStatus.PROPOSED for task in tasks) == 2


async def test_crash_after_remote_create_does_not_double_order(tmp_path, now, make_event) -> None:
    db = str(tmp_path / "state.db")
    first, store = build(tmp_path, now, db=db,
                         accept_override=True, fulfill_seconds=1000)
    first.ingest([make_event(severity=5)])
    task = store.list_tasks()[0]
    # The "crashed" process created the remote task but died before saving SUBMITTED.
    remote = await first.client.create_task(35.0, 139.0, 12, f"{task.id}-a0")

    second = Orchestrator(
        Store(db),
        first.client,
        Policy(level=1),
        AuditLog(tmp_path / "audit.jsonl"),
        clock=Clock(now),
    )
    await second.submit_approved()

    resumed = Store(db).list_tasks()[0]
    assert resumed.status is TaskStatus.SUBMITTED
    # the same remote task, so no duplicate order
    assert resumed.remote_id == remote.id


async def test_outage_defers_submission_to_the_next_cycle(tmp_path, now, make_event) -> None:
    orchestrator, _ = build(tmp_path, now, fail_rate=1.0, accept_override=True)

    assert await orchestrator.run_once([make_event(severity=5)]) == {"approved": 1}


async def test_audit_log_records_decisions_and_stays_intact(tmp_path, now, make_event) -> None:
    orchestrator, _ = build(tmp_path, now, accept_override=True)

    await orchestrator.run_once([make_event(severity=5)])

    log = (tmp_path / "audit.jsonl").read_text()
    assert '"kind": "decision"' in log
    assert '"action": "auto_submit"' in log
    assert AuditLog(tmp_path / "audit.jsonl").verify()


async def test_approving_a_cancelled_task_is_invalid(tmp_path, now, make_event) -> None:
    orchestrator, _ = build(tmp_path, now)
    await orchestrator.run_once([make_event(severity=3)])
    orchestrator.reject("task-ev1")

    with pytest.raises(ValueError, match="Cannot transition task"):
        orchestrator.approve("task-ev1")


async def test_unknown_task_raises(tmp_path, now) -> None:
    orchestrator, _ = build(tmp_path, now)

    with pytest.raises(KeyError):
        orchestrator.approve("nope")
