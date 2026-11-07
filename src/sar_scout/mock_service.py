import asyncio
import math
import os
import random
import time
import uuid
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field


class TaskRequest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    window_hours: int = Field(ge=1, le=336)  # up to 14 days ahead


def accept_probability(window_hours: float) -> float:
    """Wider acquisition windows are easier to fit into a satellite's schedule."""
    return min(0.95, max(0.05, 0.35 + 0.15 * math.log2(window_hours / 6)))


def create_app(
    *,
    seed: int = 0,
    fail_rate: float = 0.0,
    fulfill_seconds: float = 0.0,
    latency: float = 0.0,
    accept_override: bool | None = None,
) -> FastAPI:
    app = FastAPI(title="Mock SAR tasking service", version="0.1.0")
    rng = random.Random(seed)
    tasks: dict[str, dict[str, Any]] = {}
    by_idempotency_key: dict[str, str] = {}

    async def chaos(authorization: Annotated[str | None, Header()] = None) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        if latency:
            await asyncio.sleep(latency)
        if rng.random() < fail_rate:
            raise HTTPException(status_code=503, detail="injected failure")

    def view(record: dict[str, Any]) -> dict[str, Any]:
        if record["status"] == "ACCEPTED" and time.monotonic() >= record["ready_at"]:
            record["status"] = "FULFILLED"
        return {key: value for key, value in record.items() if key != "ready_at"}

    @app.post("/v1/tasks", status_code=201, dependencies=[Depends(chaos)])
    async def create_task(
        request: TaskRequest,
        idempotency_key: Annotated[str | None, Header()] = None,
    ) -> dict[str, Any]:
        if idempotency_key and idempotency_key in by_idempotency_key:
            return view(tasks[by_idempotency_key[idempotency_key]])
        if accept_override is not None:
            accepted = accept_override
        else:
            accepted = rng.random() < accept_probability(request.window_hours)
        task_id = f"mock-{uuid.UUID(int=rng.getrandbits(128)).hex[:12]}"
        tasks[task_id] = {
            "id": task_id,
            "status": "ACCEPTED" if accepted else "REJECTED",
            "window_hours": request.window_hours,
            "latitude": request.latitude,
            "longitude": request.longitude,
            "ready_at": time.monotonic() + fulfill_seconds,
        }
        if idempotency_key:
            by_idempotency_key[idempotency_key] = task_id
        return view(tasks[task_id])

    @app.get("/v1/tasks/{task_id}", dependencies=[Depends(chaos)])
    async def get_task(task_id: str) -> dict[str, Any]:
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="unknown task")
        return view(tasks[task_id])

    @app.delete("/v1/tasks/{task_id}", dependencies=[Depends(chaos)])
    async def cancel_task(task_id: str) -> dict[str, Any]:
        if task_id not in tasks:
            raise HTTPException(status_code=404, detail="unknown task")
        record = tasks[task_id]
        if view(record)["status"] != "ACCEPTED":
            raise HTTPException(
                status_code=409, detail="task can no longer be cancelled")
        record["status"] = "CANCELLED"
        return view(record)

    return app


def app_from_env() -> FastAPI:
    return create_app(
        seed=int(os.getenv("MOCK_SEED", "0")),
        fail_rate=float(os.getenv("MOCK_FAIL_RATE", "0.0")),
        fulfill_seconds=float(os.getenv("MOCK_FULFILL_SECONDS", "5")),
        latency=float(os.getenv("MOCK_LATENCY", "0.0")),
    )
