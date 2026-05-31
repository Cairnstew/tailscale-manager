# Node Attributes

Per-device configuration for specialized features — NextDNS, Tailscale Funnel,
randomize-client-port, and app connectors.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## Structure

```json
{
  "nodeAttrs": [
    {
      "target": ["..."],
      "attr":   ["..."],
      "app":    { "...": [...] }
    }
  ]
}
```

## Fields

### `target`

Which nodes the attributes apply to.

| Selector | Example | Description |
|---|---|---|
| Any | `["*"]` | All devices |
| User | `["alice@example.com"]` | A specific user's devices |
| Group | `["group:kids"]` | Group members' devices |
| Tag | `["tag:server"]` | Tagged devices |
| Autogroup | `["autogroup:member"]` | Users with a role |

### `attr`

Array of attribute strings.

| Attribute | Description |
|---|---|
| `funnel` | Enable Tailscale Funnel on the node. |
| `randomize-client-port` | Use random WireGuard port instead of 41641. |
| `nextdns:<config-id>` | Apply a specific NextDNS configuration ID. |
| `nextdns:no-device-info` | Disable sending device metadata to NextDNS. |
| `disable-ipv4` | Disable IPv4 Tailscale address for the node. |

### `app`

Application-layer capabilities (similar to grants `app` field). The primary
use case is app connectors.

```json
{
  "target": ["*"],
  "app": {
    "tailscale.com/app-connectors": [
      {
        "name":       "example-app",
        "connectors": ["tag:example-connector"],
        "domains":    ["example.com"],
        "routes":     ["192.0.2.0/24"]
      }
    ]
  }
}
```

---

## Examples

### Funnel for all users

```json
{
  "nodeAttrs": [
    { "target": ["autogroup:member"], "attr": ["funnel"] }
  ]
}
```

### NextDNS per device group

```json
{
  "nodeAttrs": [
    { "target": ["tag:server"], "attr": ["nextdns:abc123"] },
    { "target": ["tag:iot"],    "attr": ["nextdns:xyz789", "nextdns:no-device-info"] }
  ]
}
```

### Randomize client port for office devices

```json
{
  "nodeAttrs": [
    { "target": ["tag:office-network", "group:sea-office"], "attr": ["randomize-client-port"] }
  ]
}
```

### App connector configuration

```json
{
  "nodeAttrs": [
    {
      "target": ["*"],
      "app": {
        "tailscale.com/app-connectors": [
          {
            "name":       "internal-apps",
            "connectors": ["tag:app-connector"],
            "domains":    ["internal.example.com"],
            "routes":     ["10.0.0.0/8"]
          }
        ]
      }
    }
  ]
}
```
