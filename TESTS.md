# Tests

Three-tier test suite with scoped fixtures, pure factories, and reusable helpers.

## Layout

```
tests/
├── conftest.py            # Root: sys.path, env vars, logging, session-scoped setup
│
├── unit/                  # Fast — no I/O, no services
│   ├── conftest.py        #   Mocks & fakes scoped here
│   └── test_example.py
│
├── integration/           # Needs real services (DB, network, filesystem)
│   ├── conftest.py        #   Service fixtures (test containers, tmp dirs, etc.)
│   └── test_example.py
│
├── e2e/                   # Full application lifecycle (CLI runner, browser, etc.)
│   ├── conftest.py        #   App spin-up, teardown
│   └── test_example.py
│
├── fixtures/              # Pure data & factories — no test logic, no imports from tests
│   ├── __init__.py
│   ├── factories.py       #   factory-boy / polyfactory model factories
│   ├── mocks.py           #   Reusable mock objects / fake implementations
│   └── data/              #   Static test data files (JSON, CSV, etc.)
│       ├── sample.json
│       └── sample.csv
│
└── utils/                 # Reusable logic that isn't fixtures
    ├── __init__.py
    ├── assertions.py      #   e.g. assert_response_matches_schema(response, schema)
    └── builders.py         #   e.g. UserBuilder().with_role("admin").build()
```

## Running subsets

```bash
pytest tests/unit/           # fast, no I/O
pytest tests/integration/    # needs services
pytest tests/e2e/            # full app
pytest tests/                # everything
```

## Design decisions

**Scoped conftest.py per tier.** Each tier (`unit/`, `integration/`, `e2e/`) has its own `conftest.py` so fixtures are scoped by tier. A heavy DB fixture in `integration/conftest.py` never bleeds into unit tests. This keeps `unit/` tests fast and avoids accidental coupling.

**`fixtures/` is pure data and factories — no test logic.** This is what you import from `conftest.py` files, keeping conftests lean. Nothing in `fixtures/` imports from `pytest` or from other test files. It's just Python objects, callables, and static files.

**`utils/` holds reusable logic that isn't fixtures.** Things like `assert_response_matches_schema()` or `UserBuilder().with_role("admin").build()`. These are plain functions and classes — no pytest dependency, no fixture request objects. Import them directly in tests or wire them through conftest.

**Nothing project-specific lives at the top level of `tests/`.** You'd only ever add files within the three tiers. The root `conftest.py` handles `sys.path` and any truly global session-scoped setup (env vars, logging config) that applies everywhere.

**`unit/` vs `integration/` vs `e2e/` is a trade-off, not a religion.** If a test touches the filesystem, it's probably integration. If it calls a subprocess, it's e2e. If it runs in complete isolation with only in-memory mocks, it's unit. When in doubt, put it one tier higher than you think — slower test suites are easier to speed up than flaky test classifications are to untangle.

## Naming

- Files: `test_<name>.py` — pytest discovers by prefix
- Functions: `test_<description>` inside test files
- Fixture functions in conftest: `def <thing>()` — descriptive, no prefix needed
- Factory functions in `fixtures/factories.py`: `<ModelName>Factory` — consistent with factory-boy convention
- Builder classes in `utils/builders.py`: `<Thing>Builder` — fluent interface
- Custom assertion functions in `utils/assertions.py`: `assert_<what>()` — so failure messages are readable

## Testing by package layer

| Package layer | Test tier | Approach |
|---|---|---|
| `core/` | `unit/` | Pure functions — test directly. Config/logging may need env patching or capsys. |
| `models/` | `unit/` | Instantiate dataclasses/exceptions and assert shape. No mocking needed. |
| `services/` | `unit/` or `integration/` | If using abstract repos, test with mocks from `fixtures/mocks.py` in `unit/`. For real orchestration, test with in-memory repo implementations in `integration/`. |
| `repositories/` | `integration/` | Need a real backend (test DB, temp filesystem, etc.). Classified integration by definition. |
| `utils/` | `unit/` | Stateless pure functions — trivial to test. |
| `cli/` | `e2e/` | Use `CliRunner` (typer/click) or subprocess. Invoke `main()`, assert stdout/stderr/exit code. |
