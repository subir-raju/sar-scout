from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class Event(BaseModel):

    id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    hazard: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    severity: int = Field(ge=1, le=5)
    observed_at: datetime


class TaskStatus(str, Enum):

    PROPOSED = "proposed"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    FULFILLED = "fulfilled"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DecisionAction(str, Enum):

    RECOMMEND = "recommend"
    AUTO_SUBMIT = "auto_submit"
    REQUEST_APPROVAL = "request_approval"
    DENY = "deny"


class Task(BaseModel):

    id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.PROPOSED
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    score: float = 0.0
    reason: str = ""
    auto: bool = False
    attempts: int = Field(default=0, ge=0)
    window_hours: int = Field(default=12, ge=1)
    remote_id: str | None = None


class Decision(BaseModel):

    event_id: str = Field(min_length=1)
    action: DecisionAction
    reason: str = Field(min_length=1)
    policy_level: int = Field(ge=0, le=2)


_ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PROPOSED: frozenset({TaskStatus.APPROVED, TaskStatus.CANCELLED}),
    TaskStatus.APPROVED: frozenset({TaskStatus.SUBMITTED, TaskStatus.FAILED, TaskStatus.CANCELLED}),
    TaskStatus.SUBMITTED: frozenset(
        {TaskStatus.FULFILLED, TaskStatus.FAILED, TaskStatus.CANCELLED}
    ),
    TaskStatus.FULFILLED: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


def transition_task(task: Task, target: TaskStatus, *, now: datetime | None = None) -> Task:
    if target not in _ALLOWED_TRANSITIONS[task.status]:
        raise ValueError(
            f"Cannot transition task from {task.status.value} to {target.value}")
    timestamp = now or datetime.now(timezone.utc)
    return task.model_copy(update={"status": target, "updated_at": timestamp})
