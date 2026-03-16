"""Redis async backend."""

from __future__ import annotations

from typing import Any

from aiops.core.log import get_logger
from aiops.db.base import DatabaseBase, _db_registry

logger = get_logger(__name__)


class RedisBackend(DatabaseBase):
    """Async Redis backend.

    Provides key-value operations. The SQL-like interface maps to:
    - insert(table, data) -> HSET table field1 val1 field2 val2 ...
    - fetch("key") -> GET/HGETALL
    - execute(command_string) -> raw Redis command
    """

    def __init__(self, url: str, **kwargs: Any) -> None:
        super().__init__(url, **kwargs)
        self._client = None

    async def connect(self) -> None:
        try:
            from redis.asyncio import from_url
        except ImportError:
            raise ImportError("redis not installed. Install with: pip install 'aiops[redis]'")
        self._client = from_url(self.url, decode_responses=True, **self._kwargs)
        await self._client.ping()
        logger.info("Redis connected")

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            logger.info("Redis disconnected")

    async def execute(self, query: str, *args: Any) -> Any:
        """Execute a raw Redis command. query is the command name, args are arguments."""
        return await self._client.execute_command(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        """Fetch: if key is a hash, returns [dict]; if string, returns [{"value": ...}]."""
        key_type = await self._client.type(query)
        if key_type == "hash":
            data = await self._client.hgetall(query)
            return [data] if data else []
        elif key_type == "string":
            val = await self._client.get(query)
            return [{"value": val}] if val else []
        elif key_type == "list":
            vals = await self._client.lrange(query, 0, -1)
            return [{"index": i, "value": v} for i, v in enumerate(vals)]
        elif key_type == "set":
            vals = await self._client.smembers(query)
            return [{"value": v} for v in vals]
        return []

    async def fetch_one(self, query: str, *args: Any) -> dict | None:
        results = await self.fetch(query, *args)
        return results[0] if results else None

    async def insert(self, table: str, data: dict) -> Any:
        """Insert data as a Redis hash."""
        await self._client.hset(table, mapping=data)
        return table

    async def insert_many(self, table: str, data: list[dict]) -> Any:
        """Insert multiple items as hash fields under table:index keys."""
        pipe = self._client.pipeline()
        for i, d in enumerate(data):
            pipe.hset(f"{table}:{i}", mapping=d)
        return await pipe.execute()

    # Redis-specific convenience methods

    async def get(self, key: str) -> str | None:
        return await self._client.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        await self._client.set(key, value, ex=ex)

    async def delete(self, *keys: str) -> int:
        return await self._client.delete(*keys)


_db_registry.register("redis", RedisBackend)
