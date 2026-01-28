-- Workflow instances (metadata + cached status)

CREATE TABLE IF NOT EXISTS workflows (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT,
    version      TEXT NOT NULL,
    module       TEXT NOT NULL,
    status       TEXT NOT NULL CHECK (
        status IN ('RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')
    ),
    input        JSON NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
