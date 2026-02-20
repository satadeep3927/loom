-- Workflow instances (metadata + cached status)

CREATE TABLE IF NOT EXISTS workflows (
    id           VARCHAR PRIMARY KEY,
    name         VARCHAR NOT NULL,
    description  VARCHAR,
    version      VARCHAR NOT NULL,
    module       VARCHAR NOT NULL,
    status       VARCHAR NOT NULL CHECK (
        status IN ('RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED')
    ),
    input        JSON NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
