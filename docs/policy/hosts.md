# Hosts

Named aliases for IP addresses and CIDR ranges, usable in ACL/grants source
and destination selectors.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## Structure

```json
{
  "hosts": {
    "jump-box":    "100.100.100.100",
    "db-server":  "100.100.100.101",
    "office-net": "203.0.113.0/24",
    "dc-range":   "198.51.100.0/24"
  }
}
```

## Rules

| Rule | Detail |
|---|---|
| Name | Cannot contain `@`. |
| Value | A single IPv4/IPv6 address or a CIDR range. |
| Usage | Referenced as `jump-box:22` in ACL `dst` fields, or as `"jump-box"` in grant selectors. |

## Examples

### Using hosts in ACLs

```json
{
  "hosts": {
    "bastion":  "100.100.100.10",
    "monitoring": "100.100.100.20"
  },
  "acls": [
    { "action": "accept", "src": ["autogroup:admin"], "dst": ["bastion:22"] },
    { "action": "accept", "src": ["autogroup:member"], "dst": ["monitoring:3000"] }
  ]
}
```

### Using hosts in grants

```json
{
  "hosts": {
    "db-cluster": "100.100.100.0/24"
  },
  "grants": [
    { "src": ["group:backend"], "dst": ["db-cluster"], "ip": ["tcp:5432"] }
  ]
}
```

### Using hosts in tests

```json
{
  "hosts": { "critical-db": "100.100.100.50" },
  "tests": [
    { "src": "alice@example.com", "accept": ["critical-db:5432"] }
  ]
}
```
