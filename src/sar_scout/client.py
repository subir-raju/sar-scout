import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import httpx


class TaskingError(Exception):
    """Base class for client errors."""


class TransientError(TaskingError):
    """Network, 429 or 5xx problems that outlasted every retry. Safe to try again later."""


class RequestRejected(TaskingError):
    """The server refused the request (4xx). Repeating it unchanged will not help."""


@dataclass(frozen=True)
class RemoteTask:
    id: str
    status: str
    window_hours: int


RETRY_STATUS = {429, 500, 502, 503, 504}


class TaskingClient:
    def __init__(
        self,
        base_url: str,
        token: str = "demo-token",
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        max_retries: int = 4,
        base_delay: float = 0.2,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        jitter: Callable[[], float] = random.random,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            transport=transport,
            timeout=10.0,
            headers={"Authorization": f"Bearer {token}"},
        )
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._sleep = sleep
        self._jitter = jitter

    async def aclose(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._http.request(method, path, **kwargs)
            except httpx.TransportError as exc:
                last_error = exc
            else:
                if response.status_code in RETRY_STATUS:
                    last_error = TransientError(f"HTTP {response.status_code}")
                elif response.status_code >= 400:
                    raise RequestRejected(
                        f"HTTP {response.status_code}: {response.text}")
                else:
                    return response
            if attempt < self.max_retries:
                # exponential backoff with jitter: base * 2^attempt * [0.5, 1.5)
                await self._sleep(self.base_delay * 2**attempt * (0.5 + self._jitter()))
        raise TransientError(
            f"gave up after {self.max_retries + 1} attempts: {last_error}")

    @staticmethod
    def _remote(data: dict[str, Any]) -> RemoteTask:
        return RemoteTask(
            id=data["id"], status=data["status"], window_hours=int(
                data["window_hours"])
        )

    async def create_task(
        self, latitude: float, longitude: float, window_hours: int, idempotency_key: str
    ) -> RemoteTask:
        response = await self._request(
            "POST",
            "/v1/tasks",
            json={"latitude": latitude, "longitude": longitude,
                  "window_hours": window_hours},
            headers={"Idempotency-Key": idempotency_key},
        )
        return self._remote(response.json())

    async def get_task(self, remote_id: str) -> RemoteTask:
        response = await self._request("GET", f"/v1/tasks/{remote_id}")
        return self._remote(response.json())

    async def cancel_task(self, remote_id: str) -> RemoteTask:
        response = await self._request("DELETE", f"/v1/tasks/{remote_id}")
        return self._remote(response.json())
