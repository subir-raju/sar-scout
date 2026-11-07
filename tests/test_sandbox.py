from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sar_scout import Event
from sar_scout.models import DecisionAction, TaskStatus
from sar_scout.policy import Policy
from sar_scout.sandbox import Sandbox, SandboxFull

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
POLICY = Policy(level=1, min_score=1.0, auto_min_score=2.0,
                auto_daily_cap=3, deny_zones=[])


def quake(event_id: str = "ev1", severity: int = 5, **overrides) -> Event:
    fields = {
        "id": event_id,
        "source": "test",
        "hazard": "earthquake",
        "latitude": 35.0,
        "longitude": 139.0,
        "severity": severity,
        "observed_at": NOW - timedelta(hours=1),
    }
    return Event(**{**fields, **overrides})


@pytest.fixture
def box(tmp_path: Path) -> Sandbox:
    return Sandbox(tmp_path / "box", seed=1, fulfill_seconds=0.0, now=lambda: NOW)


async def test_a_strong_event_is_sent_without_a_person(box: Sandbox) -> None:
    outcome = await box.submit_event(quake(severity=5), POLICY)
    assert outcome.decision is not None
    assert outcome.decision.action is DecisionAction.AUTO_SUBMIT
    assert outcome.task is not None
    assert outcome.task["auto"] is True
    assert outcome.task["status"] in {"submitted", "fulfilled", "failed"}
    assert outcome.decided_at == NOW


async def test_a_middling_event_waits_for_a_person(box: Sandbox) -> None:
    # score about 1.9 < 2.0
    outcome = await box.submit_event(quake(severity=3), POLICY)
    assert outcome.decision is not None
    assert outcome.decision.action is DecisionAction.REQUEST_APPROVAL
    assert outcome.task is not None and outcome.task["status"] == "proposed"


async def test_a_weak_event_is_refused_and_creates_no_task(box: Sandbox) -> None:
    outcome = await box.submit_event(quake(severity=1), POLICY)
    assert outcome.decision is not None
    assert outcome.decision.action is DecisionAction.DENY
    assert outcome.task is None
    assert box.tasks() == []


async def test_sending_the_same_event_twice_does_nothing_new(box: Sandbox) -> None:
    await box.submit_event(quake(severity=3), POLICY)
    again = await box.submit_event(quake(severity=3), POLICY)
    assert again.duplicate is True
    assert again.decision is None
    assert len(box.tasks()) == 1


async def test_approving_sends_the_task_and_it_completes(box: Sandbox) -> None:
    await box.submit_event(quake(severity=3), POLICY)
    approved = await box.approve("task-ev1")
    assert approved["status"] in {"submitted", "fulfilled"}
    await box.tick()
    # type: ignore[union-attr]
    assert box.store.get_task("task-ev1").status is TaskStatus.FULFILLED


async def test_declining_cancels_the_task(box: Sandbox) -> None:
    await box.submit_event(quake(severity=3), POLICY)
    declined = await box.reject("task-ev1")
    assert declined["status"] == "cancelled"


async def test_only_proposed_tasks_can_be_answered(box: Sandbox) -> None:
    await box.submit_event(quake(severity=3), POLICY)
    await box.reject("task-ev1")
    with pytest.raises(ValueError):
        await box.approve("task-ev1")
    with pytest.raises(KeyError):
        await box.approve("task-nope")


async def test_the_daily_allowance_is_counted_inside_the_sandbox(box: Sandbox) -> None:
    capped = POLICY.model_copy(update={"auto_daily_cap": 1})
    first = await box.submit_event(quake("a", severity=5, latitude=10.0, longitude=10.0), capped)
    second = await box.submit_event(quake("b", severity=5, latitude=-30.0, longitude=100.0), capped)
    assert first.decision is not None and first.decision.action is DecisionAction.AUTO_SUBMIT
    assert second.auto_used_today == 1
    assert second.decision is not None and second.decision.action is DecisionAction.REQUEST_APPROVAL


async def test_a_recent_image_nearby_lowers_the_next_score(box: Sandbox) -> None:
    first = await box.submit_event(quake("a", severity=5), POLICY)
    await box.tick()
    nearby = await box.submit_event(quake("b", severity=5, latitude=35.2), POLICY)
    assert first.score is not None and nearby.score is not None
    assert len(nearby.images) == 1
    assert nearby.score == pytest.approx(first.score * 0.2)


async def test_every_step_lands_in_a_log_that_verifies(box: Sandbox) -> None:
    await box.submit_event(quake(severity=3), POLICY)
    await box.approve("task-ev1")
    entries, total = box.audit_entries()
    kinds = [entry["kind"] for entry in entries]
    assert kinds[0] == "decision" and "human_approved" in kinds and "submitted" in kinds
    assert total == len(entries)
    assert box.audit_intact()


async def test_the_sandbox_has_an_event_allowance(tmp_path: Path) -> None:
    box = Sandbox(tmp_path / "box", max_events=2,
                  fulfill_seconds=0.0, now=lambda: NOW)
    await box.submit_event(quake("a", severity=1), POLICY)
    await box.submit_event(quake("b", severity=1), POLICY)
    with pytest.raises(SandboxFull):
        await box.submit_event(quake("c", severity=1), POLICY)
    # repeats are still free
    await box.submit_event(quake("a", severity=1), POLICY)


async def test_closing_removes_the_files(box: Sandbox) -> None:
    await box.submit_event(quake(severity=3), POLICY)
    assert box.directory.exists()
    await box.close()
    assert not box.directory.exists()


def test_the_default_clock_stops_at_milliseconds() -> None:
    from sar_scout.sandbox import utc_now

    for _ in range(50):
        assert utc_now().microsecond % 1000 == 0
