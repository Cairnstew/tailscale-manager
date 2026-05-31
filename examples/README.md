# Examples

Example configurations showing how to use `services.tailscale-manager.policy`
with the structured Nix options, alongside their equivalent JSON output.

Each example has:

| File | What it shows |
|---|---|
| `policy.nix` | User-facing NixOS module config with structured policy options |
| `policy.json` | The serialized JSON that gets pushed to the Tailscale API |
| `README.md` (optional) | Notes about what this example demonstrates |

To apply an example locally, copy the `policy.nix` block into your
`configuration.nix` or flake module, or use the JSON directly with
`tailscale_acl` in standalone Terraform.

## Index

| Directory | Description |
|---|---|
| [`basic/`](./basic/) | Comprehensive demo — grants, SSH, tagOwners, hosts, ipsets, postures, nodeAttrs, autoApprovers |
