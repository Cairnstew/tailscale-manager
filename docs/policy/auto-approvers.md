# Auto Approvers

Users, groups, or tags that can bypass the approval process for advertising
subnet routes, exit nodes, and app connectors.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## Structure

```json
{
  "autoApprovers": {
    "routes": {
      "192.168.0.0/24": ["group:neteng", "tag:router"],
      "10.0.0.0/16":    ["tag:core-router"]
    },
    "exitNode": ["tag:exit-gateway"],
    "appConnectors": ["tag:app-connector-manager"]
  }
}

```

## Fields

### `routes`

Map of CIDR ranges to arrays of authorized approvers.

- Approving a range also permits advertising subnets of that range.
- Approvers: users, groups, autogroups, or tags.

### `exitNode`

Array of authorized approvers for exit node advertisements.

### `appConnectors`

Array of authorized approvers for app connector advertisements.
Note: the field name is `appConnectors` (plural), not `appConnector`.

## Rules

| Rule | Detail |
|---|---|
| First advertisement only | Auto-approval triggers only when Tailscale **first receives** a route advertisement. Updating `autoApprovers` does not retroactively approve existing unapproved routes. |
| Re-triggering | Remove and re-advertise the route to trigger auto-approval. |
| Stop condition | Tailscale stops advertising a route if the device is re-authenticated by a different user, or the advertising user is suspended/deleted. |
| Tag recommendation | Using a tag as an auto approver avoids disruption when users change. |

## Examples

### Network engineering auto-approves subnet routes

```json
{
  "autoApprovers": {
    "routes": {
      "10.0.0.0/8": ["group:neteng"]
    }
  }
}
```

### Tag-based exit node approval

```json
{
  "autoApprovers": {
    "exitNode": ["tag:corp-exit"]
  }
}
```

### Combined

```json
{
  "autoApprovers": {
    "routes": {
      "192.168.0.0/16": ["group:neteng", "alice@example.com"],
      "172.16.0.0/12":  ["tag:edge-router"]
    },
    "exitNode": ["tag:cloud-exit"]
  }
}
```
