# SSH for NixOS servers (`tag:nixos`)

Demonstrates Tailscale SSH rules with `tag:nixos` managed devices.

## Tagged devices

Devices tagged `tag:nixos` represent NixOS servers in the tailnet. The admin
group owns the tag (see `tagOwners`).

## SSH access tiers

| Tier | Action | Who | SSH user | Re-auth |
|---|---|---|---|---|
| Admin | `accept` | Admin group | root + nonroot | No |
| Standard | `check` | All members | nonroot only | Every 12h |
| Machine | `accept` | Other nixos devices | root | No |

## Requirements

For SSH to work, the Tailscale SSH service must be enabled on each NixOS
device:

```nix
services.tailscale.enable = true;
services.tailscale.permitCert = false;  # optional
services.tailscale.useRoutingFeatures = "server";  # if also routing
```

No client-side SSH config changes needed — Tailscale SSH authenticates and
authorises via the coordination server.

## Key points

- **Grants + SSH**: SSH rules only control the SSH *protocol layer*. The
  network-layer grant (`tcp:22`) must also allow the traffic, or SSH
  connections are dropped before the SSH rule is evaluated.
- **Check vs Accept**: `check` forces periodic re-authentication (shown as a
  Tailscale SSH notification). `accept` allows seamless access — use for
  trusted users and machine-to-machine automation.
- **Machine-to-machine**: Tag-to-tag SSH is a common pattern for orchestration
  tools (Ansible, Salt, Nix remote builds). Tagged devices don't have a human
  to re-auth, so `accept` is the only valid action for tag-to-tag SSH.
- **No port in SSH rules**: SSH rules don't take a port — they always apply
  to port 22. The port is controlled by the grant/ACL rule.
