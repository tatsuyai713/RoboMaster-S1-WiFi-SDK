from __future__ import annotations

import threading
import time


OFFICIAL_SUBSCRIPTION_FREQUENCIES = {1, 5, 10, 20, 50}


def rate_limited_callback(freq: int, callback):  # noqa: ANN001
    frequency = int(freq)
    if frequency not in OFFICIAL_SUBSCRIPTION_FREQUENCIES:
        raise ValueError("freq must be one of 1, 5, 10, 20, or 50 Hz")
    period = 1.0 / frequency
    deadline = 0.0
    lock = threading.Lock()

    def limited(value):  # noqa: ANN001
        nonlocal deadline
        now = time.monotonic()
        with lock:
            if now < deadline:
                return
            if deadline == 0.0:
                deadline = now + period
            else:
                deadline += period
                if deadline <= now:
                    deadline += (int((now - deadline) / period) + 1) * period
        callback(value)

    return limited
