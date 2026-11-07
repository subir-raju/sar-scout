import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from sar_scout.api import create_api
from sar_scout.limits import RateLimiter, SandboxPool

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
SESSION = {"X-Session-Id": "session-aaaaaaaaaaaaaaaa"}
OTHER = {"X-Session-Id": "session-bbbbbbbbbbbbbbbb"}
POLICY = {
    "level": 1,
    "min_score": 1.0,
    "auto_min_score": 2.0,
    "auto_daily_cap": 3,
    "allow_hazards": ["earthquake", "flood"],
    "deny_zones": [],
}


def event(event_id: str = "ev1", severity: int = 5, **overrides) -> dict:
    body = {
        "id": event_id,
        "hazard": "earthquake",
        "latitude": 35.0,
        "longitude": 139.0,
        "severity": severity,
        "observed_at": (NOW - timedelta(hours=1)).isoformat(),
    }
    return {**body, **overrides}


async def send(api: httpx.AsyncClient, ev: dict, headers: dict = SESSION) -> httpx.Response:
    return await api.post("/api/events", json={"event": ev, "policy": POLICY}, headers=headers)


def make_client(tmp_path: Path, **kwargs) -> httpx.AsyncClient:
    pool = SandboxPool(base_dir=tmp_path, fulfill_seconds=0.0, now=lambda: NOW)
    app = create_api(pool=pool, now=lambda: NOW, **kwargs)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://api")


@pytest.fixture
async def api(tmp_path: Path):
    async with make_client(tmp_path) as client:
        yield client


async def test_health_needs_no_session(api: httpx.AsyncClient) -> None:
    response = await api.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["tasking"] == "mock"


async def test_decide_is_stateless_and_matches_the_policy(api: httpx.AsyncClient) -> None:
    body = {"event": event(severity=5), "policy": POLICY,
            "now": NOW.isoformat()}
    response = await api.post("/api/decide", json=body)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"]["action"] == "auto_submit"
    assert data["score"] == pytest.approx(8 * math.exp(-1 / 48))
    refused = await api.post("/api/decide", json={**body, "event": event(severity=1)})
    assert refused.json()["decision"]["action"] == "deny"


async def test_decide_checks_the_daily_allowance(api: httpx.AsyncClient) -> None:
    body = {"event": event(), "policy": POLICY, "now": NOW.isoformat(),
            "auto_used_today": 3}
    decision = (await api.post("/api/decide", json=body)).json()["decision"]
    assert decision["action"] == "request_approval"
    assert "daily auto cap 3" in decision["reason"]


@pytest.mark.parametrize(
    "bad",
    [
        {"severity": 9},
        {"latitude": 123},
        {"id": "has spaces"},
        {"hazard": "x" * 40},
        {"observed_at": "yesterday-ish"},
    ],
)
async def test_bad_events_are_rejected(api: httpx.AsyncClient, bad: dict) -> None:
    body = {"event": event(**bad), "policy": POLICY}
    assert (await api.post("/api/decide", json=body)).status_code == 422


async def test_oversized_policies_are_rejected(api: httpx.AsyncClient) -> None:
    zones = [{"name": f"z{i}", "latitude": 0, "longitude": 0, "radius_km": 1}
             for i in range(21)]
    body = {"event": event(), "policy": {**POLICY, "deny_zones": zones}}
    assert (await api.post("/api/decide", json=body)).status_code == 422


async def test_sandbox_routes_need_a_valid_session_id(api: httpx.AsyncClient) -> None:
    assert (await api.get("/api/tasks")).status_code == 400
    bad = await api.get("/api/tasks", headers={"X-Session-Id": "short"})
    assert bad.status_code == 400


async def test_an_event_runs_through_the_real_pipeline(api: httpx.AsyncClient) -> None:
    sent = await send(api, event(severity=5))
    assert sent.status_code == 200
    data = sent.json()
    assert data["decision"]["action"] == "auto_submit"
    assert data["task"]["auto"] is True
    assert data["auto_used_today"] == 0
    assert data["decided_at"].startswith("2026-06-01T12:00:00")

    listed = (await api.get("/api/tasks", headers=SESSION)).json()
    assert [t["id"] for t in listed["tasks"]] == ["task-ev1"]
    assert sum(listed["summary"].values()) == 1


async def test_the_person_can_approve_or_decline(api: httpx.AsyncClient) -> None:
    for name in ("a", "b"):
        sent = await send(api, event(name, severity=3, latitude=10.0 if name == "a" else -40.0))
        assert sent.json()["task"]["status"] == "proposed"

    approved = await api.post("/api/tasks/task-a/approve", headers=SESSION)
    assert approved.json()["status"] in {"submitted", "fulfilled"}
    declined = await api.post("/api/tasks/task-b/reject", headers=SESSION)
    assert declined.json()["status"] == "cancelled"

    again = await api.post("/api/tasks/task-b/approve", headers=SESSION)
    assert again.status_code == 409
    missing = await api.post("/api/tasks/task-zzz/approve", headers=SESSION)
    assert missing.status_code == 404


async def test_tick_finishes_submitted_tasks(api: httpx.AsyncClient) -> None:
    await send(api, event(severity=5), SESSION)
    ticked = (await api.post("/api/tick", headers=SESSION)).json()
    assert ticked["tasks"][0]["status"] == "fulfilled"
    assert ticked["summary"] == {"fulfilled": 1}


async def test_the_audit_log_is_returned_and_verifies(api: httpx.AsyncClient) -> None:
    await send(api, event(severity=3), SESSION)
    await api.post("/api/tasks/task-ev1/approve", headers=SESSION)
    view = (await api.get("/api/audit", headers=SESSION)).json()
    assert view["intact"] is True
    assert view["total"] == len(view["entries"]) >= 3
    assert len(view["entries"][0]["hash"]) == 64


async def test_visitors_cannot_see_each_other(api: httpx.AsyncClient) -> None:
    await send(api, event(severity=5), SESSION)
    assert (await api.get("/api/tasks", headers=OTHER)).json()["tasks"] == []


async def test_reset_starts_over(api: httpx.AsyncClient) -> None:
    await send(api, event(severity=5), SESSION)
    assert (await api.post("/api/reset", headers=SESSION)).json() == {"status": "reset"}
    assert (await api.get("/api/tasks", headers=SESSION)).json()["tasks"] == []


async def test_the_sandbox_allowance_returns_429(tmp_path: Path) -> None:
    pool = SandboxPool(base_dir=tmp_path, max_events=1,
                       fulfill_seconds=0.0, now=lambda: NOW)
    app = create_api(pool=pool, now=lambda: NOW)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://api") as client:
        first = await send(client, event("a"))
        second = await send(client, event("b"))
    assert first.status_code == 200
    assert second.status_code == 429


async def test_too_many_requests_from_one_address_get_429(tmp_path: Path) -> None:
    async with make_client(tmp_path, ip_limiter=RateLimiter(3)) as client:
        codes = [(await client.get("/api/tasks", headers=SESSION)).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


async def test_forwarded_addresses_are_limited_separately(tmp_path: Path) -> None:
    async with make_client(tmp_path, ip_limiter=RateLimiter(1)) as client:
        async def get(forwarded: str) -> httpx.Response:
            return await client.get("/api/tasks", headers={**SESSION, "X-Forwarded-For": forwarded})

        one = await get("9.9.9.9, 1.1.1.1")
        two = await get("9.9.9.9, 2.2.2.2")
        again = await get("7.7.7.7, 1.1.1.1")
    assert (one.status_code, two.status_code,
            again.status_code) == (200, 200, 429)


async def test_one_address_cannot_mint_endless_sandboxes(tmp_path: Path) -> None:
    async with make_client(tmp_path, new_sandbox_limiter=RateLimiter(2)) as client:
        codes = []
        for index in range(4):
            headers = {"X-Session-Id": f"session-{index:016d}"}
            codes.append((await client.get("/api/tasks", headers=headers)).status_code)
        known = await client.get("/api/tasks", headers={"X-Session-Id": "session-" + "0" * 16})
    assert codes == [200, 200, 429, 429]
    assert known.status_code == 200  # a sandbox that already exists is not a new one


async def test_only_the_configured_site_may_call_from_a_browser(tmp_path: Path) -> None:
    allowed = "https://sar-scout.example"
    async with make_client(tmp_path, allowed_origins=[allowed]) as client:
        ok = await client.options(
            "/api/events",
            headers={
                "Origin": allowed,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-session-id",
            },
        )
        other = await client.get("/api/health", headers={"Origin": "https://evil.example"})
        mine = await client.get("/api/health", headers={"Origin": allowed})
    assert ok.status_code == 200
    assert ok.headers["access-control-allow-origin"] == allowed
    assert "access-control-allow-origin" not in other.headers
    assert mine.headers["access-control-allow-origin"] == allowed
