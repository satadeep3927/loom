-- Fast event replay
CREATE INDEX IF NOT EXISTS idx_events_workflow_id
    ON events(workflow_id);

-- Worker polling (critical)
CREATE INDEX IF NOT EXISTS idx_tasks_pending
    ON tasks(status, run_at);

-- Workflow listing / inspection
CREATE INDEX IF NOT EXISTS idx_workflows_status
    ON workflows(status);
