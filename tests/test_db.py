"""Tests for database module (unit tests, no live DB required)."""

import pytest

from aiops.db.base import Database


class TestDatabaseDetection:
    def test_detects_postgresql(self):
        db = Database.__new__(Database)
        assert db._detect_backend("postgresql://user:pass@localhost/db") == "postgresql"

    def test_detects_postgres_alias(self):
        db = Database.__new__(Database)
        assert db._detect_backend("postgres://user:pass@localhost/db") == "postgresql"

    def test_detects_mysql(self):
        db = Database.__new__(Database)
        assert db._detect_backend("mysql://user:pass@localhost/db") == "mysql"

    def test_detects_mongodb(self):
        db = Database.__new__(Database)
        assert db._detect_backend("mongodb://localhost:27017/db") == "mongodb"

    def test_detects_redis(self):
        db = Database.__new__(Database)
        assert db._detect_backend("redis://localhost:6379/0") == "redis"

    def test_detects_mssql(self):
        db = Database.__new__(Database)
        assert db._detect_backend("mssql://sa:pass@localhost/db") == "mssql"

    def test_unknown_scheme_raises(self):
        db = Database.__new__(Database)
        with pytest.raises(ValueError, match="Unknown database scheme"):
            db._detect_backend("sqlite:///test.db")


class TestAvailableBackends:
    def test_all_registered(self):
        backends = Database.available_backends()
        assert "postgresql" in backends
        assert "mysql" in backends
        assert "mssql" in backends
        assert "mongodb" in backends
        assert "redis" in backends
