# DuckDB Backend Setup

Loom supports DuckDB as an alternative database backend for better concurrency.

## Configuration

Create a `loom.toml` file in your project root:

```toml
[database]
backend = "duckdb"
```

## Installation

DuckDB support is included in the standard requirements:

```bash
pip install -r requirements.txt
```

## Performance Comparison

### SQLite (Default)
- **Concurrency**: ~50 concurrent workflows
- **Use Case**: Development, small-scale deployments
- **Database File**: `.loom/LOG`

### DuckDB
- **Concurrency**: 200-300+ concurrent workflows (3-5x better)
- **Use Case**: Production, high-concurrency workloads
- **Database File**: `.loom/loom.duckdb`

## Switching Backends

1. **From SQLite to DuckDB**:
   ```bash
   # Stop all workers
   loom clean  # Optional: clear existing data
   
   # Update loom.toml
   echo '[database]\nbackend = "duckdb"' > loom.toml
   
   # Start with DuckDB
   loom run
   ```

2. **From DuckDB to SQLite**:
   ```bash
   # Stop all workers
   loom clean  # Optional: clear existing data
   
   # Update loom.toml
   echo '[database]\nbackend = "sqlite"' > loom.toml
   
   # Start with SQLite
   loom run
   ```

## Notes

- The backend is loaded at import time from `loom.toml`
- Different backends use different database files (no automatic migration)
- Both backends share the same SQL schema and API
- All existing code works without modification

## Migration Between Backends

There's currently no automatic migration tool. If you need to migrate data:

1. Export workflows using the API:
   ```python
   from loom.database import SQLiteDatabase
   
   async with SQLiteDatabase() as db:
       workflows = await db.query("SELECT * FROM workflows")
       # ... export logic
   ```

2. Import into the new backend similarly

## Example loom.toml

See `loom.toml.example` for a complete configuration template.
