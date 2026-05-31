# Project Structure

```
.
├── .github/                    # CI/CD & dependency management
│   ├── actions/
│   │   └── setup-nix/
│   │       └── action.yml      #   Reusable: Nix installer + cache + uv
│   ├── workflows/
│   │   ├── ci.yml              #   Push/PR — lint, typecheck, test, build
│   │   ├── release.yml         #   Tag v* — Nix build, PyPI publish, GH release
│   │   └── update-flake-lock.yml # Weekly — nix flake lock update PR
│   └── renovate.json           #   Renovate config — batches Python & Nix dep PRs
│
├── flake.nix                 # Nix flake — thin orchestrator, delegates to nix/
├── flake.lock                # Nix lock file — pins all flake input versions
├── pyproject.toml            # Python project metadata & dependency declarations
├── uv.lock                   # uv lock file — exact dependency resolution, drives uv2nix overlay
│
├── nix/                      # Modular Nix building blocks
│   ├── default.nix           #   Derivation — wraps app via mkApplication
│   ├── overlay.nix           #   pkgs overlay — adds tailscale-manager & env
│   ├── module.nix            #   NixOS module — optional systemd service
│   ├── home-module.nix       #   Home Manager module — user env package
│   ├── devshell.nix          #   Dev shells — default (uv2nix) + bootstrap (raw)
│   └── checks.nix            #   Flake checks — build & venv smoke tests
│
├── src/
│   ├── tailscale_manager/       # Application package (see layer rules in AGENTS.md)
│   │   ├── __init__.py
│   │   ├── py.typed
│   │   ├── core/
│   │   ├── models/
│   │   │   └── auth_key.py          #   TailscaleAuthKey dataclass
│   │   ├── services/
│   │   │   └── terraform_service.py #   Backup, generate HCL, init/plan/apply/destroy
│   │   ├── repositories/
│   │   │   └── state_repository.py  #   Read/write tfstate and last-apply.json
│   │   ├── utils/
│   │   │   └── subprocess_helpers.py #  Terraform subprocess runner
│   │   └── cli.py                   #   Typer entrypoint (all subcommands)
│   │
│   └── textual_ui/              # TUI package — optional (textual extra)
│       ├── __init__.py           #   Exports read-only status dashboard
│       └── app.py                #   TailscaleManagerApp (Textual app)
│
├── tests/                     # Tiered test suite
│   ├── conftest.py            # Root: sys.path, session-scoped setup
│   ├── unit/                  # Fast, no I/O — mocks & fakes only
│   │   ├── conftest.py
│   │   ├── test_cli.py
│   │   ├── test_state_repository.py
│   │   └── test_terraform_service.py
│   ├── integration/           # Needs services (DB, network)
│   │   └── conftest.py
│   ├── e2e/                   # Full app spin-up, CLI runner
│   │   └── conftest.py
│   ├── fixtures/              # Pure data & factories (no test logic)
│   │   ├── __init__.py
│   │   ├── factories.py
│   │   ├── mocks.py
│   │   └── data/
│   │       ├── sample.json
│   │       └── sample.csv
│   └── utils/                 # Reusable helpers (assertions, builders)
│       ├── __init__.py
│       ├── assertions.py
│       └── builders.py
│
├── UV2NIX.md                 # uv2nix reference & lookup table
├── AGENTS.md                 # Instructions for AI coding agents
├── GOTCHAS.md                # Common pitfalls
├── HEATMAP.md                # Complexity/fragility heatmap
├── STRUCTURE.md              # This file
├── README.md                 # Project readme
│
├── .gitignore                # Git ignore rules
```

## Architecture

```
pyproject.toml  ──uv add/lock──►  uv.lock
                                      │
                                      ▼
flatten.nix  ──workspace.mkPyprojectOverlay──►  Nix overlay
  │                                                  │
  │  pyproject-build-systems.overlays.wheel ─────────┤
  │                                                  │
  └── composeManyExtensions ─────────────────────────► pythonSet
                                                           │
                                               ┌───────────┼───────────────────┐
                                               ▼           ▼                   ▼
                                    nix/default.nix   nix/devshell.nix    nix/module.nix
                                    (mkApplication)   (mkShell)           (systemd service)
```

The flake.nix is a thin orchestrator. Each `nix/` file receives the system-specific `pythonSet`, `pkgs`, `workspace`, etc. and handles one concern.

## Key concepts

- **workspace** — uv2nix treats every project as a workspace (even single-project ones). `loadWorkspace` discovers & parses all members.
- **overlay** — generated from `uv.lock` via `mkPyprojectOverlay`. Adds every dependency as a Nix package attribute.
- **editableOverlay** — variant for development: installs your local package as editable (source-linked) so changes take effect immediately.
- **pythonSet** — Nixpkgs Python package set extended with the uv2nix overlays. Contains every Python package as a buildable derivation.
- **virtualenv** — aggregate derivation that combines all selected packages into a single environment (via `mkVirtualEnv`).
- **mkApplication** — wraps a venv into a standalone Nix package, hiding Python internals (interpreter, activation scripts, etc.).

## Nix Flake outputs

| Output | Source file | Description |
|---|---|---|
| `packages.default` | `nix/default.nix` | Production build via `mkApplication` |
| `devShells.default` | `nix/devshell.nix` | Full dev environment with editable installs |
| `devShells.bootstrap` | `nix/devshell.nix` | Python + uv only (no uv2nix dependency) |
| `overlays.default` | `flake.nix` (inline) | Adds `tailscale-manager` to `pkgs` |
| `nixosModules.default` | `nix/module.nix` | Optional systemd service |
| `homeManagerModules.default` | `nix/home-module.nix` | User environment package |
| `checks` | `nix/checks.nix` | Build & venv smoke tests |
