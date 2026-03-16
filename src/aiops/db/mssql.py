"""MSSQL backend using pymssql (sync, wrapped for async interface)."""

from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlparse

from aiops.core.log import get_logger
from aiops.db.base import DatabaseBase, _db_registry

logger = get_logger(__name__)


class MSSQLBackend(DatabaseBase):
    """MSSQL backend using pymssql. Runs sync operations in thread executor."""

    def __init__(self, url: str, **kwargs: Any) -> None:
        super().__init__(url, **kwargs)
        self._conn = None

    def _parse_url(self) -> dict:
        parsed = urlparse(self.url)
        return {
            "server": parsed.hostname or "localhost",
            "port": str(parsed.port or 1433),
            "user": parsed.username or "sa",
            "password": parsed.password or "",
            "database": parsed.path.lstrip("/"),
        }

    async def connect(self) -> None:
        try:
            import pymssql
        except ImportError:
            raise ImportError("pymssql not installed. Install with: pip install 'aiops[mssql]'")
        params = self._parse_url()
        params.update(self._kwargs)
        loop = asyncio.get_event_loop()
        self._conn = await loop.run_in_executor(None, lambda: pymssql.connect(**params))
        logger.info("MSSQL connected")

    async def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            logger.info("MSSQL disconnected")

    async def execute(self, query: str, *args: Any) -> Any:
        loop = asyncio.get_event_loop()

        def _exec():
            cursor = self._conn.cursor()
            cursor.execute(query, args or None)
            self._conn.commit()
            return cursor.rowcount

        return await loop.run_in_executor(None, _exec)

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        loop = asyncio.get_event_loop()

        def _fetch():
            cursor = self._conn.cursor(as_dict=True)
            cursor.execute(query, args or None)
            return list(cursor.fetchall())

        return await loop.run_in_executor(None, _fetch)

    async def fetch_one(self, query: str, *args: Any) -> dict | None:
        loop = asyncio.get_event_loop()

        def _fetch():
            cursor = self._conn.cursor(as_dict=True)
            cursor.execute(query, args or None)
            return cursor.fetchone()

        return await loop.run_in_executor(None, _fetch)

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
        loop = asyncio.get_event_loop()

        def _insert():
            cursor = self._conn.cursor()
            for d in data:
                cursor.execute(query, tuple(d.values()))
            self._conn.commit()

        await loop.run_in_executor(None, _insert)


_db_registry.register("mssql", MSSQLBackend)
