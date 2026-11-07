import sqlite3
from datetime import datetime
from pathlib import Path

from sar_scout.models import Event, Task, TaskStatus
from sar_scout.scoring import ImageRecord

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    auto INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
"""


class Store:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(path))
        self._conn.executescript(SCHEMA)

    # events ---------------------------------------------------------------
    def save_event(self, event: Event) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO events (id, data) VALUES (?, ?)",
            (event.id, event.model_dump_json()),
        )
        self._conn.commit()

    def get_event(self, event_id: str) -> Event | None:
        row = self._conn.execute(
            "SELECT data FROM events WHERE id = ?", (event_id,)).fetchone()
        return Event.model_validate_json(row[0]) if row else None

    def list_events(self) -> list[Event]:
        rows = self._conn.execute("SELECT data FROM events").fetchall()
        return [Event.model_validate_json(row[0]) for row in rows]

    # tasks ----------------------------------------------------------------
    def save_task(self, task: Task) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO tasks (id, event_id, status, auto, created_at, data) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                task.id,
                task.event_id,
                task.status.value,
                int(task.auto),
                task.created_at.isoformat(),
                task.model_dump_json(),
            ),
        )
        self._conn.commit()

    def get_task(self, task_id: str) -> Task | None:
        row = self._conn.execute(
            "SELECT data FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return Task.model_validate_json(row[0]) if row else None

    def list_tasks(self, status: TaskStatus | None = None) -> list[Task]:
        if status is None:
            rows = self._conn.execute(
                "SELECT data FROM tasks ORDER BY created_at").fetchall()
        else:
            rows = self._conn.execute(
                "SELECT data FROM tasks WHERE status = ? ORDER BY created_at", (
                    status.value,)
            ).fetchall()
        return [Task.model_validate_json(row[0]) for row in rows]

    def auto_count_since(self, since: datetime) -> int:
        """How many tasks the policy approved on its own since ``since`` (UTC timestamps)."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE auto = 1 AND created_at >= ?", (since.isoformat(),)
        ).fetchone()
        return int(row[0])

    def delivered_images(self) -> list[ImageRecord]:
        images = []
        for task in self.list_tasks(TaskStatus.FULFILLED):
            event = self.get_event(task.event_id)
            if event is not None:
                images.append(ImageRecord(event.latitude,
                              event.longitude, task.updated_at))
        return images
