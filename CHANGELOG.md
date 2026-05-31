# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

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
