-- Durable execution queue (steps, activities, timers)

CREATE TABLE IF NOT EXISTS tasks (
    id            TEXT PRIMARY KEY,
    workflow_id   TEXT NOT NULL,
    kind          TEXT NOT NULL CHECK (
        kind IN ('STEP', 'ACTIVITY', 'TIMER')
    ),
    target        TEXT NOT NULL,
    run_at        TIMESTAMP NOT NULL,
    status        TEXT NOT NULL CHECK (
        status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')
    ),
    attempts      INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    last_error    TEXT,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (workflow_id)
        REFERENCES workflows(id)
        ON DELETE CASCADE
);
