# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

## [Unreleased]

### Added
- Opt-in `enableTimer` option for daily systemd timer (default: `false`)
- `recreateIfInvalid` module option (default: `"always"`) — controls key
  rotation automatically via Terraform resource attribute
- `providerVersion` module option (default: `"~> 0.29"`) — pin the Tailscale
  Terraform provider version from NixOS config
- `write_config()` idempotent method — skips writing `main.tf.json` when
  content is unchanged, avoiding unnecessary Terraform diffs
- Tag validation in `AppConfig` — tags must start with `tag:` prefix
- Assertions block for `credentialsFile` — clear error message with
  agenix/sops examples if not set
- `Justfile` with common dev commands: `just lint`, `just typecheck`,
  `just test`, `just check`, `just build`, `just fmt`
- Pre-commit hooks config (ruff + mypy)

### Changed
- Module `package` option no longer has a hard default — injected
  automatically by `nixosModules.default` from the flake's package set
- Home Manager `package` option same pattern — injected by
  `homeManagerModules.default`
- `generate_config()` renamed to `write_config()`, returns `bool`
  (True if written, False if unchanged)
- `TerraformService` uses `config.provider_version` and
  `config.recreate_if_invalid` instead of hardcoded constants
- README: detailed OAuth client setup section, expanded module
  options table with all new options, env var table updated
- NixOS module `credentialsFile` type changed to `nullOr path`
  (default `null`) with assertion for better error messaging

### Fixed
- `pkgs.tailscale-manager` default removed — module was broken for
  anyone who imported it directly without overriding `package`
- Tag env var description now explicitly documents the comma-separated
  format and `tag:` prefix requirement

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
