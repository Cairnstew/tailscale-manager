# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

## [Unreleased]

### Added
- `agenixIntegration` NixOS module option: after a successful apply, the
  generated Tailscale auth key is extracted from tfstate and pushed into
  `agenix-manager` as an encrypted secret via
  `agenix-manager new --overwrite`.
- `AgenixSyncResult` model with `status`, `secret_name`, and `error_message`.
- `agenix_sync` field in `last-apply.json` reporting sync status independently
  of the Terraform apply result.
- Four new environment variables: `TAILSCALE_MANAGER_AGENIX_ENABLE`,
  `TAILSCALE_MANAGER_AGENIX_SECRET_NAME`,
  `TAILSCALE_MANAGER_AGENIX_SECRET_SCOPE`, `TAILSCALE_MANAGER_AGENIX_BIN`.
- **`tailscale-manager watch`**: New CLI command that polls `policy.json` and
  `auth-keys.json` for content changes and automatically re-runs `apply`.
  Designed to run as a long-running daemon process.
- **`enableWatcher` NixOS module option**: When `true`, the tailscale-manager
  systemd service runs as `Type=simple` with `Restart=on-failure` and executes
  `tailscale-manager watch`. The watch command performs an initial apply on
  startup, then polls for file changes and re-applies automatically.
- **Activation script**: When the last apply failed, the error message is now
  printed during `nixos-rebuild switch` for immediate visibility.

### Fixed
- **`autoApprovers` nested defaults**: Changed the option type to
  `types.nullOr (types.submodule { ... })` with `default = null`, and each
  sub-field (`routes`, `exitNode`, `appConnectors`) to `nullOr` with
  `default = null`. This prevents empty nested defaults from leaking into
  the serialized JSON and causing Tailscale API 400 errors. The
  `stripAutoApprovers` helper was simplified to only filter `null` values.
- **Terraform error logging**: On apply failure, the full Terraform stderr
  (containing the API error body) is now logged at `ERROR` level before
  state rollback, making it easier to diagnose the root cause.

## [0.5.1] - 2026-06-02

### Added

- **`tailscale-manager auth-keys show-key <name>`**: Retrieve a declared auth
  key's value from Terraform state. Reads from `terraform.tfstate` where Terraform
  stores the key value. Prints the key to stdout with a warning on stderr.
  Accessible via `nix run .#show-key -- <name>`.
- **`nix run .#show-key`**: Nix flakes app target that wraps the
  `auth-keys show-key` CLI command.

### Security

- Key values are read from the state file at runtime — never baked into the
  Nix store. State file is 0600, root-owned. Warning printed to stderr before
  the key value to stdout for safe piping.

## [0.5.0] - 2026-06-02

### Added

- **`tailscale-manager auth-keys` CLI subcommand**: Create, list, and revoke
  auth keys via the Tailscale API directly (no Terraform). `create` prints the
  key value once with a warning; `list` supports `--json` output; `revoke`
  takes a key ID.
- **`services.tailscale-manager.authKeys` Nix option**: Declare multiple named
  auth keys with per-key `description`, `tags`, `reusable`, `ephemeral`,
  `preauthorized`, and `recreateIfInvalid`. Each key becomes a
  `tailscale_tailnet_key` Terraform resource. When non-empty, replaces the
  top-level `tags` / `recreateIfInvalid` legacy options. Serialized to JSON
  at build time via `ExecStartPre`, applied by the existing systemd service.
- **Backward compatible**: `authKeys = {}` (default) preserves legacy single-key
  behavior via top-level `tags` / `recreateIfInvalid`.

### Security

- **`.envrc` removed from git**: The `.envrc` file (containing real OAuth
  credentials) is now gitignored and untracked. Rotate exposed credentials.

## [0.4.3] - 2026-06-01

### Fixed

- **Systemd environment quoting**: `serviceConfig.Environment` replaced with
  NixOS `environment` attrset so `providerVersion` values containing spaces
  (e.g. `"~> 0.29"`) are properly quoted instead of being split by systemd.
- **ProtectHome / Terraform plugin cache**: `ProtectHome=true` remounts `/root/`
  as read-only, preventing Terraform from writing its provider plugin cache.
  The module now overrides `HOME` to the writable state directory.
- **Policy serialization**: Empty submodule fields (`"srcPosture": []`,
  `"via": []`) are now stripped from entries inside `grants`, `ssh`, `acls`
  before JSON serialization. The Tailscale API rejects `"srcPosture": []`
  with a 400 error.
- **VERSION sync**: `constants.py` kept in sync with `pyproject.toml`.
- **Policy changes not triggering apply on rebuild**: The oneshot service now
  has `restartIfChanged = true` (default for oneshot is `false`), so
  `nixos-rebuild switch` runs the service whenever the policy content changes
  (which alters the `ExecStartPre` store path hash, making the unit definition
  differ).

### Added

- **Textual TUI bundled in Nix build**: `textual` added to the Nix virtualenv
  via `workspace.deps.tui`, so `tailscale-manager status` launches the TUI
  automatically.

### Changed

- **README**: `tailnet` default corrected from *required* to `"-"` in module
  reference table; `TAILSCALE_TAILNET` env var no longer marked required;
  `doctor` subcommand added to CLI reference and exit codes table;
  Diagnostics section moved after CLI reference.

### Added

- **Example**: `examples/ssh-nixos/` — SSH access tiers for `tag:nixos` servers
  with admin `accept`, member `check`, and machine-to-machine rules.

### Changed

- **README**: `tailnet` default corrected from *required* to `"-"` in module
  reference table; `TAILSCALE_TAILNET` env var no longer marked required;
  `doctor` subcommand added to CLI reference and exit codes table;
  Diagnostics section moved after CLI reference.

## [0.4.2] - 2026-06-01

### Added

- **`tailscale-manager doctor`**: New pre-flight diagnostics subcommand.
  Checks credentials source, OAuth client ID/secret, tailnet, terraform
  binary/version, state directory, init status, state file/permissions,
  last apply result, ACL policy, and DNS config. Supports `--check-api`
  flag for OAuth connectivity test. Exits 0 on all pass, 1 on any failure.
- **Structured error panels**: `ConfigurationError` and `TerraformError` now
  render as rich `Panel` with sections (Field, Problem, Hint, Docs URL)
  instead of raw tracebacks.
- **First-run guidance**: `tailscale-manager init` prints a structured
  4-step guide on first run. `tailscale-manager apply` exits early with
  "not initialized" message if `.terraform/` is absent.
- **Error pattern hints**: Known Terraform failure patterns (tag ownership,
  OAuth credentials, permission denied, tailnet name, registry connectivity)
  are matched against stderr and produce specific, actionable hints.
- **assert_credentials()**: Separate method on `AppConfig` called explicitly
  by `plan`, `apply`, `destroy` only — `init`, `status`, `devices`, `doctor`
  no longer require OAuth credentials to be present at construction time.

### Fixed

- **TAILSCALE_TAILNET default**: No longer crashes with `ConfigurationError`
  when unset. Defaults to `"-"` (auto-resolve from OAuth credential).
- **Duplicate `ConfigurationError`**: Removed duplicate class definition from
  `config.py` — consolidated into `core/exceptions.py`.
- **CLI entry point**: Changed from `app` (Typer object) to `main()` wrapper
  to catch and render exceptions at the top level.

### Changed

- **NixOS module**: `tailnet` option defaults to `"-"`. Added
  `network-online.target` (waits for actual connectivity), `pkgs.getent`
  (glibc NSS fallback), `GODEBUG=netdns=go` (Go built-in DNS resolver).
  All previously manual workarounds are now baked in.
- **`TerraformError` and `ConfigurationError`**: Extended from bare `Exception`
  subclasses to `@dataclass` with structured fields (`message`, `field`,
  `hint`, `command`, `exit_code`, `stdout`, `stderr`).

## [0.4.1] - 2026-06-01

### Fixed

- **NixOS module**: empty `autoApprovers` sub-fields (`exitNode`, `appConnectors`) no longer leak into the serialized JSON, which could cause Tailscale API rejection. A targeted `stripAutoApprovers` helper strips empty collections from `autoApprovers` only, preserving semantically meaningful empty lists in `tagOwners`/`groups`.

### Added

- **GOTCHAS.md**: documented the `autoApprovers` empty-field leak and its fix.

## [0.3.2] - 2026-06-01

### Added

- **App connectors**: New `services.tailscale-manager.policy.appConnectors` option
  for declarative app connector configuration. Synthesizes the correct
  `nodeAttrs` entry with `tailscale.com/app-connectors` capability, with
  assertions for duplicate names, mutual exclusion with manual `nodeAttrs.app`
  entries, and missing `policy.enable`/`acl.enable`. Includes full Nix module
  options, Python serialization tests, and documentation.
- **Live auth keys in TUI**: TUI now fetches auth keys from the Tailscale API
  (`/api/v2/tailnet/-/keys`) instead of parsing tfstate. Falls back to
  tfstate on API error. New `src/tailscale_manager/services/api_client.py`
  module for OAuth-authenticated API access.
- **Example configurations**: `examples/basic/` with `policy.nix` + `policy.json`
  side-by-side for all policy sections including app connectors.

### Changed

- **TUI visual overhaul**: Glass-morphism design with frosted panels,
  dark color scheme (`#0a0e14`), colored status indicators (green/red/yellow
  dots), dimmed secondary text, styled `DataTable` headers and rows.
  Layout reorganized: devices above auth keys in the left column.
- **TUI key column relabeled**: `Keys` → `Auth Keys` for clarity.
- **Terraform config** now generates 5 files instead of 6 (`settings.tf.json`
  removed).
- **`autoApprovers.appConnector`** renamed to `autoApprovers.appConnectors` to
  match the Tailscale API field name.

### Removed

- **`tailnetSettings` option**: Removed `services.tailscale-manager.tailnetSettings`
  and all related Python/Terraform plumbing (`TailnetSettings` model,
  `build_settings_config`, `settings.tf.json`). The Tailscale API exposes OAuth
  client credentials to `GET/PATCH /api/v2/tailnet/-/settings`, which is a
  security concern — tailnet-wide settings should be managed through the admin
  console or a separate, more restricted workflow.

### Fixed

- `ConfigDict(populate_by_name=True)` in Pydantic models so `validation_alias`
  doesn't block Python field name access.

## [0.3.1] - 2026-05-31

### Added

- **Structured policy options**: Replaced raw `services.tailscale-manager.acl.policy`
  string with `services.tailscale-manager.policy` — a full set of typed Nix submodule
  options mirroring the entire Tailscale policy file JSON schema: `grants`, `acls`,
  `ssh`, `tagOwners`, `groups`, `hosts`, `ipsets`, `postures`, `nodeAttrs`,
  `autoApprovers`, `tests`, `sshTests`, `derpMap`, `disableIPv4`,
  `randomizeClientPort`, `oneCGNATRoute`.
- **Documentation**: Comprehensive policy file reference under `docs/policy/` —
  16 files covering every section of the Tailscale policy file with exact JSON
  structures, field types, allowable values, and examples. Also `docs/OAUTH.md`,
  `docs/API.md`, `docs/CONCEPTS.md`.
- **GOTCHAS.md**: Entry documenting the `filterAttrs` vs `filterAttrsRecursive`
  footgun for policy serialization.

### Changed

- Policy serialization uses `lib.filterAttrs` (non-recursive) to preserve
  semantically meaningful empty lists in nested attrsets like `tagOwners`.
- Python `AppConfig` reads policy from `TAILSCALE_MANAGER_ACL_POLICY_PATH` env
  var via a `model_validator`, supporting both NixOS file-based injection and
  direct env-var usage outside NixOS.
- `test_build_acl_config_enabled_hujson` updated to expect
  `overwrite_existing_content: True`.
- DNS split nameserver tests reconciled with the aggregated single-resource format.

### Fixed

- `tagOwners` entries with empty owner lists (e.g. `"tag:server": []`) no longer
  silently dropped from serialized policy JSON. These are semantically distinct
  from absent entries.
- `filterAttrsRecursive` replaced with `filterAttrs` to avoid stripping
  meaningful empty values from nested attrsets.

## [0.3.0] - 2026-05-31

### Added
- **DNS management**: Declarative DNS nameservers, MagicDNS, and split DNS via
  `services.tailscale-manager.dns`. Generates `tailscale_dns_nameservers`,
  `tailscale_dns_preferences`, and `tailscale_dns_split_nameservers` resources.
- **Tailnet settings**: Declarative tailnet-wide settings via
  `services.tailscale-manager.tailnetSettings`. Supports device approval,
  auto-updates, key duration, HTTPS enforcement, and more.
- **ACL management**: Full tailnet ACL policy management via
  `services.tailscale-manager.acl`. Opt-in only (`acl.enable = true`).
  Supports HuJSON and JSON formats. Automatic backup of current policy before
  every apply with restore on failure.
- **Device discovery**: Read-only `data.tailscale_devices` data source always
  included. New `tailscale-manager devices` CLI subcommand and live device
  panel in the TUI.
- **Init preflight warnings**: `tailscale-manager init` prints non-blocking
  warnings about required OAuth scopes when scope-dependent features are configured.

### Changed
- Terraform config split from single `main.tf.json` into multiple files
  (`keys.tf.json`, `dns.tf.json`, `settings.tf.json`, `acl.tf.json`,
  `data.tf.json`). Terraform merges automatically; no user action required.
- TUI layout updated to 3-column view with devices panel (toggle with `d`).
- `write_config()` renamed to `write_configs()` and now writes multiple
  `.tf.json` files, returning True if any file changed.

### Migration
- New features require additional OAuth client scopes: `devices:read`,
  `dns:write`, `tailnet:settings`, `tailnet:acls`. Update your OAuth client
  in the Tailscale admin console.
- All new options are optional with safe defaults. No config changes required
  to upgrade from v0.1.x or v0.2.x.

## [0.1.1] - 2026-05-31

### Changed
- Bump Tailscale Terraform provider pin from `~> 0.16` to `~> 0.29`

### Fixed
- Add `recreate_if_invalid = "always"` to managed auth key resource —
  prevents silently expired keys from persisting in state without rotation

## [0.1.0] - 2026-05-31

### Added
- NixOS module (`services.tailscale-manager`) with systemd service,
  credential watcher via systemd path unit, and backup/restore on failure
- Home Manager module (`programs.tailscale-manager`) for user-level CLI install
- CLI subcommands: init, plan, apply, destroy, status, backup-state,
  restore-state, version
- Read-only Textual TUI dashboard (`tailscale-manager status`) showing
  managed key state and last apply result
- Automatic tfstate backup before every apply with configurable retention
  (`backupCount` option)
- Failure handling: backup restored on apply failure, result written to
  `last-apply.json`, non-zero exit for systemd monitoring
- `status --json` for waybar/scripting integration with exit code signaling
- Activation script prints last apply result after `nixos-rebuild switch`

### Changed
- Terraform provider credentials use canonical env vars
  `TAILSCALE_OAUTH_CLIENT_ID` / `TAILSCALE_OAUTH_CLIENT_SECRET`
- Provider block omits credentials (auto-read from env by Tailscale provider)
- `terraform plan` exit code 2 treated as success (non-empty diff)

### Fixed
- N/A (initial release)

### Security
- Credentials never written to `main.tf.json` — Terraform reads them
  directly from the process environment at apply time
