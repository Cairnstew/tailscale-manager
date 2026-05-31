# Users

User identity formats used throughout the policy file.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## User formats

| Format | When to use | Example |
|---|---|---|
| `user@domain` | User signs in via email IdP | `alice@example.com` |
| `user@github` | User signs in with GitHub | `alice@github` |
| `user@passkey` | User signs in with Passkey | `alice@passkey` |

Each format can appear in:

- `src` and `dst` fields of ACLs/grants
- Group membership lists
- `tagOwners` owner lists
- `autoApprovers` approver lists
- `tests` src field
- SSH rule src/dst fields

## Domain wildcards

`user:*@<domain>` selects all users with login emails in a given domain.
See [`autogroups.md`](./autogroups.md) for restrictions.
