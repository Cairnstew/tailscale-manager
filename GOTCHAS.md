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

## AutoApprovers: empty sub-fields leak into JSON

`autoApprovers` is a submodule with `routes` (default `{}`), `exitNode`
(default `[]`), and `appConnectors` (default `[]`). If you set only one
sub-field, the others still appear as empty `{}`/`[]` in the serialized
JSON. Tailscale's API may reject these empty values.

The fix: `stripAutoApprovers` in `module.nix` removes any empty sub-field
from `autoApprovers` before serialization. This is applied in addition to
the top-level `filterAttrs` — note the difference: the top-level filter
can't reach inside `autoApprovers` because the attrset as a whole is
non-empty.

This is **not** a general recursive filter — only `autoApprovers` is
stripped. `tagOwners` and `groups` are left alone because empty lists
are semantically meaningful there.

## Policy serialization: two-layer cleanup

The module uses a two-layer cleanup strategy for the serialized policy JSON:

**Layer 1 — submodule entries** (`cleanEntry`): inside `grants`, `ssh`, `acls`,
`tests`, `sshTests`, and `nodeAttrs` lists, each entry's direct fields are
cleaned by removing any key whose value is `null`, `[]`, or `{}`. This prevents
the Tailscale API from rejecting fields like `"srcPosture": []` (returns 400)
and removes serialization bloat from unset optional defaults.

**Layer 2 — top-level** (`filterAttrs`): keys at the policy root are removed
if their value is empty/null. This drops unused sections (`hosts`, `ipsets`,
`postures`, etc.) that would otherwise appear as `{}` or `[]` in the JSON.

Neither layer uses `filterAttrsRecursive` because it would descend into
semantically meaningful empty lists inside `tagOwners` or `groups` —
`tagOwners."tag:server" = []` means "admin-only tag" and must be preserved.

## App connectors: nodeAttrs.app and appConnectors are mutually exclusive

If you use `policy.appConnectors`, do not also set an `app` field on any
`policy.nodeAttrs` entry. The module will raise an assertion error. If you
need a custom app capability alongside app connectors, define the entire
nodeAttrs block manually via `policy.nodeAttrs` and set
`appConnectors = []`.

## App connectors: connector tag ownership is your responsibility

`policy.appConnectors` does NOT auto-generate `tagOwners` entries. You must
declare `tagOwners` for every tag in your `connectors` lists, or the Tailscale
API will reject the policy with a "tag not owned" error.

## App connectors: routes are implicitly approved

Routes defined inside a `policy.appConnectors` entry do NOT need a matching
`autoApprovers.routes` entry — Tailscale implicitly approves them when they're
declared in the policy file. You only need `autoApprovers.routes` for routes
that are advertised externally (e.g. via `tailscale up --advertise-routes` on
a device that isn't the connector).

## Policy file overwrites admin console changes

If you use Terraform (via tailscale-manager) to manage the policy file,
any changes made in the Tailscale admin console (ACLs, app connectors, etc.)
will be overwritten on the next `nixos-rebuild switch`. Manage everything
declaratively via `services.tailscale-manager.policy`.

## Tailscale Manager

### LoadCredential replaces EnvironmentFile (v0.4.0+)

The NixOS module now uses systemd `LoadCredential` instead of
`EnvironmentFile` for OAuth credential delivery. This prevents
credentials from appearing in `/proc/<pid>/environ` or systemd
journal logs. The credential file format is unchanged (KEY=VALUE).

When running outside systemd (dev shells, CI), the CLI falls back to
reading `TAILSCALE_OAUTH_CLIENT_ID` and `TAILSCALE_OAUTH_CLIENT_SECRET`
from the environment directly.

### State directory permissions

The systemd service creates `stateDir` with mode `0700`. All files
written by the service (`.tf.json`, `tfstate`, backups, policy.json)
are created with mode `0600`. If you see a "permissions wider than
0600" warning in `tailscale-manager status`, run:
```
chmod 0600 /var/lib/tailscale-manager/terraform.tfstate
```

### Sandboxing may block unusual syscalls

The service runs with `SystemCallFilter = "@system-service"`. If you
see the service killed by seccomp (journal shows `SIGSYS`), the filter
may need to be relaxed. This is rare — the standard syscall set covers
Python, subprocess, and Terraform operations.

### DNS resolution in sandboxed services

The Go-based Terraform provider resolves HTTPS endpoints (Tailscale API,
Terraform registry) at runtime. Under `ProtectSystem = "strict"` and
`CapabilityBoundingSet = ""`, glibc's NSS-based DNS resolver can fail
because it cannot access system databases (hosts, services) via `getent`.

The module handles this automatically:

- `GODEBUG=netdns=go` — forces Go to use its pure-Go DNS resolver
  (direct queries, no NSS dependency).
- `path = [ pkgs.getent ]` — ensures `getent` is available if Go falls
  back to the system resolver.
- `wants` / `after = [ "network-online.target" ]` — waits for actual
  network connectivity, not just the network service starting.

No manual workaround is needed.

### Environment variables with spaces (providerVersion)

The module uses NixOS's `environment` attrset (not `serviceConfig.Environment`)
so values containing spaces — like `providerVersion = "~> 0.29"` — are
automatically quoted by systemd's unit file generator. The `Environment=`
directive in `serviceConfig` splits on whitespace, which would otherwise
truncate `~> 0.29` to just `~>`.

### ProtectHome and the Terraform plugin cache

The service sets `ProtectHome = true`, which remounts `/root/` as an empty
read-only tmpfs. The module overrides `HOME` to point at the writable state
directory so Terraform can write its provider plugin cache to
`$stateDir/.terraform.d/` instead.

### Terraform binary must be from the Nix store

The module asserts that `terraformBin` starts with `/nix/store`. This
ensures binary integrity. Use `${pkgs.terraform}/bin/terraform` (the
default) or another Nix-store path.

### Subprocess environment is strictly limited

The CLI runs terraform with a strict environment allowlist — only
explicitly needed variables are passed to the subprocess. This prevents
accidental credential leakage via environment inheritance. The allowlist
includes `SSL_CERT_FILE` and `NIX_SSL_CERT_FILE` because the Terraform
provider makes HTTPS calls to the Tailscale API and NixOS does not use
FHS certificate paths.

### Audit logging in last-apply.json

After each apply, `last-apply.json` includes `actions` (per-resource
create/update/delete), `add_count`, `change_count`, and `remove_count`.
Old entries without these fields are handled gracefully — missing fields
default to `null` or `0`.

### Policy file content in Nix store

The policy JSON is computed at Nix eval time and written to the Nix
store as a derivation input. At service start, an `ExecStartPre` script
copies it to `stateDir/policy.json` with mode `0600`. The store path
is world-readable on the build machine — this approach protects against
casual runtime enumeration but not against a determined local user who
can read the Nix store. If the policy is genuinely sensitive, pass it
as a secret via agenix/sops rather than computing it in Nix.

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

### Tailnet defaults to "-"

If `TAILSCALE_TAILNET` is not set, it defaults to `"-"` which tells the
Tailscale API to auto-resolve the tailnet from the OAuth credential. This
is the recommended default for most users. You only need to set it explicitly
if you manage multiple tailnets with the same OAuth client.

### Pre-flight checks with `tailscale-manager doctor`

Run `tailscale-manager doctor` before `apply` to verify your configuration.
It checks credentials, terraform binary, state directory, initialization
status, and last apply result. Add `--check-api` to also test OAuth
connectivity to the Tailscale API.

### OAuth scope error patterns

Common Terraform errors and their fixes:

| Error pattern | Fix |
|---|---|
| `does not own tag:` | Add tag ownership in admin console → Settings → OAuth → your client → Tag ownership |
| `permission denied` | Verify OAuth scopes include the required permissions |
| `no such tailnet` | Use `"-"` for tailnet to auto-resolve, or check the tailnet name |
| `registry.terraform.io` | Check internet connectivity — provider download failed |

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
The CI orchestrator (`ci.yml`) uses `dorny/paths-filter` to detect changed paths. If you add a new file type or directory that should trigger a specific workflow, update the filters in the `changes` job.

`unit` tests are required (hard failure). Integration and e2e jobs in `test-integration.yml` use `continue-on-error: true`. If CI is green but integration tests are red, check the workflow run summary — they're reported separately.
