# Tests

This directory contains test cases for the SeerBot Service API.

## Structure

```
tests/
├── __init__.py
├── conftest.py          # Pytest fixtures and configuration
├── api/
│   ├── __init__.py
│   └── v1/
│       ├── __init__.py
│       └── test_analysis.py  # Tests for analysis endpoints
└── README.md
```

## Installation

Install test dependencies:

```bash
pip install -r requirements-test.txt
```

Or install all dependencies including test dependencies:

```bash
pip install -r requirements-core.txt -r requirements-test.txt
```

## Running Tests

Run all tests:

```bash
pytest
```

Run tests with verbose output:

```bash
pytest -v
```

Run a specific test file:

```bash
pytest tests/api/v1/test_analysis.py
```

Run a specific test class:

```bash
pytest tests/api/v1/test_analysis.py::TestIndicatorsAPI
```

Run a specific test method:

```bash
pytest tests/api/v1/test_analysis.py::TestIndicatorsAPI::test_get_indicators_success
```

Run tests with coverage:

```bash
pytest --cov=app --cov-report=html
```

## Test Structure

### Unit Tests (`TestIndicatorsAPI`)

Tests the `get_indicators` function directly with mocked dependencies:
- Success cases
- Error handling (invalid timeframe, no data found)
- Parameter validation (limit, time range, indicators)
- All valid timeframes
- Pair format conversion
- Chronological ordering

### Integration Tests (`TestIndicatorsAPIIntegration`)

Tests the HTTP endpoint using FastAPI's TestClient:
- Successful HTTP requests
- Invalid parameters
- Missing required parameters
- All optional parameters
- Error responses

## Fixtures

- `client`: FastAPI TestClient instance
- `mock_db`: Mock database session
- `mock_db_result`: Mock database result rows
- `mock_result_rows`: Mock result rows for indicators data

## Notes

- Tests use mocked database connections to avoid requiring a real database
- The `conftest.py` file provides shared fixtures for all tests
- All tests follow the pytest naming convention (test_*.py files, test_* functions)

