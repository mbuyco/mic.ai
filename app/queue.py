from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import redis


@dataclass
class JobEnvelope:
    job_type: str
    payload: dict


class JobQueue(Protocol):
    def enqueue(self, job_type: str, payload: dict) -> None:
        ...


class RedisJobQueue:
    def __init__(self, redis_client: redis.Redis, queue_name: str = "micai:jobs"):
        self.redis = redis_client
        self.queue_name = queue_name

    def enqueue(self, job_type: str, payload: dict) -> None:
        item = JobEnvelope(job_type=job_type, payload=payload)
        self.redis.lpush(self.queue_name, json.dumps(item.__dict__))

    def dequeue(self, timeout_seconds: int) -> JobEnvelope | None:
        item = self.redis.brpop(self.queue_name, timeout=timeout_seconds)
        if item is None:
            return None
        _, raw = item
        data = json.loads(raw)
        return JobEnvelope(job_type=data["job_type"], payload=data["payload"])


class InMemoryJobQueue:
    def __init__(self):
        self.items: list[JobEnvelope] = []

    def enqueue(self, job_type: str, payload: dict) -> None:
        self.items.append(JobEnvelope(job_type=job_type, payload=payload))

    def dequeue(self, timeout_seconds: int = 0) -> JobEnvelope | None:
        if not self.items:
            return None
        return self.items.pop(0)
