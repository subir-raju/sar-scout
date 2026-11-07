import asyncio
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import httpx
import typer

from sar_scout import evaluation, usgs
from sar_scout.audit import AuditLog
from sar_scout.client import TaskingClient
from sar_scout.dataset import load_dataset, save_dataset
from sar_scout.mock_service import create_app
from sar_scout.models import Event, TaskStatus
from sar_scout.orchestrator import Clock, Orchestrator
from sar_scout.policy import load_policy
from sar_scout.store import Store
from sar_scout.synthetic import generate_dataset

app = typer.Typer(no_args_is_help=True,
                  help="Bounded-autonomy SAR tasking prototype.")

DbOption = Annotated[str, typer.Option("--db", help="SQLite database file.")]
AuditOption = Annotated[str, typer.Option(
    "--audit", help="Hash-chained audit log (JSONL).")]
PolicyOption = Annotated[str, typer.Option(
    "--policy", help="Autonomy policy (TOML).")]
EventsOption = Annotated[str, typer.Option(
    "--events", help="Labelled events (JSON).")]


def build_orchestrator(
    db: str, audit: str, policy: str, client: TaskingClient, clock: Clock | None = None
) -> Orchestrator:
    return Orchestrator(
        Store(db), client, load_policy(policy), AuditLog(audit), clock=clock
    )


def print_summary(counts: dict[str, int]) -> None:
    typer.echo("\nTask summary:")
    for status in TaskStatus:
        if counts.get(status.value):
            typer.echo(f"  {status.value:<10} {counts[status.value]}")


@app.command()
def synth(
    out: Annotated[str, typer.Option(
        help="Output JSON file.")] = "data/events.json",
    days: int = 120,
    seed: int = 1,
) -> None:
    """Generate a synthetic earthquake dataset."""
    items = generate_dataset(days=days, seed=seed)
    save_dataset(items, out)
    typer.echo(f"wrote {len(items)} synthetic events to {out}")


@app.command("fetch-usgs")
def fetch_usgs(
    out: Annotated[str, typer.Option(
        help="Output JSON file.")] = "data/usgs.json",
    days: int = 30,
    minmag: float = 5.0,
) -> None:
    """Download real earthquakes from the USGS FDSN service (needs internet)."""
    items = usgs.fetch(days=days, min_magnitude=minmag)
    save_dataset(items, out)
    typer.echo(
        f"wrote {len(items)} USGS events (M{minmag}+, last {days} days) to {out}")


@app.command()
def demo(
    events: EventsOption = "data/events.json",
    policy: PolicyOption = "policy.toml",
    db: DbOption = "demo.db",
    audit: AuditOption = "demo-audit.jsonl",
    days: Annotated[int, typer.Option(
        help="Replay the last N days of the dataset.")] = 14,
    seed: int = 1,
    fail_rate: Annotated[float, typer.Option(
        help="Injected API failure rate.")] = 0.1,
) -> None:
    """Replay recent events day by day against an in-process mock API."""
    for path in (db, audit):
        Path(path).unlink(missing_ok=True)
    all_events = [item.event for item in load_dataset(events)]
    cutoff = max(event.observed_at for event in all_events) - \
        timedelta(days=days)
    by_day: dict[date, list[Event]] = defaultdict(list)
    for event in all_events:
        if event.observed_at >= cutoff:
            by_day[event.observed_at.date()].append(event)

    transport = httpx.ASGITransport(
        app=create_app(seed=seed, fail_rate=fail_rate))
    client = TaskingClient("http://mock", transport=transport, base_delay=0.01)
    clock = Clock()
    orchestrator = build_orchestrator(db, audit, policy, client, clock)

    async def replay() -> dict[str, int]:
        counts: dict[str, int] = {}
        for day in sorted(by_day):
            clock.fixed = datetime(day.year, day.month,
                                   day.day, 23, 59, tzinfo=timezone.utc)
            counts = await orchestrator.run_once(by_day[day])
        await client.aclose()
        return counts

    print_summary(asyncio.run(replay()))
    typer.echo(f"\naudit log intact: {AuditLog(audit).verify()}")
    typer.echo(f"next: scout status --db {db}")


@app.command()
def run(
    events: EventsOption = "data/usgs.json",
    policy: PolicyOption = "policy.toml",
    db: DbOption = "scout.db",
    audit: AuditOption = "audit.jsonl",
    base_url: Annotated[str, typer.Option(
        help="Tasking API base URL.")] = "http://localhost:8000",
    token: str = "demo-token",
    as_of: Annotated[str | None, typer.Option(
        help="ISO time to treat as 'now'.")] = None,
    watch: Annotated[int, typer.Option(
        help="Repeat every N seconds (0 = run once).")] = 0,
) -> None:
    """Run one agent cycle against an HTTP tasking API (for example the mock service)."""
    clock = Clock(datetime.fromisoformat(as_of) if as_of else None)
    client = TaskingClient(base_url, token)
    orchestrator = build_orchestrator(db, audit, policy, client, clock)

    async def cycle() -> dict[str, int]:
        return await orchestrator.run_once([item.event for item in load_dataset(events)])

    while True:
        print_summary(asyncio.run(cycle()))
        if not watch:
            break
        time.sleep(watch)


@app.command()
def status(db: DbOption = "scout.db") -> None:
    """List all tasks."""
    tasks = Store(db).list_tasks()
    if not tasks:
        typer.echo("no tasks")
    for task in tasks:
        mode = "auto" if task.auto else "human"
        typer.echo(
            f"{task.id:<18} {task.status.value:<10} score={task.score:5.2f} {mode:<5} {task.reason}"
        )


@app.command()
def approve(
    task_id: str,
    db: DbOption = "scout.db",
    audit: AuditOption = "audit.jsonl",
    policy: PolicyOption = "policy.toml",
) -> None:
    """Approve a proposed task. The next `run` submits it."""
    orchestrator = build_orchestrator(
        db, audit, policy, TaskingClient("http://unused"))
    typer.echo(
        f"{orchestrator.approve(task_id).id} -> {TaskStatus.APPROVED.value}")


@app.command()
def reject(
    task_id: str,
    db: DbOption = "scout.db",
    audit: AuditOption = "audit.jsonl",
    policy: PolicyOption = "policy.toml",
) -> None:
    """Reject (cancel) a proposed task."""
    orchestrator = build_orchestrator(
        db, audit, policy, TaskingClient("http://unused"))
    typer.echo(
        f"{orchestrator.reject(task_id).id} -> {TaskStatus.CANCELLED.value}")


@app.command("eval")
def evaluate_command(
    events: EventsOption = "data/events.json",
    daily_budget: int = 1,
    seeds: int = 20,
    plot: Annotated[str | None, typer.Option(
        help="Save a PNG chart here.")] = None,
) -> None:
    """Compare random, severity-only and scorer strategies under a daily budget."""
    results = evaluation.evaluate(load_dataset(
        events), daily_budget=daily_budget, seeds=seeds)
    typer.echo(evaluation.format_table(results))
    if plot:
        evaluation.plot(results, plot)
        typer.echo(f"\nchart saved to {plot}")


@app.command("verify-audit")
def verify_audit(audit: AuditOption = "audit.jsonl") -> None:
    """Check the audit log's hash chain."""
    ok = AuditLog(audit).verify()
    typer.echo("audit log OK" if ok else "audit log TAMPERED")
    raise typer.Exit(code=0 if ok else 1)


if __name__ == "__main__":
    app()
