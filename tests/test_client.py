import httpx
import pytest

from sar_scout.client import RequestRejected, TaskingClient, TransientError

OK = {"id": "r1", "status": "ACCEPTED", "window_hours": 12}


async def no_sleep(_: float) -> None:
    return None


def make_client(handler, **kwargs) -> TaskingClient:
    return TaskingClient(
        "http://tasking.test",
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
        jitter=lambda: 0.5,
        **kwargs,
    )


async def test_retries_then_succeeds() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503) if len(calls) < 3 else httpx.Response(201, json=OK)

    remote = await make_client(handler).create_task(1, 2, 12, "key")

    assert remote.id == "r1"
    assert len(calls) == 3


async def test_gives_up_after_max_retries() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(TransientError):
        await make_client(handler, max_retries=2).get_task("r1")
    assert len(calls) == 3


async def test_client_errors_are_not_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(422, text="bad request")

    with pytest.raises(RequestRejected):
        await make_client(handler).create_task(1, 2, 12, "key")
    assert len(calls) == 1


async def test_rate_limiting_is_retried() -> None:
    responses = iter([httpx.Response(429), httpx.Response(200, json=OK)])

    remote = await make_client(lambda request: next(responses)).get_task("r1")

    assert remote.status == "ACCEPTED"


async def test_network_errors_are_retried() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("connection refused")
        return httpx.Response(200, json=OK)

    assert (await make_client(handler).get_task("r1")).id == "r1"


async def test_backoff_grows_exponentially() -> None:
    delays: list[float] = []

    async def record(delay: float) -> None:
        delays.append(delay)

    client = TaskingClient(
        "http://tasking.test",
        transport=httpx.MockTransport(lambda request: httpx.Response(503)),
        sleep=record,
        jitter=lambda: 0.5,
        base_delay=1.0,
        max_retries=3,
    )
    with pytest.raises(TransientError):
        await client.get_task("r1")

    assert delays == [1.0, 2.0, 4.0]


async def test_idempotency_key_is_sent() -> None:
    seen: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers.get("Idempotency-Key")
        return httpx.Response(201, json=OK)

    await make_client(handler).create_task(1, 2, 12, "task-1-a0")

    assert seen["key"] == "task-1-a0"
