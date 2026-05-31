# Gotchas

## uv2nix

### uv.lock required for evaluation
The flake won't evaluate without a `uv.lock`. Use `nix develop .#bootstrap` to get Python + uv, then run `uv lock`.

### uv.lock doesn't contain build systems
uv [doesn't lock build systems](https://github.com/astral-sh/uv/issues/5190). uv2nix uses `pyproject-build-systems` overlay to supply them. If a build system isn't in that repo, you must supply it via an overlay.

### Don't use `uv run` inside the dev shell
`uv run` creates its own venv, defeating uv2nix's provisioning. The dev shell already makes all scripts/entry points available directly.

### Don't filter sources at workspace root
`uv2nix.lib.workspace.loadWorkspace` reads from the workspace root at evaluation time. Filtering there causes IFD and breaks editables. Filter per-package instead.

### Editable packages need `REPO_ROOT`
The editable overlay uses `$REPO_ROOT` to locate the source tree. The dev shell `shellHook` sets it via `git rev-parse --show-toplevel`. If you're not in a git repo, set it manually.

### `unset PYTHONPATH`
Nixpkgs Python builders set `PYTHONPATH`, which leaks into unrelated builds. Always unset it in the dev shell `shellHook`.

### MacOS wheels may not match
Nixpkgs doesn't know your actual macOS version. Set `darwinSdkVersion` explicitly in the `stdenv` override if wheel compatibility fails.

## uv / Python

### setuptools.backends._legacy is gone
`setuptools.backends._legacy._Backend` was removed in modern setuptools. Use `setuptools.build_meta` instead.

### `tool.uv.dev-dependencies` is deprecated
Use `[dependency-groups] dev = [...]` instead (modern uv convention).

## Nix

### Python version mismatch
If `flake.nix` uses `pkgs.python3` but `pyproject.toml` says `requires-python = ">=3.12"`, you may get interpreter incompatibilities. Either pin `python = pkgs.python312` in `flake.nix`, or use the auto-filter approach from the uv2nix docs.

### result symlinks
`nix build` creates `result` symlinks. These are in `.gitignore` but can confuse tooling if you build inside the repo.

### Flake lock drift
After changing flake inputs, run `nix flake lock` to update `flake.lock`. Otherwise you'll silently use the old pinned versions.

## Tailscale Manager

### terraform binary not in Python deps
The `terraform` binary is NOT a Python dependency. It's provided by the NixOS module via
`services.tailscale-manager.terraformBin` (default: `${pkgs.terraform}/bin/terraform`).
Do not try to pip-install terraform.

### Terraform provider downloaded at runtime
The Tailscale Terraform provider (`tailscale/tailscale`) is downloaded by `terraform init`
into the state directory's `.terraform/` subdirectory at runtime. This requires network
access on the target machine. For fully offline builds, look into `pkgs.terraform-providers.tailscale`
and generate a provider mirror — but this is a future enhancement.

### Airgap / corporate network
On a fresh machine — or after wiping `stateDir` — the first `nixos-rebuild switch` will
need outbound internet access to `registry.terraform.io` to download the Tailscale provider.
If outbound HTTP(S) is blocked (corporate proxy, airgapped deployment), the service will
fail silently. Since the CLI now exits non-zero on failure, `systemctl status` will show
red, and `last-apply.json` will contain the Terraform error message — but the root cause
(provider download failure) may not be obvious at a glance.

Workarounds:
- Pre-run `terraform init` manually on a machine with internet, then copy the
  `.terraform/` directory to the target machine.
- Deploy a Terraform provider mirror (custom or using
  `pkgs.terraform-providers.tailscale`) and pass `-plugin-dir` or configure the
  mirror in Terraform's CLI config.

### CDKTF is deprecated (Dec 2025)
Do NOT use `cdktf` or `cdktf-cdktf-provider-*` PyPI packages. This project uses
subprocess + JSON-format HCL (Option A), which is simpler and doesn't depend on CDKTF's
deprecated Python bindings.

### Credentials via EnvironmentFile
The NixOS module reads credentials from an EnvironmentFile (KEY=VAL format). Use agenix
or sops-nix to encrypt this file. The module accepts any path via `credentialsFile`.

The OAuth credentials are passed to the Tailscale Terraform provider via
`TAILSCALE_OAUTH_CLIENT_ID` and `TAILSCALE_OAUTH_CLIENT_SECRET` environment
variables — the provider picks them up automatically, so they never appear in
the generated `main.tf.json`.

### Tailscale OAuth client must own tags to create keys
When using OAuth client credentials, the Tailscale API creates tailnet-owned keys.
Tailnet-owned keys **require tags**, and the OAuth client must be a **tag owner**
for those tags in the Tailscale admin console.

To configure this:
1. Go to https://login.tailscale.com/admin/settings/oauth
2. Find your OAuth client → Edit → **Tag ownership**
3. Add the tags the client can use (e.g. `tag:ci`, `tag:infra`)
4. Pass those tags via `services.tailscale-manager.tags` in the NixOS module

Without this, `terraform apply` will fail with:
```
Error creating tailnet key: tailnet-owned auth key must have tags set (400)
```
or:
```
Error creating tailnet key: requested tags [tag:xxx] are invalid or not permitted (400)
```

See [Tailscale OAuth docs](https://tailscale.com/kb/1215/oauth-clients) for details.

## CI / GitHub Actions

### `flake-checker-action` telemetry
The `flake-checker-action` (used in setup-nix) phones home to Determinate Systems' telemetry service. This is fine for most projects — worth knowing for audit-sensitive environments.

### Test tiers are detected by directory presence
The CI `detect` job checks if `tests/$tier/test_*.py` exists. If you add a new tier directory, it won't be run until you add it to the `for dir in` loop in `ci.yml`.

### `nix develop .#bootstrap` vs `nix develop`
Lint and typecheck use `.#bootstrap` (fast, no uv2nix venv). Tests use `nix develop` (full hermetic environment). If lint/typecheck fail but tests pass, the issue is tool version mismatch between the two shells — check both have the same ruff/mypy version.

### `continue-on-error` for integration/e2e
`unit` tests are required (hard failure). `integration` and `e2e` use `continue-on-error: true`. If CI is green but integration tests are red, check the workflow run summary — they're reported separately.
