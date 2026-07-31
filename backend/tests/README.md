# Backend Test Layout

Run all locally discoverable tests from `backend/` with:

```bash
python -m unittest discover -s tests
```

Use the directories to target narrower suites:

- `unit/`: isolated logic with mocked external dependencies.
- `integration/`: component or infrastructure boundary behavior.
- `e2e/`: complete workflow scenarios used by the Compose E2E script.
- `benchmarks/`: orchestrator benchmark runner and metrics tests.
- `fixtures/`: reusable input and expected-result data.
