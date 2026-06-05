# CI/CD Workflows

## Architecture: hub-and-spoke

A central `ci.yml` orchestrator detects what changed and fans out to focused,
reusable workflow files. Each workflow owns exactly one concern. Scheduled jobs
run independently and never block PRs.

```
                    ┌─────────────┐
                    │   ci.yml    │  push/PR
                    │ (detect)    │
                    └──────┬──────┘
                           │ dorny/paths-filter
          ┌────────────────┼──────────────────────┐
          │                │                      │
          ▼                ▼                      ▼
    ┌──────────┐    ┌───────────┐          ┌────────────┐
    │ lint.yml │    │ nix.yml   │   ...    │ weekly-    │
    │ (ruff +  │    │ (flake    │          │ deps.yml   │
    │  mypy)   │    │  check +  │          │ (scheduled)│
    └──────────┘    │  build +  │          └────────────┘
                    │  devshell)│
                    └───────────┘
```

Every reusable workflow supports `workflow_call` (invoked by the orchestrator)
and `workflow_dispatch` (manual trigger via GitHub UI).

---

## Workflow reference

### `ci.yml` — Orchestrator

| Trigger | Push to `main`, pull_request |
|---|---|

**Detect phase** (`dorny/paths-filter@v3`): classifies changed paths into
buckets — `python`, `tests`, `nix`, `docs`, `any` — then fans out:

| Called workflow | Run condition |
|---|---|
| `lint` | Python or any file changed |
| `test-unit` | Python, tests, or any file changed |
| `test-integration` | Tests or any file changed |
| `nix` | Always (if detect succeeded) |
| `security` | Python or any file changed |
| `docs` | Docs or any file changed |

### `lint.yml` — Lint & type check

| Trigger | `workflow_call`, `workflow_dispatch` |
|---|---|

Runs inside `nix develop .#bootstrap` (fast — no uv2nix venv build):

1. `ruff format --check src/ tests/`
2. `ruff check src/ tests/`
3. `mypy src/`

### `test-unit.yml` — Unit tests

| Trigger | `workflow_call`, `workflow_dispatch` |
|---|---|

Runs inside `nix develop` (full hermetic uv2nix environment):

1. `pytest tests/unit --cov --cov-report=xml --cov-report=term`
2. Uploads coverage to Codecov

### `test-integration.yml` — Integration & E2E tests

| Trigger | `workflow_call`, `workflow_dispatch` |
|---|---|

Two jobs, both with `continue-on-error: true` (soft-fail):

- **test-integration**: `pytest tests/integration --cov`
- **test-e2e**: `pytest tests/e2e --cov`

Both upload coverage on every run (even on failure) via `if: always()`.

### `nix.yml` — Nix checks & dev shell smoke tests

| Trigger | `workflow_call`, `workflow_dispatch` |
|---|---|

Two jobs:

**nix-checks**:
1. `nix flake check` — validates flake evaluation, runs all `checks` derivations
2. `nix build .#default` — production build

**devshell-smoke**: validates that `nix develop` works correctly for
other developers:
1. `nix develop .#default --command true` — builds the full dev environment
2. `nix develop .#bootstrap --command true` — builds the bootstrap environment
3. Runs Python import checks (`typer`, `pydantic`, `textual`) and tool
   availability (`pytest`, `ruff`, `mypy`) inside each shell

### `security.yml` — Dependency vulnerability scan

| Trigger | `workflow_call`, `workflow_dispatch` |
|---|---|

1. `pip-audit` — scans `uv.lock` for known vulnerabilities
2. `bandit -r src/ -ll` — static analysis (medium+ severity)

### `docs.yml` — Documentation build

| Trigger | `workflow_call`, `workflow_dispatch` |
|---|---|

If `mkdocs.yml` exists, builds the site with `mkdocs build --strict`.
Skips gracefully with a warning if no mkdocs config is found
(this repo doesn't ship a `mkdocs.yml` — create one to enable).

### `weekly-deps.yml` — Scheduled dependency maintenance

| Trigger | `cron: "0 6 * * 1"` (Monday 06:00 UTC), `workflow_dispatch` |
|---|---|

Two jobs:

**flake-lock**: Uses `DeterminateSystems/update-flake-lock-action@v24`
to open a PR updating `flake.lock`.

**dep-audit**: Runs `pip-audit` and `nix flake lock --check`, posts
results to the workflow summary.

### `release.yml` — Tag-driven release

| Trigger | Push tag `v*` |
|---|---|

1. **detect** — checks if the CLI entrypoint exists
2. **build** — `nix build`, uploads artifact
3. **publish-pypi** — (gated on CLI) builds wheel, publishes via
   `uv publish` with trusted publishing (OIDC)
4. **github-release** — creates a GitHub release with the build artifact
   and auto-generated release notes

---

## Dev shell environments

| Shell | Environment | Used by |
|---|---|---|
| `.#default` | Full uv2nix venv (editable package + all deps) | `nix develop`, `test-unit`, `test-integration`, `devshell-smoke` |
| `.#bootstrap` | Python + uv only (no uv2nix venv) | `lint`, `security`, `docs`, `dep-audit` |

The `.#bootstrap` shell is faster because it doesn't build the uv2nix virtual
environment. Use it for non-test workflows. The `.#default` shell provides the
full hermetic environment needed for running tests against the actual package.

---

## Composite action: `setup-nix`

`.github/actions/setup-nix/action.yml` is the single reusable action shared
by all workflows:

1. `DeterminateSystems/nix-installer-action@v16` — installs Nix
2. `DeterminateSystems/magic-nix-cache-action@v8` — caching
3. `DeterminateSystems/flake-checker-action@v9` — flake evaluation check
4. `actions/cache@v4` — caches `~/.cache/uv`, `.ruff_cache`, `.mypy_cache`

No separate `setup-python` action is needed — the project uses uv2nix for
all Python tooling, so Nix is the single dependency.

---

## Skipping logic

The orchestrator skips workflows when no relevant files changed. The detection
is conservative — `any` matches every path, so on most PRs all workflows run:

| Filter | Matches |
|---|---|
| `python` | `pyproject.toml`, `uv.lock`, `src/**/*.py` |
| `tests` | `tests/**/*.py`, `tests/**/*.nix`, `fixtures/**` |
| `nix` | `flake.nix`, `flake.lock`, `nix/**/*.nix` |
| `docs` | `docs/**/*.md`, `mkdocs.yml` |
| `any` | `**/*` (safety net — always true when anything changes) |

The `nix` job always runs (no path filter) because Nix evaluation covers the
entire project.
