from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from sar_scout import Event, Task, TaskStatus, transition_task


def make_task() -> Task:
    return Task(id="task-1", event_id="event-1")


def test_event_rejects_coordinates_outside_earth() -> None:
    with pytest.raises(ValidationError):
        Event(
            id="event-1",
            source="test",
            hazard="flood",
            latitude=95,
            longitude=10,
            severity=3,
            observed_at=datetime.now(timezone.utc),
        )


def test_task_defaults_to_proposed_with_utc_timestamp() -> None:
    task = make_task()

    assert task.status is TaskStatus.PROPOSED
    assert task.created_at.tzinfo is timezone.utc


def test_task_can_move_through_approval_and_submission() -> None:
    proposed = make_task()

    approved = transition_task(proposed, TaskStatus.APPROVED)
    submitted = transition_task(approved, TaskStatus.SUBMITTED)
    fulfilled = transition_task(submitted, TaskStatus.FULFILLED)

    assert proposed.status is TaskStatus.PROPOSED
    assert fulfilled.status is TaskStatus.FULFILLED


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (TaskStatus.PROPOSED, TaskStatus.SUBMITTED),
        (TaskStatus.SUBMITTED, TaskStatus.APPROVED),
        (TaskStatus.FULFILLED, TaskStatus.CANCELLED),
        (TaskStatus.FAILED, TaskStatus.SUBMITTED),
        (TaskStatus.CANCELLED, TaskStatus.APPROVED),
    ],
)
def test_task_rejects_invalid_transitions(
    current: TaskStatus, target: TaskStatus
) -> None:
    task = make_task().model_copy(update={"status": current})

    with pytest.raises(ValueError, match="Cannot transition task"):
        transition_task(task, target)
