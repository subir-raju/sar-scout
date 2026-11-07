from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from sar_scout.dataset import LabeledEvent, severity_from_magnitude
from sar_scout.models import Event

FDSN_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def parse_geojson(data: dict[str, Any]) -> list[LabeledEvent]:
    """Convert a USGS FeatureCollection into labelled events.

    The USGS "sig" score is kept as the evaluation label. It is a proxy for importance,
    not ground truth. Features without a magnitude, time or coordinates are skipped.
    """
    items: list[LabeledEvent] = []
    for feature in data.get("features", []):
        properties = feature.get("properties") or {}
        coordinates = (feature.get("geometry") or {}).get("coordinates") or []
        if properties.get("mag") is None or properties.get("time") is None or len(coordinates) < 2:
            continue
        event = Event(
            id=str(feature["id"]),
            source="usgs",
            hazard="earthquake",
            latitude=float(coordinates[1]),
            longitude=float(coordinates[0]),
            severity=severity_from_magnitude(float(properties["mag"])),
            observed_at=datetime.fromtimestamp(
                properties["time"] / 1000, tz=timezone.utc),
        )
        items.append(LabeledEvent(event, float(properties.get("sig") or 0)))
    return sorted(items, key=lambda item: item.event.observed_at)


def fetch(
    days: int = 30, min_magnitude: float = 5.0, client: httpx.Client | None = None
) -> list[LabeledEvent]:
    end = datetime.now(timezone.utc)
    params: dict[str, str | int | float] = {
        "format": "geojson",
        "starttime": (end - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": min_magnitude,
        "orderby": "time-asc",
        "limit": 20000,
    }
    http = client or httpx.Client(timeout=60.0)
    try:
        response = http.get(FDSN_URL, params=params)
        response.raise_for_status()
        return parse_geojson(response.json())
    finally:
        if client is None:
            http.close()
