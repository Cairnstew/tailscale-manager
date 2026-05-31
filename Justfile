# List available commands
default:
    @just --list

# Enter dev shell
dev:
    nix develop

# Lint
lint:
    nix develop .#bootstrap --command ruff check src/

# Type check
typecheck:
    nix develop .#bootstrap --command mypy src/tailscale_manager/

# Run unit tests
test:
    nix develop --command pytest tests/unit/ -v

# Run all checks
check: lint typecheck test
    nix flake check

# Build
build:
    nix build .#default

# Format
fmt:
    nix develop .#bootstrap --command ruff format src/
