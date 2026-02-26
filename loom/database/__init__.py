from ..common.config import get_database_backend
from .base import DatabaseBackend
from .db import Database as SQLiteDatabase

# Conditionally import and export the correct Database implementation
_backend = get_database_backend()

if _backend == "duckdb":
    from .duckdb_backend import DuckDBDatabase

    Database = DuckDBDatabase
else:
    Database = SQLiteDatabase
    DuckDBDatabase = None  # type: ignore

__all__ = [
    "DatabaseBackend",
    "Database",
    "SQLiteDatabase",
    "DuckDBDatabase",
]
