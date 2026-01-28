CREATE TRIGGER IF NOT EXISTS trg_workflows_updated
AFTER UPDATE ON workflows
FOR EACH ROW
BEGIN
    UPDATE workflows
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;

-- Trigger to update 'updated_at' timestamp on tasks table updates --

CREATE TRIGGER IF NOT EXISTS trg_tasks_updated
AFTER UPDATE ON tasks
FOR EACH ROW
BEGIN
    UPDATE tasks
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;
