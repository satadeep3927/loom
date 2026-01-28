CREATE TABLE IF NOT EXISTS logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_id  TEXT NOT NULL,
    level        TEXT NOT NULL,
    message      TEXT NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workflow_id)
        REFERENCES workflows(id)
        ON DELETE CASCADE
);