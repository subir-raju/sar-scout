import json
from dataclasses import dataclass
from pathlib import Path

from sar_scout.models import Event


@dataclass(frozen=True)
class LabeledEvent:
    event: Event
    impact: float


def severity_from_magnitude(magnitude: float) -> int:
    """Map an earthquake magnitude to the 1..5 severity scale used by Event."""
    if magnitude < 5.5:
        return 1
    if magnitude < 6.0:
        return 2
    if magnitude < 6.5:
        return 3
    if magnitude < 7.0:
        return 4
    return 5


def save_dataset(items: list[LabeledEvent], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"event": item.event.model_dump(
        mode="json"), "impact": item.impact} for item in items]
    target.write_text(json.dumps(rows), encoding="utf-8")


def load_dataset(path: str | Path) -> list[LabeledEvent]:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    return [LabeledEvent(Event.model_validate(row["event"]), row["impact"]) for row in rows]
