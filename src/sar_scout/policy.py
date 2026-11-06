import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

from sar_scout.geo import haversine_km
from sar_scout.models import Decision, DecisionAction, Event


class DenyZone(BaseModel):
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0)


class Policy(BaseModel):
    """Level 0 recommends only, level 1 auto-submits high scores, level 2 auto-submits more."""

    level: int = Field(default=1, ge=0, le=2)
    min_score: float = 0.5          # below this the event is not worth a task at all
    auto_min_score: float = 3.0     # level 1: minimum score to submit without a human
    auto_daily_cap: int = Field(default=3, ge=0)
    allow_hazards: list[str] = Field(
        default_factory=lambda: ["earthquake", "flood"])
    deny_zones: list[DenyZone] = Field(default_factory=list)


def load_policy(path: str | Path) -> Policy:
    with open(path, "rb") as handle:
        return Policy.model_validate(tomllib.load(handle))


def decide(policy: Policy, event: Event, score: float, auto_used_today: int) -> Decision:
    """Checks run in a fixed order, and the first one that applies wins."""

    def make(action: DecisionAction, reason: str) -> Decision:
        return Decision(
            event_id=event.id, action=action, reason=reason, policy_level=policy.level
        )

    if score < policy.min_score:
        return make(DecisionAction.DENY, f"score {score:.2f} below minimum {policy.min_score}")

    for zone in policy.deny_zones:
        distance = haversine_km(
            event.latitude, event.longitude, zone.latitude, zone.longitude)
        if distance <= zone.radius_km:
            return make(DecisionAction.DENY, f"inside deny zone '{zone.name}'")

    if event.hazard not in policy.allow_hazards:
        return make(DecisionAction.REQUEST_APPROVAL, f"hazard '{event.hazard}' is not allow-listed")

    if policy.level == 0:
        return make(DecisionAction.RECOMMEND, "level 0: recommendations only")

    threshold = policy.auto_min_score if policy.level == 1 else policy.min_score
    if score < threshold:
        return make(
            DecisionAction.REQUEST_APPROVAL, f"score {score:.2f} below auto threshold {threshold}"
        )

    if auto_used_today >= policy.auto_daily_cap:
        return make(
            DecisionAction.REQUEST_APPROVAL, f"daily auto cap {policy.auto_daily_cap} reached"
        )

    return make(DecisionAction.AUTO_SUBMIT, f"score {score:.2f} >= {threshold}, within daily cap")
