# Tag Owners

Controls **who can assign which tags to devices**. Every tag used in the
tailnet must be declared here before use.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## Structure

```json
{
  "tagOwners": {
    "tag:webserver":      ["group:engineering"],
    "tag:secure-server":  ["group:security-admins", "president@example.com"],
    "tag:corp":           ["autogroup:member"],
    "tag:monitoring":     []
  }
}
```

## Rules

| Rule | Detail |
|---|---|
| Prefix | Every tag name must start with `tag:`. |
| Owners | Can be users, groups, autogroups, or other tags (tag chaining). |
| `[]` shorthand | Equivalent to `["autogroup:admin"]`. |
| Admin access | `autogroup:admin` and `autogroup:network-admin` can assign **all** tags implicitly. |

## Owner types

| Type | Example | Description |
|---|---|---|
| User | `"alice@example.com"` | A specific user |
| Group | `"group:engineering"` | All group members |
| Autogroup | `"autogroup:admin"` | Users with that role |
| Tag | `"tag:owner-tag"` | Devices with that tag can assign the target tag (tag chaining) |
| Shorthand | `[]` | Same as `["autogroup:admin"]` |

## Tag chaining

A tag can own another tag, creating a delegation chain:

```json
{
  "tagOwners": {
    "tag:terraform-owner": ["autogroup:admin"],
    "tag:ci":              ["tag:terraform-owner"],
    "tag:server":          ["tag:terraform-owner"]
  }
}
```

Devices tagged `tag:terraform-owner` can assign `tag:ci` and `tag:server`
to other devices.

## OAuth client tag ownership

OAuth clients that create auth keys with tags must own those tags (directly
or through a chain). If the OAuth client's tag is `tag:terraform-owner`, auth
keys can be created with `tag:ci` or `tag:server` per the chain above.

Common error:

```
Error creating tailnet key: requested tags [tag:ci] are invalid or not permitted (400)
```

## Examples

### Admin-only tags

```json
{
  "tagOwners": {
    "tag:sensitive": []
  }
}
```

### Delegated tag management

```json
{
  "tagOwners": {
    "tag:devops":          ["group:platform-eng"],
    "tag:ci-runner":       ["tag:devops"],
    "tag:staging":         ["tag:devops"],
    "tag:prod":            ["autogroup:admin"],
    "tag:corp-device":     ["autogroup:member"]
  }
}
```
