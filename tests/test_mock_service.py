import httpx
import pytest

from sar_scout.mock_service import accept_probability, create_app

AUTH = {"Authorization": "Bearer test"}
BODY = {"latitude": 10.0, "longitude": 20.0, "window_hours": 24}


def make_http(**kwargs) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=create_app(**kwargs))
    return httpx.AsyncClient(transport=transport, base_url="http://mock")


def test_acceptance_grows_with_the_window() -> None:
    probabilities = [accept_probability(w) for w in (6, 12, 24, 48, 96, 336)]
    assert probabilities == sorted(probabilities)
    assert 0.05 <= probabilities[0] and probabilities[-1] <= 0.95


async def test_requires_a_bearer_token() -> None:
    async with make_http() as http:
        assert (await http.post("/v1/tasks", json=BODY)).status_code == 401


async def test_window_over_14_days_is_rejected() -> None:
    async with make_http() as http:
        response = await http.post("/v1/tasks", json={**BODY, "window_hours": 400}, headers=AUTH)
        assert response.status_code == 422


async def test_accepted_task_becomes_fulfilled() -> None:
    async with make_http(accept_override=True) as http:
        created = await http.post("/v1/tasks", json=BODY, headers=AUTH)
        assert created.status_code == 201
        task_id = created.json()["id"]

        fetched = await http.get(f"/v1/tasks/{task_id}", headers=AUTH)
        assert fetched.json()["status"] == "FULFILLED"


async def test_rejected_acquisition_is_reported() -> None:
    async with make_http(accept_override=False) as http:
        created = await http.post("/v1/tasks", json=BODY, headers=AUTH)
        assert created.json()["status"] == "REJECTED"


async def test_same_idempotency_key_returns_the_same_task() -> None:
    headers = {**AUTH, "Idempotency-Key": "k1"}
    async with make_http(accept_override=True) as http:
        first = await http.post("/v1/tasks", json=BODY, headers=headers)
        second = await http.post("/v1/tasks", json=BODY, headers=headers)
        assert first.json()["id"] == second.json()["id"]


async def test_cancel_works_only_while_pending() -> None:
    async with make_http(accept_override=True, fulfill_seconds=1000) as http:
        task_id = (await http.post("/v1/tasks", json=BODY, headers=AUTH)).json()["id"]
        first = await http.delete(f"/v1/tasks/{task_id}", headers=AUTH)
        second = await http.delete(f"/v1/tasks/{task_id}", headers=AUTH)
        assert first.json()["status"] == "CANCELLED"
        assert second.status_code == 409


async def test_unknown_task_is_404() -> None:
    async with make_http() as http:
        assert (await http.get("/v1/tasks/nope", headers=AUTH)).status_code == 404


@pytest.mark.parametrize("seed", [1, 2])
async def test_failure_injection_is_reproducible(seed: int) -> None:
    async def codes() -> list[int]:
        async with make_http(seed=seed, fail_rate=0.5) as http:
            return [(await http.get("/v1/tasks/x", headers=AUTH)).status_code for _ in range(10)]

    assert await codes() == await codes()
