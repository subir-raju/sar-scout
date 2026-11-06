from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import pytest

from sar_scout import Event

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def now() -> datetime:
    return NOW


@pytest.fixture
def make_event() -> Callable[..., Event]:
    def _make(**overrides: Any) -> Event:
        fields: dict[str, Any] = {
            "id": "ev1",
            "source": "test",
            "hazard": "earthquake",
            "latitude": 35.0,
            "longitude": 139.0,
            "severity": 4,
            "observed_at": NOW,
        }
        fields.update(overrides)
        return Event(**fields)

    return _make
