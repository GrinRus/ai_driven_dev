# SKILL: testing-pytest

## Name
Pytest testing

## Version
1.0

## When to use
- Project uses Python and pytest (pyproject.toml/requirements.txt).

## Commands
### Install
- python -m pip install -r requirements.txt
- python -m pip install -e .

### Test (fast/targeted/full)
- pytest
- pytest tests/path/test_file.py
- pytest -k "pattern"

### Lint/Format
- python -m ruff check .
- python -m ruff format .

## Evidence
- Save logs under: `aidd/reports/tests/<ticket>.<ts>.pytest.log`.
- In the response, include the log path and a 1-line summary.

## Pitfalls
- Ensure the correct virtualenv is active.
- Targeted pytest runs should not skip critical fixtures.

## Tooling
- Use AIDD hooks for format/test cadence when enabled.
