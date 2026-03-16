"""MySQL async backend using aiomysql."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from aiops.core.log import get_logger
from aiops.db.base import DatabaseBase, _db_registry

logger = get_logger(__name__)


class MySQLBackend(DatabaseBase):
    """Async MySQL backend using aiomysql."""

    def __init__(self, url: str, **kwargs: Any) -> None:
        super().__init__(url, **kwargs)
        self._pool = None

    def _parse_url(self) -> dict:
        parsed = urlparse(self.url)
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "user": parsed.username or "root",
            "password": parsed.password or "",
            "db": parsed.path.lstrip("/"),
        }

    async def connect(self) -> None:
        try:
            import aiomysql
        except ImportError:
            raise ImportError("aiomysql not installed. Install with: pip install 'aiops[mysql]'")
        params = self._parse_url()
        params.update(self._kwargs)
        self._pool = await aiomysql.create_pool(**params)
        logger.info("MySQL connection pool created")

    async def disconnect(self) -> None:
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            logger.info("MySQL connection pool closed")

    async def execute(self, query: str, *args: Any) -> Any:
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, args or None)
                await conn.commit()
                return cur.rowcount

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        import aiomysql

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, args or None)
                return list(await cur.fetchall())

    async def fetch_one(self, query: str, *args: Any) -> dict | None:
        import aiomysql

        async with self._pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, args or None)
                return await cur.fetchone()

    async def insert(self, table: str, data: dict) -> Any:
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["%s"] * len(data))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        return await self.execute(query, *data.values())

    async def insert_many(self, table: str, data: list[dict]) -> Any:
        if not data:
            return
        columns = ", ".join(data[0].keys())
        placeholders = ", ".join(["%s"] * len(data[0]))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(query, [tuple(d.values()) for d in data])
                await conn.commit()


_db_registry.register("mysql", MySQLBackend)
