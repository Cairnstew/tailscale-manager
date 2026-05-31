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
│   │   │   ├── acl_backup.py        #   ACL policy backup/restore utilities
│   │   │   ├── config.py            #   AppConfig (Pydantic) with env var parsing
│   │   │   ├── constants.py         #   Well-known paths and filenames
│   │   │   └── exceptions.py        #   Domain exceptions
│   │   ├── models/
│   │   │   ├── acl.py               #   AclConfig model
│   │   │   ├── auth_key.py          #   TailscaleAuthKey dataclass
│   │   │   ├── device.py            #   TailscaleDevice dataclass
│   │   │   └── settings.py          #   TailnetSettings model
│   │   ├── services/
│   │   │   ├── features/            #   Feature config builders (per resource type)
│   │   │   │   ├── __init__.py      #     Re-exports all builders
│   │   │   │   ├── acl.py           #     tailscale_acl builder
│   │   │   │   ├── devices.py       #     data.tailscale_devices builder
│   │   │   │   ├── dns.py           #     tailscale_dns_* builders
│   │   │   │   └── settings.py      #     tailscale_tailnet_settings builder
│   │   │   └── terraform_service.py #   Orchestrator: calls feature builders,
│   │   │                            #   writes multi-file .tf.json, runs terraform
│   │   ├── repositories/
│   │   │   └── state_repository.py  #   Read/write tfstate, last-apply.json, devices
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
│   │   ├── test_acl_backup.py
│   │   ├── test_acl_feature.py
│   │   ├── test_acl_model.py
│   │   ├── test_cli.py
│   │   ├── test_cli_devices.py
│   │   ├── test_device_model.py
│   │   ├── test_devices_feature.py
│   │   ├── test_dns_feature.py
│   │   ├── test_settings_feature.py
│   │   ├── test_settings_model.py
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
├── docs/                     # Tailscale reference documentation
│   ├── POLICY.md             #   Policy file index — entry point into docs/policy/
│   ├── OAUTH.md              #   OAuth clients & trust credentials
│   ├── API.md                #   Tailscale API endpoints & scopes
│   ├── CONCEPTS.md           #   Terminology and concepts
│   └── policy/               #   Policy file deep reference (16 files)
│       ├── README.md         #     Overview, format, JSON skeleton
│       ├── grants.md         #     Grants syntax
│       ├── acls.md           #     ACL rules
│       ├── ssh.md            #     Tailscale SSH
│       ├── tag-owners.md     #     Tag ownership
│       ├── groups.md         #     Named user groups
│       ├── hosts.md          #     Named IP/CIDR aliases
│       ├── ipsets.md         #     Named IP collections
│       ├── postures.md       #     Device posture conditions
│       ├── node-attrs.md     #     Per-device attributes
│       ├── auto-approvers.md #     Route/exit node auto-approval
│       ├── tests.md          #     Assertion tests
│       ├── network-options.md#     DERP, IPv4, CGNAT, client port
│       ├── autogroups.md     #     Autogroup reference
│       ├── selectors.md      #     Selector types reference
│       └── users.md          #     User identity formats
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
