# Loom Tests

This directory contains the test suite for Loom workflow orchestration.

## Test Structure

- **conftest.py**: Test fixtures and configuration
- **test_workflow.py**: Tests for workflow definition and compilation
- **test_activity.py**: Tests for activity decorator and validation
- **test_context.py**: Tests for workflow context and state management
- **test_database.py**: Tests for database operations
- **test_integration.py**: End-to-end integration tests

## Running Tests

Install test dependencies:
```bash
pip install pytest pytest-asyncio
```

Run all tests:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=src --cov-report=html
```

Run specific test file:
```bash
pytest tests/test_workflow.py
```

Run with verbose output:
```bash
pytest -v
```

## Test Categories

### Unit Tests
- Workflow decorator and compilation
- Activity decorator and validation
- Context and state proxy
- Database operations

### Integration Tests
- Full workflow execution
- Event sourcing and replay
- Task queue processing
- Error handling and recovery

## Writing New Tests

Follow these conventions:

1. Use descriptive test names: `test_<what>_<scenario>`
2. Use pytest fixtures from conftest.py
3. Mark async tests with `@pytest.mark.asyncio`
4. Test both success and failure paths
5. Mock external dependencies when appropriate
