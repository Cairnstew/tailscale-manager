# Tailnet Policy File — Complete Reference

Everything about the Tailscale tailnet policy file: structure, syntax,
selector types, and capabilities.

> **Source**: [Tailscale Docs — Syntax reference](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## Format

The policy file is **HuJSON** (Human JSON) — a superset of JSON that supports:

- `//` single-line comments
- `/* */` multi-line comments
- Trailing commas in arrays and objects
- Unquoted keys (though JSON-quoted keys are always valid)

Tailscale stores and returns the policy in HuJSON. The admin console editor
and API both accept and return HuJSON.

---

## Complete top-level skeleton

```json
{
  // Access control (prefer grants over ACLs)
  "grants":         [],
  "acls":           [],

  // SSH
  "ssh":            [],

  // Automation
  "autoApprovers":  {},

  // Attributes
  "nodeAttrs":      [],
  "postures":       {},

  // Targets
  "tagOwners":      {},
  "groups":         {},
  "hosts":          {},
  "ipsets":         {},

  // Tests
  "tests":          [],
  "sshTests":       [],

  // Network options
  "derpMap":              {},
  "disableIPv4":          false,
  "randomizeClientPort":  false,
  "oneCGNATRoute":        ""
}
```

All top-level keys are optional. An empty policy file `{}` grants no access
(deny-by-default) and sets no configuration.

---

## Section index

| Section | File | Type | Purpose |
|---|---|---|---|
| Grants | [`grants.md`](./grants.md) | Access control | **Preferred.** Unified network + app-layer access with routing. |
| ACLs | [`acls.md`](./acls.md) | Access control | Legacy network-layer rules. Still supported, no new features. |
| SSH | [`ssh.md`](./ssh.md) | Access control | Tailscale SSH rules. |
| Tag owners | [`tag-owners.md`](./tag-owners.md) | Targets | Who can assign tags to devices. |
| Groups | [`groups.md`](./groups.md) | Targets | Named sets of users. |
| Hosts | [`hosts.md`](./hosts.md) | Targets | Named IP/CIDR aliases. |
| IP sets | [`ipsets.md`](./ipsets.md) | Targets | Named collections of IP ranges. |
| Postures | [`postures.md`](./postures.md) | Attributes | Device posture conditions for access rules. |
| Node attributes | [`node-attrs.md`](./node-attrs.md) | Attributes | Per-device settings (NextDNS, funnel, app connectors, etc.). In the NixOS module, use `policy.appConnectors` for app connectors — it synthesizes the correct `nodeAttrs` entry. |
| Auto approvers | [`auto-approvers.md`](./auto-approvers.md) | Automation | Who can bypass approval for routes/exit nodes. |
| Tests | [`tests.md`](./tests.md) | Tests | Assertions about ACLs/grants that must pass. |
| Network options | [`network-options.md`](./network-options.md) | Options | DERP, IPv4, CGNAT, client port settings. |

## Cross-cutting references

| Reference | File | Covers |
|---|---|---|
| Autogroups table | [`autogroups.md`](./autogroups.md) | All `autogroup:*` selectors used across ACLs, grants, SSH, tag owners, auto-approvers |
| Selectors | [`selectors.md`](./selectors.md) | Complete reference of every source/destination selector type |
| Users | [`users.md`](./users.md) | User identity formats (email, GitHub, Passkey) |

---

## Deny-by-default

Tailscale grants no access unless explicitly allowed. The only `action`
in ACLs is `accept`; grants have an implied `accept`.

---

## How tailscale-manager uses this

ACL policies are managed via Terraform's `tailscale_acl` resource:

```json
{
  "resource": {
    "tailscale_acl": {
      "tailnet_policy": {
        "acl": "<full policy file content as string>",
        "overwrite_existing_content": true
      }
    }
  }
}
```

The entire policy is stored as a single string in the `acl` field. `tailscale-manager`
backs up the current policy before every apply and restores it on failure.

**Important**: `tailscale_acl` manages the entire policy file. Enabling ACL
management means all policy configuration must be declared in `acl_policy`.
Admin-console edits will be overwritten on the next apply.

---

## Reference links

| Resource | URL |
|---|---|
| Source (this doc) | https://tailscale.com/docs/reference/syntax/policy-file |
| Grants syntax | https://tailscale.com/docs/reference/syntax/grants |
| ACL examples | https://tailscale.com/docs/reference/examples/acls |
| Grant examples | https://tailscale.com/docs/reference/examples/grants |
| IP sets | https://tailscale.com/docs/features/ip-sets |
| Device posture | https://tailscale.com/docs/features/device-posture |
| App connectors | https://tailscale.com/docs/features/app-connectors |
| DERP servers | https://tailscale.com/docs/reference/derp-servers |
| Visual editor | https://tailscale.com/docs/features/visual-acl-editor |
