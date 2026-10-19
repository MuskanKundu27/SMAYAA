from app.core.rate_limit import SlidingWindowLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_limiter_allows_up_to_the_limit_per_key() -> None:
    limiter = SlidingWindowLimiter(max_events=2, window_seconds=60, clock=FakeClock())

    assert limiter.allow("a")
    assert limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")  # keys are independent


def test_limiter_allows_again_once_old_events_leave_the_window() -> None:
    clock = FakeClock()
    limiter = SlidingWindowLimiter(max_events=1, window_seconds=60, clock=clock)
    assert limiter.allow("a")

    clock.now += 59
    assert not limiter.allow("a")
    clock.now += 1
    assert limiter.allow("a")
