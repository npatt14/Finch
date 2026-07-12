from app.ratelimit import SlidingWindowLimiter


def test_sliding_window_allows_up_to_max_then_blocks():
    clock = [1000.0]
    lim = SlidingWindowLimiter(2, 10, now=lambda: clock[0])
    assert lim.allow("a") is True
    assert lim.allow("a") is True
    assert lim.allow("a") is False


def test_window_expiry_frees_capacity():
    clock = [1000.0]
    lim = SlidingWindowLimiter(1, 10, now=lambda: clock[0])
    assert lim.allow("a") is True
    assert lim.allow("a") is False
    clock[0] += 11
    assert lim.allow("a") is True


def test_keys_are_independent():
    lim = SlidingWindowLimiter(1, 10)
    assert lim.allow("a") is True
    assert lim.allow("b") is True
    assert lim.allow("a") is False


def test_zero_max_disables_limit():
    lim = SlidingWindowLimiter(0, 10)
    assert all(lim.allow("a") for _ in range(100))
