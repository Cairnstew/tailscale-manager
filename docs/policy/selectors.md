# Selectors Reference

Every selector type available across ACLs, grants, and SSH rules.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## Source selectors (for `src`)

| Type | Example | ACL | Grant | SSH | Description |
|---|---|---|---|---|---|
| Any | `*` | ✅ | ✅ | ❌ | All tailnet traffic + approved subnets + shared |
| User | `alice@example.com` | ✅ | ✅ | ✅ | A specific user's devices |
| Group | `group:engineering` | ✅ | ✅ | ✅ | All group members |
| Tag | `tag:production` | ✅ | ✅ | ✅ | Tagged devices |
| Tailscale IP | `100.100.123.123` | ✅ | ✅ | ❌ | Single device |
| Subnet CIDR | `192.168.1.0/24` | ✅ | ✅ | ❌ | IP range |
| Host alias | `my-host` | ✅ | ✅ | ❌ | From `hosts` section |
| Autogroup (role) | `autogroup:admin` | ✅ | ✅ | ✅ | Users with that role |
| Autogroup (all) | `autogroup:danger-all` | ✅ | ✅ | ❌ | **All** sources |
| Autogroup (tagged) | `autogroup:tagged` | ❌ | ✅ | ✅ | All tagged devices |
| Autogroup (shared) | `autogroup:shared` | ✅ | ✅ | ❌ | Users who accepted share |
| Domain wildcard | `user:*@example.com` | ❌ | ✅ | ✅ | Users in domain |
| IP set | `ipset:prod` | ❌ | ✅ | ❌ | Named IP collection |

## Destination selectors (for `dst`)

| Type | Example | ACL | Grant | SSH | Description |
|---|---|---|---|---|---|
| Any | `*` | ✅ | ✅ | ❌ | Any destination |
| User | `alice@example.com` | ✅ | ✅ | ✅ | User's devices |
| Group | `group:engineering` | ✅ | ✅ | ❌ | Group members' devices |
| Tag | `tag:production` | ✅ | ✅ | ✅ | Tagged devices |
| Tailscale IP | `100.100.123.123` | ✅ | ✅ | ❌ | Single device |
| Subnet CIDR | `192.168.1.0/24` | ✅ | ✅ | ❌ | IP range |
| Host alias | `my-host` | ✅ | ✅ | ❌ | From `hosts` section |
| Self | `autogroup:self` | ✅ | ✅ | ✅ | Source user's own devices |
| Internet | `autogroup:internet` | ✅ | ✅ | ❌ | Access via exit nodes |
| Role | `autogroup:admin` | ✅ | ✅ | ❌ | Devices of users with role |
| Member | `autogroup:member` | ✅ | ✅ | ❌ | Direct tailnet members |
| Tagged | `autogroup:tagged` | ❌ | ✅ | ❌ | All tagged devices |
| IP set | `ipset:prod` | ❌ | ✅ | ❌ | Named IP collection |
| Service | `svc:my-service` | ❌ | ✅ | ❌ | Tailscale Service |
| Domain wildcard | `user:*@example.com` | ❌ | ✅ | ❌ | Users in domain |

## SSH source/destination notes

- SSH `src`: can be user, group, tag, autogroup, or `user:*@<domain>`.
  Cannot use `*`, IPs, or hostnames.
- SSH `dst`: can be tag, `autogroup:self`, or a single named user
  (if src is the same user). Cannot use `*`, IPs, or hostnames.
- Port is always 22 — not configurable in SSH rules.

## Test selectors

For `tests` and `sshTests`:

- `src` in tests: user, group, tag, or host (no `*`, no CIDR).
- `accept`/`deny` destinations: Tailscale IP, host, user, group, tag, or service.
  No CIDR, no `*`.

## Port formats (ACL `dst`)

```
host:*         # any port
host:22        # single port
host:80,443    # multiple ports
host:1000-2000 # range
```
