"""Unified async database interface with pluggable backends."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from aiops.core.log import get_logger
from aiops.core.plugin import PluginRegistry

logger = get_logger(__name__)

_db_registry = PluginRegistry("database")


class DatabaseBase:
    """Abstract async database interface."""

    def __init__(self, url: str, **kwargs: Any) -> None:
        self.url = url
        self._kwargs = kwargs

    async def connect(self) -> None:
        raise NotImplementedError

    async def disconnect(self) -> None:
        raise NotImplementedError

    async def execute(self, query: str, *args: Any) -> Any:
        raise NotImplementedError

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        raise NotImplementedError

    async def fetch_one(self, query: str, *args: Any) -> dict | None:
        raise NotImplementedError

    async def insert(self, table: str, data: dict) -> Any:
        raise NotImplementedError

    async def insert_many(self, table: str, data: list[dict]) -> Any:
        raise NotImplementedError

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.disconnect()


class Database:
    """Unified database facade. Auto-detects backend from URL scheme.

    Usage:
        db = Database(url="postgresql://user:pass@localhost/mydb")
        async with db:
            rows = await db.fetch("SELECT * FROM users")

        # Or manually:
        await db.connect()
        await db.insert("users", {"name": "alice", "age": 30})
        await db.disconnect()
    """

    def __init__(self, url: str, **kwargs: Any) -> None:
        self.url = url
        _ensure_backends_registered()
        backend_key = self._detect_backend(url)
        backend_cls = _db_registry.get(backend_key)
        self._backend: DatabaseBase = backend_cls(url=url, **kwargs)
        logger.info(f"Database initialized: backend={backend_key}")

    @staticmethod
    def _detect_backend(url: str) -> str:
        scheme = urlparse(url).scheme.lower().split("+")[0]
        mapping = {
            "postgresql": "postgresql",
            "postgres": "postgresql",
            "mysql": "mysql",
            "mssql": "mssql",
            "mongodb": "mongodb",
            "mongo": "mongodb",
            "redis": "redis",
            "rediss": "redis",
        }
        backend = mapping.get(scheme)
        if not backend:
            raise ValueError(
                f"Unknown database scheme '{scheme}'. "
                f"Supported: {', '.join(sorted(set(mapping.values())))}"
            )
        return backend

    async def connect(self) -> None:
        await self._backend.connect()

    async def disconnect(self) -> None:
        await self._backend.disconnect()

    async def execute(self, query: str, *args: Any) -> Any:
        return await self._backend.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        return await self._backend.fetch(query, *args)

    async def fetch_one(self, query: str, *args: Any) -> dict | None:
        return await self._backend.fetch_one(query, *args)

    async def insert(self, table: str, data: dict) -> Any:
        return await self._backend.insert(table, data)

    async def insert_many(self, table: str, data: list[dict]) -> Any:
        return await self._backend.insert_many(table, data)

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.disconnect()

    @staticmethod
    def available_backends() -> list[str]:
        _ensure_backends_registered()
        return _db_registry.keys()


_backends_registered = False


def _ensure_backends_registered():
    global _backends_registered
    if _backends_registered:
        return
    _backends_registered = True
    from aiops.db import postgres, mysql, mssql, mongo, redis_backend  # noqa: F401
