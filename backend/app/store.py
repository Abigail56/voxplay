"""Short-lived shared state: rate limits, liveness phrases, game rooms and live updates.

RedisStore is used when REDIS_URL is set (docker compose, the Space), so
every API instance sees the same counters, phrases and rooms, and a live update
published by one instance reaches the WebSockets of all of them (Redis
pub/sub). MemoryStore keeps the same data in this process; it is used by the
tests and when no Redis is configured.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol


class Store(Protocol):
    async def incr(self, key: str, ttl_seconds: int) -> int:
        """Add 1 to a counter and return it. The counter disappears ttl_seconds after it was created."""
        ...

    async def put(self, key: str, value: str, ttl_seconds: int) -> None: ...

    async def take(self, key: str) -> str | None:
        """Get a value and delete it in one step, so it can only ever be read once."""
        ...

    async def get(self, key: str) -> str | None: ...

    async def delete(self, key: str) -> None: ...

    def lock(self, key: str, timeout: float = 10.0) -> AbstractAsyncContextManager:
        """Only one request at a time (on any instance) inside `async with store.lock(key):`."""
        ...

    async def set_add(self, key: str, member: str) -> None: ...

    async def set_remove(self, key: str, member: str) -> None: ...

    async def set_members(self, key: str) -> set[str]: ...

    async def publish(self, channel: str, message: str) -> None: ...

    def subscribe(self, *channels: str) -> AbstractAsyncContextManager[AsyncIterator[tuple[str, str]]]:
        """`async with store.subscribe(...) as events:` listens from the moment the block starts;
        `async for channel, message in events` then yields everything published on those channels."""
        ...

    async def close(self) -> None: ...


class RedisStore:
    def __init__(self, url: str) -> None:
        import redis.asyncio as redis

        self._redis = redis.from_url(url, decode_responses=True)

    async def incr(self, key: str, ttl_seconds: int) -> int:
        async with self._redis.pipeline(transaction=True) as pipe:
            # NX: only the first hit in a window sets the expiry.
            count, _ = await pipe.incr(key).expire(key, ttl_seconds, nx=True).execute()
        return int(count)

    async def put(self, key: str, value: str, ttl_seconds: int) -> None:
        await self._redis.set(key, value, ex=ttl_seconds)

    async def take(self, key: str) -> str | None:
        return await self._redis.getdel(key)

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)

    def lock(self, key: str, timeout: float = 10.0) -> AbstractAsyncContextManager:
        return self._redis.lock(f"lock:{key}", timeout=timeout, blocking_timeout=timeout)

    async def set_add(self, key: str, member: str) -> None:
        await self._redis.sadd(key, member)

    async def set_remove(self, key: str, member: str) -> None:
        await self._redis.srem(key, member)

    async def set_members(self, key: str) -> set[str]:
        return set(await self._redis.smembers(key))

    async def publish(self, channel: str, message: str) -> None:
        await self._redis.publish(channel, message)

    @asynccontextmanager
    async def subscribe(self, *channels: str) -> AsyncIterator[AsyncIterator[tuple[str, str]]]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(*channels)

        async def events() -> AsyncIterator[tuple[str, str]]:
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    yield msg["channel"], msg["data"]

        try:
            yield events()
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()

    async def close(self) -> None:
        await self._redis.aclose()


class MemoryStore:
    """The same behaviour as RedisStore, inside this process."""

    def __init__(self, max_keys: int = 100_000) -> None:
        self.max_keys = max_keys
        self._data: dict[str, tuple[str | int, float]] = {}  # key -> (value, expires at)
        self._sets: dict[str, set[str]] = defaultdict(set)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._listeners: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def _live(self, key: str):
        item = self._data.get(key)
        if item and item[1] <= time.monotonic():
            del self._data[key]
            return None
        return item

    def _make_room(self) -> None:
        if len(self._data) >= self.max_keys:
            now = time.monotonic()
            self._data = {k: v for k, v in self._data.items() if v[1] > now}
        while len(self._data) >= self.max_keys:
            self._data.pop(next(iter(self._data)))  # forget the oldest

    async def incr(self, key: str, ttl_seconds: int) -> int:
        item = self._live(key)
        if item is None:
            self._make_room()
            item = (0, time.monotonic() + ttl_seconds)
        count = int(item[0]) + 1
        self._data[key] = (count, item[1])
        return count

    async def put(self, key: str, value: str, ttl_seconds: int) -> None:
        self._make_room()
        self._data[key] = (value, time.monotonic() + ttl_seconds)

    async def take(self, key: str) -> str | None:
        item = self._live(key)
        if item is None:
            return None
        del self._data[key]
        return str(item[0])

    async def get(self, key: str) -> str | None:
        item = self._live(key)
        return None if item is None else str(item[0])

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def lock(self, key: str, timeout: float = 10.0) -> AbstractAsyncContextManager:
        return self._locks[key]

    async def set_add(self, key: str, member: str) -> None:
        self._sets[key].add(member)

    async def set_remove(self, key: str, member: str) -> None:
        self._sets[key].discard(member)

    async def set_members(self, key: str) -> set[str]:
        return set(self._sets[key])

    async def publish(self, channel: str, message: str) -> None:
        for queue in list(self._listeners[channel]):
            queue.put_nowait((channel, message))

    @asynccontextmanager
    async def subscribe(self, *channels: str) -> AsyncIterator[AsyncIterator[tuple[str, str]]]:
        queue: asyncio.Queue = asyncio.Queue()
        for c in channels:
            self._listeners[c].add(queue)

        async def events() -> AsyncIterator[tuple[str, str]]:
            while True:
                yield await queue.get()

        try:
            yield events()
        finally:
            for c in channels:
                self._listeners[c].discard(queue)

    async def close(self) -> None:
        self._data.clear()
        self._sets.clear()


def make_store(redis_url: str) -> Store:
    return RedisStore(redis_url) if redis_url else MemoryStore()
