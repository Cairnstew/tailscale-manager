# Autogroups Quick Reference

All built-in autogroup selectors available in the policy file, where they can
be used, and which plans support them.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## Complete autogroup table

| Autogroup | Use as | Description | Plan |
|---|---|---|---|
| `autogroup:internet` | dst | Access internet via exit nodes | All |
| `autogroup:self` | dst | Source user's own devices (not for tags) | All |
| `autogroup:owner` | src, dst, tagOwner, autoApprover | Tailnet owner | All |
| `autogroup:admin` | src, dst, tagOwner, autoApprover | Admin role | All |
| `autogroup:member` | src, dst, tagOwner, autoApprover | All direct tailnet members (not shared users) | All |
| `autogroup:tagged` | src, dst | All tagged devices | All |
| `autogroup:shared` | src | Users who accepted a sharing invite | All |
| `autogroup:nonroot` | SSH users | Any user except root | All |
| `autogroup:danger-all` | src | **All** sources (extremely permissive) | All |
| `autogroup:network-admin` | src, dst, tagOwner, autoApprover | Network admin role | Standard+ |
| `autogroup:it-admin` | src, dst, tagOwner, autoApprover | IT admin role | Standard+ |
| `autogroup:billing-admin` | src, dst, tagOwner, autoApprover | Billing admin role | Standard+ |
| `autogroup:auditor` | src, dst, tagOwner, autoApprover | Auditor role | Standard+ |
| `localpart:*@<domain>` | SSH users | SSH user matching email local-part | Premium, Enterprise |
| `user:*@<domain>` | src, dst, tagOwner, autoApprover | Users with login in the given domain | All |

## Domain-based autogroups

```
user:*@example.com
localpart:*@example.com
```

- Include users who are both tailnet members and have login in the domain.
- **Cannot** use known shared domains (e.g. `gmail.com`).
- **Must** list domain aliases explicitly.
- `*` is a full wildcard, not arbitrary — `user:b*b@example.com` does not work.
- Domain autogroups do not apply to external invited users.

## Legacy compatibility

- `autogroup:members` (plural) still works but is deprecated — use `autogroup:member`.
- Cannot use both `autogroup:member` and `autogroup:members` in the same policy.

## `autogroup:self` notes

- Only applies to **user-owned** devices, not tagged devices.
- Cannot combine `autogroup:self` with `autogroup:tagged`.

## `autogroup:danger-all` notes

- Includes sources **outside** your tailnet.
- Use with extreme caution — effectively disables access control for those sources.
