from pathlib import Path

import pytest

from sar_scout.dataset import LabeledEvent, load_dataset, save_dataset, severity_from_magnitude
from sar_scout.synthetic import generate_dataset
from sar_scout.usgs import parse_geojson


@pytest.mark.parametrize(
    ("magnitude", "severity"),
    [(5.0, 1), (5.5, 2), (5.99, 2), (6.0, 3), (6.5, 4), (7.0, 5), (9.0, 5)],
)
def test_severity_from_magnitude(magnitude: float, severity: int) -> None:
    assert severity_from_magnitude(magnitude) == severity


def test_dataset_roundtrip(tmp_path: Path, make_event) -> None:
    items = [LabeledEvent(make_event(), 123.0)]
    save_dataset(items, tmp_path / "nested" / "d.json")

    assert load_dataset(tmp_path / "nested" / "d.json") == items


def test_synthetic_data_is_reproducible() -> None:
    assert generate_dataset(
        days=10, seed=3) == generate_dataset(days=10, seed=3)
    assert generate_dataset(
        days=10, seed=3) != generate_dataset(days=10, seed=4)


def test_synthetic_events_are_valid_and_sorted() -> None:
    items = generate_dataset(days=60, seed=1)
    times = [item.event.observed_at for item in items]

    assert items
    assert times == sorted(times)
    assert all(1 <= item.event.severity <=
               5 and item.impact > 0 for item in items)
    assert len({item.event.id for item in items}) == len(items)


SAMPLE = {
    "features": [
        {
            "id": "us7000abcd",
            "properties": {"mag": 6.4, "time": 1_700_000_000_000, "sig": 630},
            "geometry": {"coordinates": [142.5, 38.2, 25.0]},
        },
        {
            "id": "no-mag",
            "properties": {"mag": None, "time": 1},
            "geometry": {"coordinates": [1, 2]},
        },
        {"id": "no-xy", "properties": {"mag": 5.0, "time": 1},
            "geometry": {"coordinates": []}},
    ]
}


def test_usgs_parser_keeps_valid_features_and_the_label() -> None:
    items = parse_geojson(SAMPLE)

    assert [item.event.id for item in items] == ["us7000abcd"]
    item = items[0]
    assert (item.event.latitude, item.event.longitude) == (38.2, 142.5)
    assert item.event.severity == 3
    assert item.event.observed_at.tzinfo is not None
    assert item.impact == 630.0


def test_usgs_parser_handles_empty_input() -> None:
    assert parse_geojson({}) == []
