# Grants

Next-generation access control combining network-layer and application-layer
capabilities in a unified syntax. **Preferred over ACLs** for all new policies.

> **Source**: [Tailscale Docs — Grants syntax](https://tailscale.com/docs/reference/syntax/grants)
> Last validated: Jan 5, 2026

---

## Core concepts

- **Deny-by-default** — access must be explicitly granted.
- **Union semantics** — multiple matching grants combine; more specific grants
  do not override less specific ones.
- **App capabilities only apply** if network-layer access is also granted.
- **Local caching** — compiled grants are distributed to and cached by every
  Tailscale client.

---

## Structure

```json
{
  "grants": [
    {
      "src":        ["..."],
      "dst":        ["..."],
      "ip":         ["..."],
      "app":        { "...": [...] },
      "srcPosture": ["..."],
      "via":        ["..."]
    }
  ]
}
```

## Fields

### `src` (required)

Array of [source selectors](./selectors.md).

### `dst` (required)

Array of [destination selectors](./selectors.md). In grants, destinations also
support `svc:<serviceName>` for Tailscale Services.

### `ip` (required if no `app`)

Array of network-layer capability selectors.

| Selector | Example | Description |
|---|---|---|
| All ports/protocols | `"*"` | TCP + UDP + ICMP on all ports |
| Single port | `"443"` | TCP + UDP on port 443 |
| Port range | `"80-443"` | TCP + UDP on ports 80-443 |
| Protocol all ports | `"icmp:*"` | All ports of the given protocol |
| Protocol + port | `"tcp:443"` | Specific protocol and port |
| Protocol + range | `"tcp:80-443"` | Specific protocol and port range |

Named protocol aliases:

| Protocol | Alias | IANA # |
|---|---|---|
| IGMP | `igmp` | 2 |
| IP-in-IP | `ipv4`, `ip-in-ip` | 4 |
| TCP | `tcp` | 6 |
| EGP | `egp` | 8 |
| IGP | `igp` | 9 |
| UDP | `udp` | 17 |
| GRE | `gre` | 47 |
| ESP | `esp` | 50 |
| AH | `ah` | 51 |
| SCTP | `sctp` | 132 |

### `app` (required if no `ip`)

Optional. Map of application capability identifiers to parameter objects.

```json
"app": {
  "tailscale.com/cap/tailsql": [
    { "dataSrc": ["*"] }
  ],
  "tailscale.com/cap/golink": [
    { "admin": true }
  ],
  "tailscale.com/cap/kubernetes": [
    { "impersonate": { "groups": ["system:masters"] } }
  ]
}
```

- Format: `<domain>/<capabilityName>`
- `tailscale.com` and `tailscale.io` are reserved.
- Parameters are opaque JSON — the policy engine validates JSON syntax only.
- Application defines its own parameter schema.

### `srcPosture`

Optional. Array of [posture conditions](../postures.md) to further restrict
the source.

### `via`

Optional. Array of tags specifying routing devices (exit nodes, subnet routers,
app connectors) that traffic must go through.

```json
"via": ["tag:my-exit-node"]
```

- Only tags are valid in `via`.
- Sets `[]` or `null` or omit to allow any route.

---

## Selector reference

See [`selectors.md`](./selectors.md) for the complete list of source and
destination selectors available in grants.

---

## Examples

### Basic network access

```json
{
  "grants": [
    { "src": ["group:engineering"], "dst": ["tag:server"], "ip": ["*"] }
  ]
}
```

### Application-layer only

```json
{
  "grants": [
    {
      "src": ["group:engineering"],
      "dst": ["tag:tailsql"],
      "app": { "tailscale.com/cap/tailsql": [{ "dataSrc": ["*"] }] }
    }
  ]
}
```

### Network + app combined

```json
{
  "grants": [
    {
      "src": ["alice@example.com"],
      "dst": ["tag:prod"],
      "ip":  ["*"],
      "app": { "tailscale.com/cap/golink": [{ "admin": true }] }
    }
  ]
}
```

### Forced routing via specific exit node

```json
{
  "grants": [
    {
      "src": ["group:engineering"],
      "dst": ["autogroup:internet"],
      "ip":  ["*"],
      "via": ["tag:corp-exit"]
    }
  ]
}
```

### Posture-restricted access

```json
{
  "grants": [
    {
      "src":        ["group:engineering"],
      "dst":        ["tag:prod"],
      "ip":         ["tcp:22"],
      "srcPosture": ["posture:latestMac"]
    }
  ]
}
```
