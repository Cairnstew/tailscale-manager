# Tests & SSH Tests

Assertions that run every time the policy file changes. If a test fails,
Tailscale **rejects** the updated policy with an error.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## ACL/Grant Tests

### Structure

```json
{
  "tests": [
    {
      "src":             "dave@example.com",
      "srcPostureAttrs": { "node:os": "windows" },
      "proto":           "tcp",
      "accept":          ["example-host-1:22", "vega:80"],
      "deny":            ["192.0.2.3:443"]
    }
  ]
}
```

### Fields

#### `src`

Required. The identity to test from. Can be:

- User email: `"alice@example.com"`
- Group: `"group:engineering"`
- Tag: `"tag:production"`
- Host: `"my-host"` (from `hosts` section)

Cannot use `*`.

#### `srcPostureAttrs`

Optional. Key-value pairs of posture attributes to use when evaluating
posture conditions in access rules.

#### `proto`

Optional. Protocol to test. Defaults to TCP+UDP. Use `"icmp"` with port `0`
for ICMP (ping) tests.

#### `accept` / `deny`

Required. Arrays of `host:port` destinations where `port` is a single
numeric port.

| Host Type | Example | Description |
|---|---|---|
| Tailscale IP | `100.100.123.123:443` | Specific device |
| Host | `my-host:22` | From `hosts` section |
| User | `alice@example.com:80` | User's devices |
| Group | `group:engineering:443` | Group members' devices |
| Tag | `tag:production:22` | Tagged devices |
| Service | `svc:my-service:443` | Tailscale Service |

Cannot use CIDR notation or `*`. Legacy `allow` still works but prefer `accept`.

### ICMP test example

```json
{
  "tests": [
    {
      "src":    "alice@example.com",
      "proto":  "icmp",
      "accept": ["tag:production:0"]
    }
  ]
}
```

---

## SSH Tests

### Structure

```json
{
  "sshTests": [
    {
      "src":             "dave@example.com",
      "dst":             ["example-host-1"],
      "accept":          ["dave"],
      "check":           ["admin"],
      "deny":            ["root"],
      "srcPostureAttrs": { "node:os": "windows" }
    }
  ]
}
```

### Fields

#### `src`

Required. The SSH client identity.

#### `dst`

Required. Array of one or more destinations (user, group, tag, host).

#### `accept`

SSH usernames that should be accepted without additional checks.

#### `check`

SSH usernames that should require re-authentication checks.

#### `deny`

SSH usernames that should be denied under any circumstances.

#### `srcPostureAttrs`

Optional posture attributes for evaluating posture conditions.

---

## Examples

### Ensure critical access is not revoked

```json
{
  "tests": [
    {
      "src":    "oncall@example.com",
      "accept": ["tag:prod:22", "tag:prod:443"],
      "deny":   ["tag:prod:3389"]
    },
    {
      "src":    "auditor@example.com",
      "accept": ["tag:logging:22"],
      "deny":   ["tag:prod:*", "tag:staging:*"]
    }
  ]
}
```

### Ensure subnet router isolation

```json
{
  "tests": [
    {
      "src":    "external-vendor@example.com",
      "accept": ["100.100.100.1:443"],
      "deny":   ["198.51.100.7:22"]
    }
  ]
}
```

### SSH test for SRE access

```json
{
  "sshTests": [
    {
      "src":    "sre-lead@example.com",
      "dst":    ["tag:prod"],
      "accept": ["root"],
      "deny":   ["alice"]
    }
  ]
}
```
