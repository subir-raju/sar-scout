import asyncio
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from sar_scout.api import create_api
from sar_scout.limits import SandboxPool

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "src" / "data" / "live-fixture.json"
NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
SESSION = {"X-Session-Id": "fixture-session-0000000000000000"}
POLICY = {
    "level": 1,
    "min_score": 1.0,
    "auto_min_score": 2.0,
    "auto_daily_cap": 3,
    "allow_hazards": ["earthquake", "flood"],
    "deny_zones": [
        {"name": "example-restricted-zone", "latitude": 0.0,
            "longitude": 0.0, "radius_km": 50.0}
    ],
}

# (id, hazard, latitude, longitude, severity, hours old)
EVENTS = [
    ("tokyo", "earthquake", 35.7, 139.7, 5, 2),         # acts alone
    # just imaged nearby, so it scores low
    ("tokyo-again", "earthquake", 35.9, 139.5, 5, 2),
    ("dhaka", "flood", 23.8, 90.4, 3, 6),               # acts alone
    # acts alone, the third of the day
    ("jakarta", "flood", -6.2, 106.8, 4, 30),
    # allowance used up, so it asks
    ("santiago", "earthquake", -33.4, -70.6, 5, 1),
    # hazard not on the allow list
    ("istanbul", "wildfire", 41.0, 28.9, 4, 3),
    ("quiet", "earthquake", -20.0, -70.0, 1, 5),        # too weak
    ("restricted", "earthquake", 0.1, 0.1, 5, 1),       # inside the no-go zone
]


async def main() -> None:
    pool = SandboxPool(base_dir=Path(tempfile.mkdtemp()),
                       fulfill_seconds=0.0, now=lambda: NOW)
    app = create_api(pool=pool, now=lambda: NOW)
    cases = []
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as http:
        for event_id, hazard, lat, lon, severity, hours in EVENTS:
            event = {
                "id": event_id,
                "hazard": hazard,
                "latitude": lat,
                "longitude": lon,
                "severity": severity,
                "observed_at": (NOW - timedelta(hours=hours)).isoformat(),
            }
            response = await http.post(
                "/api/events", json={"event": event, "policy": POLICY}, headers=SESSION
            )
            response.raise_for_status()
            cases.append({"event": event, "policy": POLICY,
                         "result": response.json()})
            # lets delivered images count as stale
            await http.post("/api/tick", headers=SESSION)
    await pool.close()
    OUT.write_text(json.dumps(cases, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} cases to {OUT.relative_to(ROOT)}")
    for case in cases:
        decision = case["result"]["decision"]
        print(
            f"  {case['event']['id']:<12} {decision['action']:<17} {decision['reason']}")


if __name__ == "__main__":
    asyncio.run(main())
