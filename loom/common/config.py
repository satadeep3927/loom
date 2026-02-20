import os
import tomllib
from pathlib import Path
from typing import Literal

MIGRATION_UPGRADES = os.path.join(os.path.dirname(__file__), "../", "migrations", "up")

MIGRATION_DOWNGRADES = os.path.join(
    os.path.dirname(__file__), "../", "migrations", "down"
)

DUCKDB_MIGRATION_UPGRADES = os.path.join(
    os.path.dirname(__file__), "../", "migrations", "duckdb_up"
)

DUCKDB_MIGRATION_DOWNGRADES = os.path.join(
    os.path.dirname(__file__), "../", "migrations", "duckdb_down"
)

DATA_ROOT = ".loom"
DATABASE = os.path.join(DATA_ROOT, "LOG")

DatabaseBackend = Literal["sqlite", "duckdb"]


def _load_config() -> dict:
    """Load configuration from loom.toml if it exists."""
    config_path = Path.cwd() / "loom.toml"
    if config_path.exists():
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    return {}


def get_database_backend() -> DatabaseBackend:
    """Get the configured database backend (default: sqlite)."""
    config = _load_config()
    backend = config.get("database", {}).get("backend", "sqlite")
    
    if backend not in ("sqlite", "duckdb"):
        raise ValueError(f"Invalid database backend: {backend}. Must be 'sqlite' or 'duckdb'")
    
    return backend  # type: ignore


def get_database_path() -> str:
    """Get the database file path based on the configured backend."""
    backend = get_database_backend()
    
    if backend == "sqlite":
        return DATABASE
    elif backend == "duckdb":
        return os.path.join(DATA_ROOT, "loom.duckdb")
    
    return DATABASE
