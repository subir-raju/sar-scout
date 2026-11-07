import hashlib
import shutil
import tempfile
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sar_scout.sandbox import Sandbox


class RateLimiter:
    """Sliding window: at most ``limit`` calls per ``window_seconds`` for each key."""

    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        *,
        time_fn: Callable[[], float] = time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self.limit = limit
        self.window = window_seconds
        self._time = time_fn
        self._max_keys = max_keys
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = self._time()
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        if len(self._hits) > self._max_keys:
            self._prune(now)
        return True

    def _prune(self, now: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= now - self.window]:
            del self._hits[key]
        while len(self._hits) > self._max_keys:  # still too many: drop the oldest keys
            del self._hits[next(iter(self._hits))]


class SandboxPool:
    """At most ``max_sandboxes`` live at once, each dropped after ``ttl_seconds`` idle."""

    def __init__(
        self,
        *,
        max_sandboxes: int = 100,
        ttl_seconds: float = 1800.0,
        base_dir: Path | None = None,
        time_fn: Callable[[], float] = time.monotonic,
        **sandbox_options: Any,
    ) -> None:
        self.max_sandboxes = max_sandboxes
        self.ttl = ttl_seconds
        self._time = time_fn
        self._options = sandbox_options
        self._base = base_dir or Path(
            tempfile.mkdtemp(prefix="scout-sandboxes-"))
        self._owns_base = base_dir is None
        self._items: OrderedDict[str, tuple[Sandbox, float]] = OrderedDict()

    def __len__(self) -> int:
        return len(self._items)

    def has(self, session_id: str) -> bool:
        item = self._items.get(session_id)
        return item is not None and item[1] + self.ttl > self._time()

    async def get(self, session_id: str) -> Sandbox:
        retired = self._expired()
        item = self._items.get(session_id)
        if item is None:
            while len(self._items) >= self.max_sandboxes:  # least recently used goes first
                _, (old, _) = self._items.popitem(last=False)
                retired.append(old)
            sandbox = self._create(session_id)
        else:
            sandbox = item[0]
        self._items[session_id] = (sandbox, self._time())
        self._items.move_to_end(session_id)
        for old in retired:
            await old.close()
        return sandbox

    async def reset(self, session_id: str) -> Sandbox:
        item = self._items.pop(session_id, None)
        if item is not None:
            await item[0].close()
        return await self.get(session_id)

    async def close(self) -> None:
        sandboxes = [box for box, _ in self._items.values()]
        self._items.clear()
        for box in sandboxes:
            await box.close()
        if self._owns_base:
            shutil.rmtree(self._base, ignore_errors=True)

    def _expired(self) -> list[Sandbox]:
        cutoff = self._time() - self.ttl
        stale = [sid for sid, (_, used)
                 in self._items.items() if used <= cutoff]
        return [self._items.pop(sid)[0] for sid in stale]

    def _create(self, session_id: str) -> Sandbox:
        seed = int.from_bytes(hashlib.sha256(
            session_id.encode()).digest()[:4], "big")
        self._base.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(dir=self._base))
        return Sandbox(directory, seed=seed, **self._options)
