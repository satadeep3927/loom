-- Workflow logs

CREATE SEQUENCE IF NOT EXISTS logs_id_seq START 1;

CREATE TABLE IF NOT EXISTS logs (
    id           BIGINT PRIMARY KEY DEFAULT nextval('logs_id_seq'),
    workflow_id  VARCHAR NOT NULL,
    level        VARCHAR NOT NULL,
    message      VARCHAR NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
);
