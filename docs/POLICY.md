# Policy File Reference

> **Source**: [Tailscale Docs — Syntax reference](https://tailscale.com/docs/reference/syntax/policy-file)

The tailnet policy file is a HuJSON document controlling access, routing,
SSH, and device configuration for your entire tailnet.

For an in-depth breakdown of every section, see the
[`docs/policy/`](./policy/) directory:

## Section files

| Section | File | Covers |
|---|---|---|
| Overview, format, skeleton | [`policy/README.md`](./policy/README.md) | Top-level structure, HuJSON format, deny-by-default |
| Grants | [`policy/grants.md`](./policy/grants.md) | Preferred access control — network + app-layer |
| ACLs | [`policy/acls.md`](./policy/acls.md) | Legacy network-layer rules |
| SSH | [`policy/ssh.md`](./policy/ssh.md) | Tailscale SSH rules |
| Tag owners | [`policy/tag-owners.md`](./policy/tag-owners.md) | Tag assignment permissions |
| Groups | [`policy/groups.md`](./policy/groups.md) | Named user groups |
| Hosts | [`policy/hosts.md`](./policy/hosts.md) | Named IP/CIDR aliases |
| IP sets | [`policy/ipsets.md`](./policy/ipsets.md) | Named IP collections |
| Postures | [`policy/postures.md`](./policy/postures.md) | Device posture conditions |
| Node attributes | [`policy/node-attrs.md`](./policy/node-attrs.md) | Per-device settings |
| Auto approvers | [`policy/auto-approvers.md`](./policy/auto-approvers.md) | Route/exit node auto-approval |
| Tests | [`policy/tests.md`](./policy/tests.md) | Policy assertion tests |
| Network options | [`policy/network-options.md`](./policy/network-options.md) | DERP, IPv4, CGNAT, client port |

## Cross-cutting references

| File | Covers |
|---|---|
| [`policy/autogroups.md`](./policy/autogroups.md) | Complete autogroup table with plan availability |
| [`policy/selectors.md`](./policy/selectors.md) | All source/destination selector types |
| [`policy/users.md`](./policy/users.md) | User identity formats |

## tailscale-manager integration

ACL policies are managed via Terraform's `tailscale_acl` resource. The entire
policy is passed as a single string. See the [README](./policy/README.md#how-tailscale-manager-uses-this)
for details on the backup/restore flow and the `overwrite_existing_content` flag.

## Reference links

| Resource | URL |
|---|---|
| Policy file syntax (source) | https://tailscale.com/docs/reference/syntax/policy-file |
| Grants syntax | https://tailscale.com/docs/reference/syntax/grants |
| ACL examples | https://tailscale.com/docs/reference/examples/acls |
| Grant examples | https://tailscale.com/docs/reference/examples/grants |
| IP sets | https://tailscale.com/docs/features/ip-sets |
| Device posture | https://tailscale.com/docs/features/device-posture |
| DERP servers | https://tailscale.com/docs/reference/derp-servers |
