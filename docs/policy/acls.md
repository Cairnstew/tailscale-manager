# ACLs

First-generation network-layer access control rules. **Prefer grants**
([`grants.md`](./grants.md)) for new policies — ACLs are supported
indefinitely but receive no new features.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## Structure

```json
{
  "acls": [
    {
      "action": "accept",
      "src":    ["..."],
      "proto":  "tcp",
      "dst":    ["..."]
    }
  ]
}
```

## Fields

### `action`

Required. The only possible value is `"accept"`. Tailscale is deny-by-default,
so any access must be explicitly granted.

### `src`

Required. Array of source selectors. Each element can be:

| Type | Example | Matches |
|---|---|---|
| Any | `*` | All tailnet devices, approved subnets, `autogroup:shared` |
| User | `alice@example.com` | User's devices |
| Group | `group:engineering` | Group members' devices |
| Tailscale IP | `100.100.123.123` | A single device |
| Subnet CIDR | `192.168.1.0/24` | Any IP in the range |
| Host | `my-host` | IP/CIDR from the `hosts` section |
| Tag | `tag:production` | All tagged devices |
| Autogroup | `autogroup:admin` | Devices of users with that role |
| Autogroup (all) | `autogroup:danger-all` | **All** sources including outside tailnet |

See [`selectors.md`](./selectors.md) for the complete reference.

### `proto`

Optional. Protocol the rule applies to. Without it, the rule applies to all
TCP and UDP traffic.

| Value | Description |
|---|---|
| *(omitted)* | All TCP + UDP |
| `"tcp"` | TCP only |
| `"udp"` | UDP only |
| `"icmp"` | ICMP only |
| `"sctp"` | SCTP only |
| IANA number (1-255) | e.g. `"6"` for TCP, `"17"` for UDP |

Only TCP, UDP, and SCTP support port specifications. Other protocols must
use `*` for ports. If traffic is allowed for a given IP pair, ICMP is also
allowed. Requires Tailscale v1.18.2+.

### `dst`

Required. Array of destination selectors in `host:port` format:

```
host:port
```

**Host** can be:

| Type | Example | Description |
|---|---|---|
| Any | `*` | Any destination |
| User | `alice@example.com` | User's devices |
| Group | `group:engineering` | Group members' devices |
| Tailscale IP | `100.100.123.123` | A single device |
| Subnet CIDR | `192.168.1.0/24` | IP range |
| Host | `my-host` | From `hosts` section |
| Tag | `tag:production` | Tagged devices |
| Internet | `autogroup:internet` | Access via exit nodes |
| Self | `autogroup:self` | Source user's own devices |
| Role | `autogroup:admin`, `autogroup:member`, etc. | Users with that role |
| IP set | `ipset:my-set` | From `ipsets` section |

**Port** can be:

| Type | Example |
|---|---|
| Any | `*` |
| Single | `22` |
| Multiple | `80,443` |
| Range | `1000-2000` |

## Subnet routers and exit nodes

ACLs don't limit discovery of routes. Restrict subnet access by ensuring no
ACL grants access to those routes; use `tests` to enforce.

```json
"tests": [{
  "src": "alice@example.com",
  "accept": ["192.0.2.100:22"],
  "deny":  ["198.51.100.7:22"]
}]
```

Only devices with `autogroup:internet` access can use exit nodes.

## 4via6

When targeting resources behind a 4via6 subnet router, use the **IPv6** CIDR
as the destination, not the IPv4 address. Use `tailscale debug via` to get
the IPv6 CIDR.

## Taildrop

Taildrop permits file sharing between your own devices regardless of ACLs.

## Legacy fields

The legacy field names `users` (replaced by `src`) and `ports` (replaced by
`dst`) still work but are deprecated. Use the modern names.
