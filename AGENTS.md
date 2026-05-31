# Agent Instructions

## About this project

Python project managed with `uv2nix` — uv's `uv.lock` drives Nix derivations via pure Nix code.

## Examples

Live-tested example configurations live in `examples/`. Each example has a
`policy.nix` (NixOS config) and `policy.json` (serialized output) side by
side for comparison.

| Directory | What it demonstrates |
|---|---|
| [`examples/basic/`](./examples/basic/) | All policy sections: grants, SSH, tag owners, hosts, IP sets, postures, node attrs, auto-approvers, app connectors |

## Reference files

| File | Role |
|---|---|
| `UV2NIX.md` | Full uv2nix reference & lookup table |
| `GOTCHAS.md` | Common pitfalls — read before debugging build issues |
| `HEATMAP.md` | Complexity/fragility heatmap of every project file |
| `STRUCTURE.md` | Project structure, architecture diagram, devShells & packages |
| `TESTS.md` | Test tier layout, design decisions, and conventions |
| `AGENTS.md` | This file — agent instructions |
| `docs/POLICY.md` | Tailnet policy file index — points into `docs/policy/` |
| `docs/policy/README.md` | Policy file overview, format, and complete JSON skeleton |
| `docs/policy/grants.md` | Grants syntax (preferred access control) |
| `docs/policy/acls.md` | ACL rule syntax |
| `docs/policy/ssh.md` | Tailscale SSH rules |
| `docs/policy/tag-owners.md` | Tag ownership declarations |
| `docs/policy/groups.md` | Named user groups |
| `docs/policy/hosts.md` | Named IP/CIDR aliases |
| `docs/policy/ipsets.md` | Named IP collection sets |
| `docs/policy/postures.md` | Device posture conditions |
| `docs/policy/node-attrs.md` | Per-device attributes (funnel, NextDNS, etc.) |
| `docs/policy/auto-approvers.md` | Route/exit node auto-approval |
| `docs/policy/tests.md` | ACL/grant/SSH assertion tests |
| `docs/policy/network-options.md` | DERP, IPv4, CGNAT, client port options |
| `docs/policy/autogroups.md` | Complete autogroup reference with plan availability |
| `docs/policy/selectors.md` | All source/destination selector types |
| `docs/policy/users.md` | User identity formats |
| `docs/OAUTH.md` | OAuth clients & trust credentials reference |
| `docs/API.md` | Tailscale API endpoint and scope reference |
| `docs/CONCEPTS.md` | Tailscale terminology and concepts reference |

## Key files

| File | Role |
|---|---|
| `flake.nix` | Nix flake — thin orchestrator, delegates to `nix/` modules |
| `nix/default.nix` | Package derivation (mkApplication) |
| `nix/devshell.nix` | Dev shell definitions (default + bootstrap) |
| `nix/overlay.nix` | pkgs overlay reference |
| `nix/module.nix` | NixOS module (systemd service) |
| `nix/home-module.nix` | Home Manager module (user env) |
| `nix/checks.nix` | Flake checks |
| `pyproject.toml` | Python project metadata, dependencies |
| `uv.lock` | Lock file — drives the Nix overlay. **Must be regenerated after any pyproject.toml change.** |
| `examples/` | Live-tested example configs with Nix + JSON side by side |
| `src/tailscale_manager/` | Application package source |
| `src/textual_ui/` | TUI package (Textual) — optional, add as dependency when needed |
| `tests/` | Test suite |
| `.github/workflows/ci.yml` | CI — lint, typecheck, test, build on push/PR |
| `.github/workflows/release.yml` | Release — Nix build + PyPI publish on tag |
| `.github/workflows/update-flake-lock.yml` | Weekly flake.lock update (Monday) |
| `.github/renovate.json` | Renovate config — batches Python & Nix dep PRs |

## Workflows

### Add a dependency
```
nix develop .#bootstrap   # or nix develop (if uv.lock is current)
uv add <package>
# uv.lock updated, flake.nix picks it up automatically
```

### Enter dev environment
```
nix develop
```
This builds a Nix-managed venv with all deps. Never use `uv run` inside it — `uv2nix` provisions the venv, not `uv`.

### Build for production
```
nix build .#default
```

### CI workflows

The `.github/workflows/` directory has three workflows that run out of the box:

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | Push to main, PR | Detect project capabilities → lint (ruff) → typecheck (mypy) → test (pytest matrix by tier) → Nix checks (`nix flake check` + `nix build`). Test tiers are auto-detected from existing directories. `unit` is required; `integration` and `e2e` are soft-fail. |
| `release.yml` | Tag push `v*` | Build via Nix → publish to PyPI (if CLI detected) → create GitHub release. PyPI publishing is gated behind `has_cli`. |
| `update-flake-lock.yml` | Weekly (Monday) | Runs `nix flake lock --update`, opens a PR. |

Lint and typecheck run inside `nix develop .#bootstrap` (fast, no uv2nix venv build). Tests run inside `nix develop` (full hermetic environment). See `TESTS.md` for test tier conventions.

## Rules for agents

1. **Never edit `uv.lock` directly** — always use `uv lock` or `uv add`/`uv remove`.
2. **After editing `pyproject.toml`**, tell the user to run `uv lock` to regenerate `uv.lock`.
3. **After editing `flake.nix`**, run `nix flake lock` to update `flake.lock`.
4. **Source filtering**: avoid filtering at the workspace root level (causes IFD + breaks editables). Filter per-package via overlay in `flake.nix`.
5. **Python version**: controlled by `requires-python` in `pyproject.toml` and the `python` variable in `flake.nix`. Keep in sync.
6. **Setuptools backend**: `pyproject.toml` uses `setuptools.build_meta`. If switching backends (hatchling, pdm, etc.), update `build-system.requires` accordingly and ensure the build system is covered by `pyproject-build-systems` inputs.
7. **Adding Nix-specific overrides** — place them in `flake.nix` as an additional extension in `composeManyExtensions`. See `UV2NIX.md` > Overriding Packages for patterns.
8. **Package layer conventions** — follow the import direction rules in `src/tailscale_manager/`:
   - `core/` imports nothing from the rest of the package
   - `models/` is pure data shapes
   - `services/` imports `models/` and `repositories/`
   - `repositories/` handles data access
   - `utils/` is stateless pure functions
   - The top-level `__init__.py` is the public API contract
