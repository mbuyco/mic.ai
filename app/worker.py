from __future__ import annotations

import asyncio

from app.config import settings
from app.jobs import enqueue_due_schedules, process_inbound_message, send_outbound_message
from app.runtime import runtime


async def handle_job(job_type: str, payload: dict) -> bool:
    with runtime.repo_scope() as repo:
        if job_type == "inbound.process_message":
            return process_inbound_message(repo, runtime.queue, payload)
        if job_type == "outbound.send_text":
            return await send_outbound_message(repo, payload)
        if job_type == "scheduler.dispatch_due":
            enqueue_due_schedules(repo, runtime.queue)
            return True
    return False


async def worker_loop() -> None:
    runtime.initialize()
    if runtime.redis_queue is None:
        return

    while True:
        job = runtime.redis_queue.dequeue(settings.queue_poll_timeout_seconds)
        if job is None:
            await asyncio.sleep(0.05)
            continue
        await handle_job(job.job_type, job.payload)


def main() -> None:
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
