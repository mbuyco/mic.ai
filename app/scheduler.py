from __future__ import annotations

import time

from app.runtime import runtime


def run_scheduler_loop(interval_seconds: int = 15) -> None:
    runtime.initialize()
    while True:
        runtime.queue.enqueue("scheduler.dispatch_due", {})
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_scheduler_loop()
