# Tailscale SSH

Controls who can SSH into which devices, and as which user.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## Requirements

For an SSH connection to succeed, **both** must be true:

1. A network-layer rule allows traffic from source to destination on **port 22**
   (via ACL or grant).
2. An SSH rule allows the connection with the given SSH user.

---

## Structure

```json
{
  "ssh": [
    {
      "action":      "accept",
      "src":         ["..."],
      "dst":         ["..."],
      "users":       ["..."],
      "checkPeriod": "12h",
      "acceptEnv":   ["..."],
      "srcPosture":  ["..."],
      "srcPostureAttrs": {}
    }
  ]
}
```

## Fields

### `action`

| Value | Description |
|---|---|
| `"accept"` | Accept the connection immediately. |
| `"check"` | Require periodic re-authentication per `checkPeriod`. |

### `src`

Sources that can initiate SSH. Valid selectors:

- `autogroup:member`
- `autogroup:admin`, `autogroup:owner`, etc.
- `group:<name>`
- `tag:<name>`
- `user:*@<domain>`
- A specific user email
- `autogroup:tagged`

Cannot use `*`, IP addresses, or hostnames in `src`.

### `dst`

Destinations that accept SSH. Valid selectors:

- `tag:<name>` — tagged devices
- `autogroup:self` — the source user's own devices (only if src is a user/group)
- A single named user — only if src is the same user

Cannot use `*`, IP addresses, or hostnames. Port is always 22 (not
configurable).

### `users`

SSH usernames on the destination host that are allowed.

| Selector | Description | Plan |
|---|---|---|
| `autogroup:nonroot` | Any non-root user | All |
| `root` | Root user | All |
| `alice` (literal) | A specific username | All |
| `localpart:*@<domain>` | SSH user matching the email local-part | Premium, Enterprise |
| *(omitted)* | Defaults to the connecting user's local username | All |

### `checkPeriod`

Only for `"check"` action. Time between re-authentication checks.

- Format: `"90m"` (minutes) or `"20h"` (hours)
- Min: `"1m"`, Max: `"168h"` (7 days)
- Default: `"12h"`
- Special: `"always"` — check every connection (may break automation)

### `acceptEnv`

Allowlist of environment variable names clients can forward via `SendEnv` /
`SetEnv`. Requires Tailscale v1.76.0+ on the host.

Supports `*` (any sequence) and `?` (single char) wildcards.

| Pattern | Permitted | Rejected |
|---|---|---|
| `*` | `FOO_A`, `FOO_B`, `BAZ` | — |
| `FOO_*` | `FOO_A`, `FOO_B`, `FOO_OTHER` | `BAZ` |
| `FOO_?` | `FOO_A`, `FOO_B` | `FOO_OTHER`, `BAZ` |
| `FOO_A` | `FOO_A` | `FOO_B`, `BAZ` |

### `srcPosture`

Array of posture conditions to restrict the source device. See
[`postures.md`](./postures.md).

---

## Evaluation order

Tailscale evaluates SSH rules most-restrictive first:

1. `check` policies
2. `accept` policies

If a user matches both a `check` rule and an `accept` rule, the `check` rule
wins.

---

## Default SSH policy

An unmodified tailnet has:

```json
{
  "ssh": [{
    "action": "check",
    "src":    ["autogroup:member"],
    "dst":    ["autogroup:self"],
    "users":  ["autogroup:nonroot", "root"]
  }]
}
```

---

## Allowed connection patterns

| Src | Dst | Check mode? |
|---|---|---|
| User | Own devices (`autogroup:self`) | Yes |
| User/group | Tagged device | Yes |
| Tagged device | Tagged device | No (must be `accept`) |
| User | Shared tagged device | Yes |

---

## Examples

### Users can SSH to their own devices (non-root)

```json
{
  "ssh": [{
    "action": "accept",
    "src":    ["autogroup:member"],
    "dst":    ["autogroup:self"],
    "users":  ["autogroup:nonroot"]
  }]
}
```

### SRE team can SSH as ubuntu/root to production

```json
{
  "ssh": [{
    "action": "accept",
    "src":    ["group:sre"],
    "dst":    ["tag:prod"],
    "users":  ["ubuntu", "root"]
  }]
}
```

### Domain-matched SSH users

```json
{
  "ssh": [{
    "action": "accept",
    "src":    ["user:*@example.com"],
    "dst":    ["tag:prod"],
    "users":  ["localpart:*@example.com"]
  }]
}
```
