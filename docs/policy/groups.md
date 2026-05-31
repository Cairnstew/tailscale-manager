# Groups

Named sets of users for use in access rules, SSH rules, tag owners, and
auto-approvers.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## Structure

```json
{
  "groups": {
    "group:engineering": [
      "dave@example.com",
      "laura@example.com"
    ],
    "group:sales": [
      "brad@example.com",
      "alice@example.com"
    ]
  }
}
```

## Rules

| Rule | Detail |
|---|---|
| Prefix | Must start with `group:`. |
| Members | Specified by full login email/identifier. |
| Nesting | Groups **cannot** contain other groups. |
| Plan limit | Group count depends on plan (see [Pricing](https://tailscale.com/pricing)). |

## Synced groups (SCIM)

Groups can be synced from an identity provider via SCIM. The format is:

```
group:name@domain
```

Example:

```json
{
  "grants": [{
    "src": ["group:security-team@example.com"],
    "dst": ["tag:logging"],
    "ip":  ["*"]
  }],
  "tagOwners": {
    "tag:logging": ["group:security-team@example.com"]
  }
}
```

Synced groups are read-only in the policy file — they are managed by the
identity provider.

## Editing membership

Group membership can be edited:
1. **In the policy file** — edit the `groups` section directly.
2. **Admin console** — Users page → user menu → Edit group membership.

Requires Owner, Admin, or Network admin role.

## Examples

### Role-based groups

```json
{
  "groups": {
    "group:developers":  ["alice@example.com", "bob@example.com"],
    "group:devops":      ["carol@example.com"],
    "group:security":    ["dave@example.com"]
  },
  "grants": [
    { "src": ["group:developers"], "dst": ["tag:staging"], "ip": ["*"] },
    { "src": ["group:devops"],     "dst": ["tag:prod"],    "ip": ["*"] },
    { "src": ["group:security"],   "dst": ["tag:prod"],    "ip": ["tcp:22"] }
  ]
}
```
