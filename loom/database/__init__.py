from ..common.config import get_database_backend
from .base import DatabaseBackend
from .db import Database as SQLiteDatabase
from .duckdb_backend import DuckDBDatabase

# Conditionally export the correct Database implementation based on config
_backend = get_database_backend()

if _backend == "duckdb":
    Database = DuckDBDatabase
else:
    Database = SQLiteDatabase

__all__ = [
    "DatabaseBackend",
    "Database",
    "SQLiteDatabase",
    "DuckDBDatabase",
]