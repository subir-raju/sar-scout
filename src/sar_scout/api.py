import os
import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from sar_scout.limits import RateLimiter, SandboxPool
from sar_scout.models import Decision, Event
from sar_scout.policy import DenyZone, Policy, decide
from sar_scout.sandbox import Sandbox, SandboxFull, utc_now
from sar_scout.scoring import score_event

try:
    VERSION = version("sar-scout")
except PackageNotFoundError:  # running from a source checkout that was never installed
    VERSION = "0.1.0"

SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


def valid_session(session_id: str | None) -> str:
    if not session_id or not SESSION_ID.match(session_id):
        raise HTTPException(
            400, "send a random X-Session-Id header of 16 to 64 letters or digits")
    return session_id


# request and response shapes -----------------------------------------------------------
class EventIn(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.:-]+$")
    source: str = Field(default="web", min_length=1, max_length=32)
    hazard: str = Field(min_length=1, max_length=20)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    severity: int = Field(ge=1, le=5)
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def assume_utc(cls, value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    def to_event(self) -> Event:
        return Event(**self.model_dump())


class PolicyIn(Policy):
    """The same policy, with sizes bounded because strangers send it."""

    allow_hazards: list[str] = Field(default_factory=list, max_length=8)
    deny_zones: list[DenyZone] = Field(default_factory=list, max_length=20)

    @field_validator("allow_hazards")
    @classmethod
    def short_names(cls, values: list[str]) -> list[str]:
        if any(len(name) > 20 for name in values):
            raise ValueError("hazard names are at most 20 characters")
        return values


class DecideRequest(BaseModel):
    event: EventIn
    policy: PolicyIn
    auto_used_today: int = Field(default=0, ge=0, le=10_000)
    now: datetime | None = None


class DecideResponse(BaseModel):
    score: float
    decision: Decision


class EventRequest(BaseModel):
    event: EventIn
    policy: PolicyIn


class ImageUsed(BaseModel):
    latitude: float
    longitude: float
    taken_at: datetime


class EventResult(BaseModel):
    duplicate: bool
    decided_at: datetime
    auto_used_today: int
    images_considered: list[ImageUsed]
    score: float | None
    decision: Decision | None
    task: dict[str, Any] | None
    summary: dict[str, int]


class TaskList(BaseModel):
    tasks: list[dict[str, Any]]
    summary: dict[str, int]


class AuditView(BaseModel):
    entries: list[dict[str, Any]]
    total: int
    intact: bool


def client_ip(request: Request) -> str:
    """The address of the caller. Behind one proxy, the last X-Forwarded-For entry is the
    one the proxy itself added, so it cannot be forged by the caller."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def create_api(
    *,
    pool: SandboxPool | None = None,
    ip_limiter: RateLimiter | None = None,
    new_sandbox_limiter: RateLimiter | None = None,
    allowed_origins: list[str] | None = None,
    allowed_origin_regex: str | None = None,
    now: Any = utc_now,
) -> FastAPI:
    # explicit None checks: an empty pool has length 0, which Python treats as false
    pool = SandboxPool() if pool is None else pool
    ip_limiter = RateLimiter(240) if ip_limiter is None else ip_limiter
    new_sandbox_limiter = RateLimiter(
        10) if new_sandbox_limiter is None else new_sandbox_limiter

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await pool.close()

    app = FastAPI(title="sar-scout API", version=VERSION, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["http://localhost:5173"],
        allow_origin_regex=allowed_origin_regex,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Session-Id"],
    )

    # guards ---------------------------------------------------------------------------
    async def guard_ip(request: Request) -> str:
        address = client_ip(request)
        if not ip_limiter.allow(address):
            raise HTTPException(
                429, "too many requests, wait a moment", headers={"Retry-After": "10"}
            )
        return address

    async def sandbox_for(
        address: Annotated[str, Depends(guard_ip)],
        x_session_id: Annotated[str | None, Header()] = None,
    ) -> Sandbox:
        session_id = valid_session(x_session_id)
        if not pool.has(session_id) and not new_sandbox_limiter.allow(address):
            raise HTTPException(
                429, "too many new sessions from this address", headers={"Retry-After": "60"}
            )
        return await pool.get(session_id)

    Box = Annotated[Sandbox, Depends(sandbox_for)]

    def summary_of(box: Sandbox) -> dict[str, int]:
        return box.summary()

    # routes ---------------------------------------------------------------------------
    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "version": VERSION,
            "tasking": "mock",
            "sandboxes": len(pool),
        }

    @app.post("/api/decide", response_model=DecideResponse, dependencies=[Depends(guard_ip)])
    async def decide_only(body: DecideRequest) -> DecideResponse:
        """Score and decide one event. Stateless: nothing is stored."""
        moment = body.now or now()
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        event = body.event.to_event()
        score = score_event(event, moment)
        return DecideResponse(
            score=score, decision=decide(
                body.policy, event, score, body.auto_used_today)
        )

    @app.post("/api/events", response_model=EventResult)
    async def send_event(body: EventRequest, box: Box) -> EventResult:
        """Run an event through the real pipeline in this visitor's sandbox."""
        try:
            outcome = await box.submit_event(body.event.to_event(), body.policy)
        except SandboxFull as exc:
            raise HTTPException(429, str(exc)) from exc
        return EventResult(
            duplicate=outcome.duplicate,
            decided_at=outcome.decided_at,
            auto_used_today=outcome.auto_used_today,
            images_considered=[
                ImageUsed(latitude=i.latitude,
                          longitude=i.longitude, taken_at=i.taken_at)
                for i in outcome.images
            ],
            score=outcome.score,
            decision=outcome.decision,
            task=outcome.task,
            summary=summary_of(box),
        )

    @app.get("/api/tasks", response_model=TaskList)
    async def list_tasks(box: Box) -> TaskList:
        return TaskList(tasks=box.tasks(), summary=summary_of(box))

    @app.post("/api/tick", response_model=TaskList)
    async def tick(box: Box) -> TaskList:
        """Send anything approved and ask the mock service how submitted tasks are doing."""
        await box.tick()
        return TaskList(tasks=box.tasks(), summary=summary_of(box))

    @app.post("/api/tasks/{task_id}/approve")
    async def approve(task_id: str, box: Box) -> dict[str, Any]:
        return await answer(box, task_id, approve=True)

    @app.post("/api/tasks/{task_id}/reject")
    async def reject(task_id: str, box: Box) -> dict[str, Any]:
        return await answer(box, task_id, approve=False)

    async def answer(box: Sandbox, task_id: str, *, approve: bool) -> dict[str, Any]:
        try:
            return await (box.approve(task_id) if approve else box.reject(task_id))
        except KeyError as exc:
            raise HTTPException(404, f"no task called {task_id}") from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/audit", response_model=AuditView)
    async def audit(box: Box, limit: int = 12) -> AuditView:
        entries, total = box.audit_entries(max(1, min(limit, 100)))
        return AuditView(entries=entries, total=total, intact=box.audit_intact())

    @app.post("/api/reset")
    async def reset(
        _: Annotated[str, Depends(guard_ip)],
        x_session_id: Annotated[str | None, Header()] = None,
    ) -> dict[str, str]:
        await pool.reset(valid_session(x_session_id))
        return {"status": "reset"}

    return app


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def app_from_env() -> FastAPI:
    origins = [o.strip() for o in os.getenv(
        "SCOUT_ALLOWED_ORIGINS", "").split(",") if o.strip()]
    return create_api(
        pool=SandboxPool(
            max_sandboxes=_env_int("SCOUT_MAX_SANDBOXES", 100),
            ttl_seconds=float(os.getenv("SCOUT_SANDBOX_TTL_SECONDS", "1800")),
            fail_rate=float(os.getenv("SCOUT_FAIL_RATE", "0.1")),
        ),
        ip_limiter=RateLimiter(_env_int("SCOUT_RATE_PER_MINUTE", 240)),
        allowed_origins=origins or None,
        allowed_origin_regex=os.getenv("SCOUT_ALLOWED_ORIGIN_REGEX") or None,
    )
