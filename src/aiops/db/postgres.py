"""PostgreSQL async backend using asyncpg."""

from __future__ import annotations

from typing import Any

from aiops.core.log import get_logger
from aiops.db.base import DatabaseBase, _db_registry

logger = get_logger(__name__)


class PostgresBackend(DatabaseBase):
    """Async PostgreSQL backend using asyncpg."""

    def __init__(self, url: str, **kwargs: Any) -> None:
        super().__init__(url, **kwargs)
        self._pool = None

    async def connect(self) -> None:
        try:
            import asyncpg
        except ImportError:
            raise ImportError("asyncpg not installed. Install with: pip install 'aiops[postgres]'")
        self._pool = await asyncpg.create_pool(self.url, **self._kwargs)
        logger.info("PostgreSQL connection pool created")

    async def disconnect(self) -> None:
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQL connection pool closed")

    async def execute(self, query: str, *args: Any) -> str:
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def fetch_one(self, query: str, *args: Any) -> dict | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def insert(self, table: str, data: dict) -> Any:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(f"${i + 1}" for i in range(len(data)))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) RETURNING *"
        return await self.fetch_one(query, *data.values())

    async def insert_many(self, table: str, data: list[dict]) -> Any:
        if not data:
            return
        columns = ", ".join(data[0].keys())
        placeholders = ", ".join(f"${i + 1}" for i in range(len(data[0])))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        async with self._pool.acquire() as conn:
            await conn.executemany(query, [tuple(d.values()) for d in data])


_db_registry.register("postgresql", PostgresBackend)
