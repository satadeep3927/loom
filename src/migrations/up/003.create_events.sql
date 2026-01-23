-- Append-only event log (SOURCE OF TRUTH)

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id  TEXT NOT NULL,
    type         TEXT NOT NULL,
    payload      JSON,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (workflow_id)
        REFERENCES workflows(id)
        ON DELETE CASCADE
);
