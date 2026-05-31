# IP Sets

Named collections of IP addresses, CIDR ranges, hosts, and other IP sets.
They let you group multiple network segments into a single reusable selector.

> **Source**: [Tailscale Docs — IP sets](https://tailscale.com/docs/features/ip-sets)
> Last validated: Apr 8, 2026

---

## Structure

```json
{
  "ipsets": {
    "ipset:datacenters": [
      "203.0.113.0/24",
      "198.51.100.5",
      "jump-box"
    ],
    "ipset:cloud-ranges": [
      "ipset:datacenters",
      "10.0.0.0/8"
    ]
  }
}
```

## Rules

| Rule | Detail |
|---|---|
| Prefix | Must start with `ipset:`. |
| Members | IP addresses, CIDR ranges, host aliases, or other IP sets. |
| Nesting | IP sets **can** contain other IP sets. |
| Usage | Referenced as `ipset:datacenters` in ACL/grants selectors. |

## Examples

### IP sets in ACLs

```json
{
  "ipsets": {
    "ipset:prod":  ["10.0.1.0/24", "10.0.2.0/24"],
    "ipset:staging": ["10.0.3.0/24"]
  },
  "acls": [
    { "action": "accept", "src": ["group:devops"], "dst": ["ipset:prod:*"] }
  ]
}
```

### IP sets in grants

```json
{
  "ipsets": {
    "ipset:internal-services": [
      "100.100.0.0/16",
      "10.0.0.0/8"
    ]
  },
  "grants": [
    {
      "src": ["autogroup:member"],
      "dst": ["ipset:internal-services"],
      "ip":  ["*"]
    }
  ]
}
```

### Nesting IP sets

```json
{
  "ipsets": {
    "ipset:us-east":  ["100.64.1.0/24", "100.64.2.0/24"],
    "ipset:us-west":  ["100.64.3.0/24", "100.64.4.0/24"],
    "ipset:all-regions": ["ipset:us-east", "ipset:us-west"]
  }
}
```
