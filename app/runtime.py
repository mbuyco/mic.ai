from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import redis

from app.config import settings
from app.db import init_db
from app.db import session_scope as db_session_scope
from app.queue import InMemoryJobQueue, JobQueue, RedisJobQueue
from app.repository import Repository


class Runtime:
    def __init__(self) -> None:
        self.queue: JobQueue = InMemoryJobQueue()
        self.redis_queue: RedisJobQueue | None = None

    def initialize(self) -> None:
        init_db()
        if settings.app_env != "test":
            try:
                client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
                client.ping()
                self.redis_queue = RedisJobQueue(client)
                self.queue = self.redis_queue
            except Exception:
                self.redis_queue = None

    @contextmanager
    def repo_scope(self) -> Iterator[Repository]:
        with db_session_scope() as session:
            yield Repository(session)

    def set_test_queue(self, queue: JobQueue) -> None:
        self.queue = queue
        self.redis_queue = None


runtime = Runtime()
