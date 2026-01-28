-- Revert to SQLite defaults (no explicit PRAGMA resets needed)
-- SQLite will use defaults when connection is closed/reopened

-- Note: These settings are connection-specific and will revert to defaults
-- when the database connection is closed. No explicit downgrade needed.