import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import NamedTuple

from sar_scout.geo import haversine_km
from sar_scout.models import Event


class ImageRecord(NamedTuple):
    """An image that has already been delivered for some place and time."""

    latitude: float
    longitude: float
    taken_at: datetime


# A judgement call, not a measurement: how well SAR suits each hazard.
# Radar sees through cloud, which matters most for floods.
HAZARD_SUITABILITY = {"flood": 1.3, "landslide": 1.1,
                      "earthquake": 1.0, "wildfire": 0.8}


@dataclass(frozen=True)
class ScoringConfig:
    decay_hours: float = 48.0       # a fresh image is worth less as the event ages
    stale_radius_km: float = 150.0  # "we already imaged this area" radius
    stale_hours: float = 72.0
    stale_penalty: float = 0.2      # multiplier when the area was imaged recently


def _staleness(
    event: Event, now: datetime, images: Sequence[ImageRecord], config: ScoringConfig
) -> float:
    for image in images:
        recent = (now - image.taken_at).total_seconds() / \
            3600 <= config.stale_hours
        distance = haversine_km(
            event.latitude, event.longitude, image.latitude, image.longitude
        )
        if recent and distance <= config.stale_radius_km:
            return config.stale_penalty
    return 1.0


def score_event(
    event: Event,
    now: datetime,
    recent_images: Sequence[ImageRecord] = (),
    config: ScoringConfig | None = None,
) -> float:
    """Higher is better. Severity 1..5 maps to 0.5..8 before the other factors apply."""
    config = config or ScoringConfig()
    age_hours = max(0.0, (now - event.observed_at).total_seconds() / 3600)
    severity = 2 ** (event.severity - 2)
    suitability = HAZARD_SUITABILITY.get(event.hazard, 1.0)
    freshness = math.exp(-age_hours / config.decay_hours)
    return severity * suitability * freshness * _staleness(event, now, recent_images, config)
