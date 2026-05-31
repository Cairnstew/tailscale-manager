# Contributing

## Development setup

```bash
nix develop          # full hermetic environment (uv2nix venv)
nix develop .#bootstrap  # fast env for lint/typecheck only
```

## Workflow

```bash
# Add a dependency
nix develop .#bootstrap
uv add <package>

# Lint
ruff check src/

# Type check
mypy src/tailscale_manager/

# Test
pytest tests/unit/ -v

# Build
nix build .#default

# Full check
nix flake check
```

## Layer conventions

Follow the import direction rules in `AGENTS.md`:
- `core/` — no imports from the rest of the package
- `models/` — pure data shapes only
- `services/` — imports `models/` and `repositories/`
- `repositories/` — data access only
- `utils/` — stateless pure functions only

## Pull requests

- One logical change per PR
- All checks must pass: `ruff`, `mypy`, `pytest`, `nix build`
- Update `CHANGELOG.md` under `[Unreleased]`
- Update `STRUCTURE.md` if files are added or removed
