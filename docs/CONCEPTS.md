# Tailscale Concepts & Terminology

Key Tailscale concepts relevant to `tailscale-manager` and tailnet
administration.

> **Source**: [Tailscale Docs — Terminology and concepts](https://tailscale.com/docs/reference/glossary)

---

## Network architecture

| Term | Definition |
|---|---|
| **Tailnet** | Your Tailscale network — an interconnected collection of users, devices, and resources. Has a control plane and a data plane. |
| **Overlay network** | A virtual network built on top of the underlay. Tailscale forms an overlay where each node has a stable identity and IP address regardless of underlay changes. |
| **Underlay network** | The physical IP network Tailscale runs over (Wi-Fi, LAN, cloud networking, etc.). |
| **Coordination server** | Central server that maintains connections to all devices, manages encryption keys, and pushes policy changes. Part of the control plane — never relays traffic (no bottleneck). |
| **DERP** | Designated Encrypted Relay for Packets. Globally distributed relay servers that act as a fallback when direct connections fail (NAT traversal failure). |
| **NAT traversal** | Technique to connect devices across firewalls and NAT gateways. Tailscale uses techniques like STUN, UPnP, and DERP relay to establish direct connections. |
| **Mesh topology** | Every device talks directly to every other device (no hub-and-spoke). Direct connections are established via NAT traversal; DERP relays are used only when necessary. |

## Devices and nodes

| Term | Definition |
|---|---|
| **Device** | A physical or virtual machine running the Tailscale client. |
| **Node** | The combination of a user + device. A device authenticated by one user is one node; if a second user authenticates on the same device, it's a different node. |
| **Peer** | Another node your device communicates with. |
| **Tailscale IP** | A unique `100.x.y.z` (IPv4) or `fd7a:115c:a1e0::/48` (IPv6) address assigned to each device. Stable across network changes (Wi-Fi → cellular, etc.). |
| **Device key** | A unique public/private key pair per device. More than one user can use a device, but each device has exactly one key pair. |
| **Key expiry** | Automatic expiry and rotation of cryptographic keys. Can be disabled for long-lived devices from the admin console. |

## Access control

| Term | Definition |
|---|---|
| **ACL** | Access control list. Rules in the tailnet policy file that control which sources can reach which destinations. Deny-by-default. |
| **Grant** | Next-generation ACL syntax with app-layer capabilities. Preferred over traditional ACLs for new policies. |
| **Tailnet policy file** | HuJSON file containing all ACL rules, SSH rules, tag ownership, groups, and other configuration. The single source of truth for access policy. |
| **Tag** | A `tag:<name>` identifier that groups devices by function (e.g. `tag:server`, `tag:ci`). Tags are not users — they're identities for services and infrastructure. Tags must be declared in `tagOwners` before use. |
| **Group** | A `group:<name>` set of users (e.g. `group:engineering`). Can be defined in the policy file or synced from an identity provider via SCIM. |
| **Autogroup** | Built-in dynamic groups like `autogroup:admin`, `autogroup:member`, etc. Automatically include users with specific roles or properties. |
| **Host** | A named alias for an IP address or CIDR range in the policy file. |
| **IP set** | A named collection of IP addresses, CIDRs, hosts, and other IP sets for use in access rules. |
| **tagOwners** | Policy section declaring which users/groups/tags can assign each tag. `[]` is shorthand for `["autogroup:admin"]`. |

## Auth keys

| Term | Definition |
|---|---|
| **Auth key** | A pre-authentication key that lets a device join a tailnet without interactive login. Can be reusable, ephemeral, and pre-authorized. |
| **OAuth client** | A trust credential that generates short-lived API access tokens. Used by `tailscale-manager` to authenticate to the Tailscale API via the Terraform provider. |
| **Pre-authorized** | An auth key that skips the device approval flow. Devices join without requiring an admin to approve them. |
| **Ephemeral** | An auth key that creates a node which is removed from the tailnet when it disconnects. Useful for CI/CD runners, short-lived VMs. |
| **recreate_if_invalid** | Terraform attribute that automatically replaces an expired/revoked key on the next apply. This is the rotation mechanism in `tailscale-manager`. |

## DNS

| Term | Definition |
|---|---|
| **MagicDNS** | Automatic DNS registration: every device gets a `<hostname>.tailnet-name.ts.net` domain. No manual DNS configuration needed. |
| **Global nameservers** | DNS servers used by all tailnet devices for external name resolution. |
| **Split DNS** | Per-domain DNS: specific domains are resolved by specific nameservers. |
| **Tailscale DNS** | The DNS resolver built into the Tailscale client. Handles MagicDNS, custom nameservers, and split DNS. |

## Features

| Term | Definition |
|---|---|
| **Subnet router** | A device that advertises routes to physical subnets, making them accessible to the entire tailnet. |
| **Exit node** | A device through which other nodes route internet-bound traffic (full tunnel mode for internet). |
| **App connector** | A device that routes traffic to specified domains or IP ranges (for connecting to SaaS, private apps behind a connector). |
| **Tailscale SSH** | SSH managed by the tailnet policy. Keys are distributed via the coordination server — no SSH keys to manage manually. |
| **Taildrop** | Peer-to-peer file transfer between devices in the same tailnet. Always end-to-end encrypted. |
| **Tailscale Funnel** | Expose a local service to the internet through Tailscale's infrastructure. |
| **Tailscale Serve** | Expose a local service to the tailnet as an HTTP reverse proxy. |

## Identity and administration

| Term | Definition |
|---|---|
| **Admin console** | Web UI at https://login.tailscale.com/admin for managing the tailnet. |
| **Identity provider (IdP)** | External service for user authentication (Google, Okta, Microsoft, GitHub, etc.). Tailscale is not an IdP. |
| **SSO** | Single sign-on. Users authenticate through the tailnet's configured identity provider. |
| **SCIM** | System for Cross-domain Identity Management. Used to sync users and groups from an IdP into Tailscale. |
| **User roles** | Owner, Admin, Network admin, IT admin, Billing admin, Auditor. Each role has different levels of access to the admin console and API. |

## Key prefixes

Tailscale API keys and secrets use identifiable prefixes:

| Prefix | Type |
|---|---|
| `tskey-api-` | API access token (legacy, user-generated) |
| `tskey-client-` | OAuth client secret |
| `tskey-auth-` | Auth key (pre-authentication key) |

---

## Reference links

| Resource | URL |
|---|---|
| Terminology (this doc) | https://tailscale.com/docs/reference/glossary |
| Tailscale architecture | https://tailscale.com/docs/concepts/control-data-planes |
| Tailscale IP addresses | https://tailscale.com/docs/concepts/ip-and-dns-addresses |
| DNS in Tailscale | https://tailscale.com/docs/reference/dns-in-tailscale |
| Tags | https://tailscale.com/docs/features/tags |
| Auth keys | https://tailscale.com/docs/features/access-control/auth-keys |
| Key prefixes | https://tailscale.com/docs/reference/key-prefixes |
| User roles | https://tailscale.com/docs/reference/user-roles |
| Tailnet name | https://tailscale.com/docs/concepts/tailnet-name |
