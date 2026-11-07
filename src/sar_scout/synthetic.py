import math
import random
from datetime import datetime, timedelta, timezone

from sar_scout.dataset import LabeledEvent, severity_from_magnitude
from sar_scout.models import Event


def _poisson(rng: random.Random, mean: float) -> int:
    limit, count, product = math.exp(-mean), 0, 1.0
    while True:
        product *= rng.random()
        if product <= limit:
            return count
        count += 1


def generate_dataset(
    days: int = 90,
    seed: int = 1,
    rate_per_day: float = 4.0,
    start: datetime | None = None,
) -> list[LabeledEvent]:
    rng = random.Random(seed)
    start = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
    items: list[LabeledEvent] = []

    def add(
        when: datetime,
        latitude: float,
        longitude: float,
        magnitude: float,
        depth_km: float,
        exposure: float,
        aftershock: bool,
    ) -> None:
        depth_factor = 1.5 if depth_km < 20 else 1.0 if depth_km < 70 else 0.5
        impact = 100 * (magnitude - 4) ** 2 * \
            (0.3 + 2 * exposure) * depth_factor
        if aftershock:
            impact *= 0.25
        event = Event(
            id=f"syn{len(items):05d}",
            source="synthetic",
            hazard="earthquake",
            latitude=round(max(-89.0, min(89.0, latitude)), 3),
            longitude=round(((longitude + 180) % 360) - 180, 3),
            severity=severity_from_magnitude(magnitude),
            observed_at=when,
        )
        items.append(LabeledEvent(event, round(impact, 1)))

    for day in range(days):
        day_start = start + timedelta(days=day)
        for _ in range(_poisson(rng, rate_per_day)):
            # Gutenberg-Richter, b=1
            magnitude = min(9.0, 5.0 - math.log10(1.0 - rng.random()))
            depth_km = min(600.0, max(2.0, rng.lognormvariate(3.0, 1.0)))
            latitude = math.degrees(math.asin(2 * rng.random() - 1))
            longitude = rng.uniform(-180, 180)
            exposure = rng.random() ** 2  # hidden: most quakes affect few people
            when = day_start + timedelta(seconds=rng.randint(0, 86399))
            add(when, latitude, longitude, magnitude,
                depth_km, exposure, aftershock=False)
            if magnitude >= 6.5:
                for _ in range(rng.randint(2, 6)):
                    add(
                        when + timedelta(hours=rng.uniform(1, 72)),
                        latitude + rng.uniform(-0.4, 0.4),
                        longitude + rng.uniform(-0.4, 0.4),
                        max(5.0, magnitude - rng.uniform(0.8, 1.8)),
                        depth_km,
                        exposure,
                        aftershock=True,
                    )
    return sorted(items, key=lambda item: item.event.observed_at)
