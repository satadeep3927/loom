-- Append-only event log (SOURCE OF TRUTH)
-- DuckDB uses BIGINT with auto-sequence for PRIMARY KEY

CREATE SEQUENCE IF NOT EXISTS events_id_seq START 1;

CREATE TABLE IF NOT EXISTS events (
    id           BIGINT PRIMARY KEY DEFAULT nextval('events_id_seq'),
    workflow_id  VARCHAR NOT NULL,
    type         VARCHAR NOT NULL,
    payload      JSON,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);
