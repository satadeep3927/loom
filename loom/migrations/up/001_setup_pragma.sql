-- Enable WAL for concurrent readers/writers
PRAGMA journal_mode = WAL;

-- Good durability/performance tradeoff for workflows
PRAGMA synchronous = NORMAL;

-- Wait for write locks instead of failing
PRAGMA busy_timeout = 5000;

-- Enforce foreign keys (off by default in SQLite)
PRAGMA foreign_keys = ON;
