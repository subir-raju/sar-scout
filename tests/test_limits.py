from pathlib import Path

from sar_scout.limits import RateLimiter, SandboxPool


class FakeTime:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_limiter_allows_a_burst_then_refuses() -> None:
    clock = FakeTime()
    limiter = RateLimiter(3, 60, time_fn=clock)
    assert [limiter.allow("a") for _ in range(4)] == [True, True, True, False]


def test_the_limiter_counts_each_key_separately() -> None:
    limiter = RateLimiter(1, 60, time_fn=FakeTime())
    assert limiter.allow("a") and limiter.allow("b")
    assert not limiter.allow("a")


def test_the_limiter_recovers_when_the_window_passes() -> None:
    clock = FakeTime()
    limiter = RateLimiter(1, 60, time_fn=clock)
    assert limiter.allow("a") and not limiter.allow("a")
    clock.now += 61
    assert limiter.allow("a")


def test_the_limiter_forgets_old_keys_instead_of_growing_forever() -> None:
    clock = FakeTime()
    limiter = RateLimiter(5, 60, time_fn=clock, max_keys=10)
    for index in range(10):
        limiter.allow(f"old-{index}")
    clock.now += 120
    for index in range(5):
        limiter.allow(f"new-{index}")
    assert len(limiter._hits) <= 10


async def test_the_same_session_gets_the_same_sandbox(tmp_path: Path) -> None:
    pool = SandboxPool(base_dir=tmp_path)
    first = await pool.get("session-aaaaaaaaaaaaaaaa")
    assert await pool.get("session-aaaaaaaaaaaaaaaa") is first
    assert await pool.get("session-bbbbbbbbbbbbbbbb") is not first
    await pool.close()


async def test_idle_sandboxes_expire_and_their_files_go(tmp_path: Path) -> None:
    clock = FakeTime()
    pool = SandboxPool(base_dir=tmp_path, ttl_seconds=100, time_fn=clock)
    old = await pool.get("session-aaaaaaaaaaaaaaaa")
    assert pool.has("session-aaaaaaaaaaaaaaaa")
    clock.now += 101
    assert not pool.has("session-aaaaaaaaaaaaaaaa")
    await pool.get("session-bbbbbbbbbbbbbbbb")  # any visit sweeps the pool
    assert len(pool) == 1
    assert not old.directory.exists()
    await pool.close()


async def test_a_full_pool_drops_the_least_recently_used(tmp_path: Path) -> None:
    clock = FakeTime()
    pool = SandboxPool(base_dir=tmp_path, max_sandboxes=2, time_fn=clock)
    await pool.get("session-aaaaaaaaaaaaaaaa")
    clock.now += 1
    await pool.get("session-bbbbbbbbbbbbbbbb")
    clock.now += 1
    await pool.get("session-aaaaaaaaaaaaaaaa")  # a is now the freshest
    clock.now += 1
    await pool.get("session-cccccccccccccccc")
    assert pool.has("session-aaaaaaaaaaaaaaaa")
    assert not pool.has("session-bbbbbbbbbbbbbbbb")
    assert len(pool) == 2
    await pool.close()


async def test_reset_gives_a_fresh_sandbox(tmp_path: Path) -> None:
    pool = SandboxPool(base_dir=tmp_path)
    first = await pool.get("session-aaaaaaaaaaaaaaaa")
    second = await pool.reset("session-aaaaaaaaaaaaaaaa")
    assert second is not first
    assert not first.directory.exists()
    await pool.close()
