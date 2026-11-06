"""Validated domain models and task lifecycle transitions."""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class Event(BaseModel):
    """A normalized event that may warrant SAR imaging."""

    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    hazard: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    severity: int = Field(ge=1, le=5)
    observed_at: datetime


class TaskStatus(str, Enum):
    """Lifecycle states for a proposed imaging task."""

    PROPOSED = "proposed"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    FULFILLED = "fulfilled"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DecisionAction(str, Enum):
    """Possible outcomes from an autonomy policy."""

    RECOMMEND = "recommend"
    AUTO_SUBMIT = "auto_submit"
    REQUEST_APPROVAL = "request_approval"
    DENY = "deny"


class Task(BaseModel):
    """A task request and its current lifecycle state."""

    id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.PROPOSED
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class Decision(BaseModel):
    """An explainable policy decision for an event."""

    event_id: str = Field(min_length=1)
    action: DecisionAction
    reason: str = Field(min_length=1)
    policy_level: int = Field(ge=0, le=2)


_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PROPOSED: frozenset({TaskStatus.APPROVED, TaskStatus.CANCELLED}),
    TaskStatus.APPROVED: frozenset({TaskStatus.SUBMITTED, TaskStatus.CANCELLED}),
    TaskStatus.SUBMITTED: frozenset(
        {TaskStatus.FULFILLED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    ),
    TaskStatus.FULFILLED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


def transition_task(task: Task, target: TaskStatus) -> Task:
    """Return a copy of ``task`` in ``target`` if that transition is allowed."""
    if target not in _ALLOWED_TRANSITIONS[task.status]:
        raise ValueError(f"Cannot transition task from {task.status.value} to {target.value}")
    return task.model_copy(update={"status": target})
