"""MongoDB async backend using motor."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from aiops.core.log import get_logger
from aiops.db.base import DatabaseBase, _db_registry

logger = get_logger(__name__)


class MongoBackend(DatabaseBase):
    """Async MongoDB backend using motor.

    Usage differs slightly from SQL backends since MongoDB is document-based.
    The `table` parameter maps to collection name.
    The `query` parameter for fetch/execute accepts MongoDB filter dicts (as JSON strings or dicts).
    """

    def __init__(self, url: str, database: str | None = None, **kwargs: Any) -> None:
        super().__init__(url, **kwargs)
        self._client = None
        self._db = None
        # Extract database name from URL path or explicit parameter
        parsed = urlparse(url)
        self._db_name = database or parsed.path.lstrip("/") or "default"

    async def connect(self) -> None:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except ImportError:
            raise ImportError("motor not installed. Install with: pip install 'aiops[mongo]'")
        self._client = AsyncIOMotorClient(self.url, **self._kwargs)
        self._db = self._client[self._db_name]
        logger.info(f"MongoDB connected: database={self._db_name}")

    async def disconnect(self) -> None:
        if self._client:
            self._client.close()
            logger.info("MongoDB disconnected")

    async def execute(self, query: str, *args: Any) -> Any:
        """Execute a raw command on the database."""
        import json

        cmd = json.loads(query) if isinstance(query, str) else query
        return await self._db.command(cmd)

    async def fetch(self, query: str, *args: Any) -> list[dict]:
        """Fetch documents. query format: 'collection_name' or 'collection_name:{"filter": ...}'"""
        collection_name, filter_dict = self._parse_query(query)
        collection = self._db[collection_name]
        cursor = collection.find(filter_dict)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    async def fetch_one(self, query: str, *args: Any) -> dict | None:
        collection_name, filter_dict = self._parse_query(query)
        collection = self._db[collection_name]
        doc = await collection.find_one(filter_dict)
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def insert(self, table: str, data: dict) -> Any:
        """Insert a document into a collection."""
        collection = self._db[table]
        result = await collection.insert_one(data)
        return str(result.inserted_id)

    async def insert_many(self, table: str, data: list[dict]) -> Any:
        if not data:
            return []
        collection = self._db[table]
        result = await collection.insert_many(data)
        return [str(id_) for id_ in result.inserted_ids]

    @staticmethod
    def _parse_query(query: str) -> tuple[str, dict]:
        import json

        if ":" in query:
            collection, filter_str = query.split(":", 1)
            return collection.strip(), json.loads(filter_str)
        return query.strip(), {}


_db_registry.register("mongodb", MongoBackend)
