import json
import random
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sar_scout.audit import AuditLog
from sar_scout.models import Event
from sar_scout.policy import DenyZone, Policy, decide
from sar_scout.scoring import ImageRecord, score_event

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "src" / "data" / "parity.json"
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
HAZARDS = ["earthquake", "flood", "landslide", "wildfire", "volcano"]


def score_cases(rng: random.Random) -> list[dict]:
    cases = []
    for index in range(80):
        now = START + timedelta(seconds=rng.randint(0, 500 * 3600))
        event = Event(
            id=f"p{index}", source="parity", hazard=rng.choice(HAZARDS),
            latitude=round(rng.uniform(-80, 80), 3), longitude=round(rng.uniform(-179, 179), 3),
            severity=rng.randint(1, 5),
            observed_at=now - timedelta(seconds=rng.randint(0, 150 * 3600)),
        )
        images = []
        for _ in range(rng.randint(0, 3)):
            near = rng.random() < 0.5  # half the images are close, so the stale penalty fires
            images.append(ImageRecord(
                round(event.latitude + (rng.uniform(-1, 1)
                      if near else rng.uniform(-20, 20)), 3),
                round(event.longitude + (rng.uniform(-1, 1)
                      if near else rng.uniform(-20, 20)), 3),
                now - timedelta(seconds=rng.randint(0, 120 * 3600)),
            ))
        cases.append({
            "event": {
                "id": event.id, "hazard": event.hazard, "latitude": event.latitude,
                "longitude": event.longitude, "severity": event.severity,
                "observed_at": event.observed_at.isoformat(),
            },
            "now": now.isoformat(),
            "images": [
                {"latitude": i.latitude, "longitude": i.longitude,
                 "taken_at": i.taken_at.isoformat()}
                for i in images
            ],
            "score": score_event(event, now, images),
        })
    return cases


def decision_cases(rng: random.Random) -> list[dict]:
    cases = []
    for index in range(150):
        policy = Policy(
            level=rng.choice([0, 1, 2]),
            min_score=rng.choice([0.5, 1.0, 1.5]),
            auto_min_score=rng.choice([2.0, 2.5, 3.0]),
            auto_daily_cap=rng.randint(0, 4),
            allow_hazards=rng.choice(
                [["earthquake"], ["earthquake", "flood"], []]),
            deny_zones=[
                DenyZone(name="test zone", latitude=10.0, longitude=20.0, radius_km=900.0)],
        )
        event = Event(
            id=f"d{index}", source="parity", hazard=rng.choice(HAZARDS),
            latitude=round(rng.uniform(0, 20), 2), longitude=round(rng.uniform(10, 30), 2),
            severity=rng.randint(1, 5), observed_at=START,
        )
        score = rng.choice(
            [0.2, 0.5, 0.99, 1.0, 1.7, 2.0, 2.0, 2.5, 3.0, 5.123, 8.0])
        used = rng.randint(0, 4)
        decision = decide(policy, event, score, used)
        cases.append({
            "policy": policy.model_dump(),
            "event": {
                "id": event.id, "hazard": event.hazard, "latitude": event.latitude,
                "longitude": event.longitude, "severity": event.severity,
            },
            "score": score, "used": used,
            "action": decision.action.value, "reason": decision.reason,
            "level": decision.policy_level,
        })
    return cases


def audit_case(rng: random.Random) -> dict:
    records = [
        {"type": "decision", "event": f"ev{i:03d}", "action": rng.choice(["auto_submit", "deny"]),
         "score": f"{rng.uniform(0, 8):.2f}", "reason": "score 1.23 >= 2.0, within daily cap",
         "level": 1, "at": f"2026-01-0{i + 1}T10:00:00Z", "auto": bool(i % 2), "note": None}
        for i in range(8)
    ]
    # Non-ASCII text is where two JSON writers most often disagree, so include some.
    records.append({"type": "note", "event": "ev008",
                   "reason": "café ✓ 🌍", "level": 0})
    with tempfile.TemporaryDirectory() as tmp:
        log = AuditLog(Path(tmp) / "audit.jsonl")
        hashes = [log.append(record) for record in records]
    return {"records": records, "hashes": hashes}


def main() -> None:
    rng = random.Random(2026)
    data = {
        "scores": score_cases(rng),
        "decisions": decision_cases(rng),
        "audit": audit_case(rng),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(data['scores'])} scores, {len(data['decisions'])} decisions, "
          f"{len(data['audit']['records'])} audit records")


if __name__ == "__main__":
    main()
