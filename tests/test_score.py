from datetime import datetime, timedelta
from pathlib import Path

from sar_scout import Task, TaskStatus
from sar_scout.store import Store


def make_task(now: datetime, task_id: str = "t1", event_id: str = "e1", **fields) -> Task:
    return Task(id=task_id, event_id=event_id, created_at=now, updated_at=now, **fields)


def test_event_roundtrip(make_event) -> None:
    store = Store()
    event = make_event()
    store.save_event(event)

    assert store.get_event("ev1") == event
    assert store.get_event("missing") is None
    assert store.list_events() == [event]


def test_task_roundtrip(now: datetime) -> None:
    store = Store()
    task = make_task(now)
    store.save_task(task)

    assert store.get_task("t1") == task
    assert store.get_task("missing") is None


def test_saving_a_task_twice_updates_it(now: datetime) -> None:
    store = Store()
    store.save_task(make_task(now))
    store.save_task(make_task(now, status=TaskStatus.APPROVED))

    assert len(store.list_tasks()) == 1
    assert store.get_task("t1").status is TaskStatus.APPROVED


def test_list_tasks_filters_by_status(now: datetime) -> None:
    store = Store()
    store.save_task(make_task(now, "a", "ea"))
    store.save_task(make_task(now, "b", "eb", status=TaskStatus.APPROVED))

    assert [t.id for t in store.list_tasks(TaskStatus.APPROVED)] == ["b"]
    assert len(store.list_tasks()) == 2


def test_auto_count_only_counts_auto_tasks_since_the_cutoff(now: datetime) -> None:
    store = Store()
    store.save_task(make_task(now - timedelta(days=2), "old", "e1", auto=True))
    store.save_task(make_task(now, "today-auto", "e2", auto=True))
    store.save_task(make_task(now, "today-human", "e3", auto=False))

    assert store.auto_count_since(now.replace(hour=0, minute=0)) == 1


def test_delivered_images_come_from_fulfilled_tasks(make_event, now: datetime) -> None:
    store = Store()
    store.save_event(make_event(id="e1"))
    store.save_event(make_event(id="e2", latitude=-10.0))
    store.save_task(make_task(now, "a", "e1", status=TaskStatus.FULFILLED))
    store.save_task(make_task(now, "b", "e2"))

    images = store.delivered_images()
    assert [(i.latitude, i.longitude, i.taken_at)
            for i in images] == [(35.0, 139.0, now)]


def test_state_survives_reopening_a_file_database(tmp_path: Path, now: datetime) -> None:
    path = tmp_path / "state.db"
    Store(path).save_task(make_task(now))

    assert Store(path).get_task("t1") is not None
