# Tailscale API Reference

Key API endpoints, authentication patterns, and integration notes relevant
to `tailscale-manager` and automated tailnet management.

> **Source**: [Tailscale API](https://tailscale.com/docs/reference/tailscale-api)
> Interactive docs: https://api.tailscale.com/api/v2/doc

---

## Authentication

Two methods:

### 1. API access token (legacy)

```
Authorization: Bearer <tskey-api-xxxxxxxxxx>
```

Generated from the [Keys page](https://login.tailscale.com/admin/settings/keys).
Expires in 1–90 days. Full tailnet access (no scope restriction).

### 2. OAuth client (trust credential) — recommended

```
# 1. Get a short-lived access token
POST https://api.tailscale.com/api/v2/oauth/token
Content-Type: application/x-www-form-urlencoded

client_id=<id>&client_secret=<secret>&scope=<scopes>

# 2. Use the token
GET /api/v2/tailnet/-/devices
Authorization: Bearer <access_token>
```

- Access token expires in **1 hour**.
- Scopes restrict which endpoints the token can access.
- `tskey-client-` prefix identifies OAuth client secrets.

`tailscale-manager` uses OAuth exclusively — the Terraform provider handles
token lifecycle transparently.

---

## Base URL

```
https://api.tailscale.com/api/v2/
```

Tailnet ID can be `-` (auto-resolves from the credential):

```
GET /api/v2/tailnet/-/devices
```

---

## Key endpoints

### Auth keys

| Method | Endpoint | Description | Scope required |
|---|---|---|---|
| `GET` | `/tailnet/:tailnet/keys` | List all auth keys | `auth_keys:read` |
| `POST` | `/tailnet/:tailnet/keys` | Create an auth key | `auth_keys` |
| `GET` | `/tailnet/:tailnet/keys/:keyId` | Get a specific auth key | `auth_keys:read` |
| `DELETE` | `/tailnet/:tailnet/keys/:keyId` | Revoke an auth key | `auth_keys` |

**POST body** (create):
```json
{
  "capabilities": {
    "devices": {
      "create": {
        "reusable": true,
        "ephemeral": false,
        "preauthorized": true,
        "tags": ["tag:ci"]
      }
    }
  },
  "expirySeconds": 7776000
}
```

`expirySeconds` max: 7776000 (90 days). `expirySeconds` can be set to `0`
for keys that do not expire. The OAuth client's tag ownership determines
which tags are valid.

### Devices

| Method | Endpoint | Description | Scope required |
|---|---|---|---|
| `GET` | `/tailnet/:tailnet/devices` | List all devices | `devices:core:read` |
| `GET` | `/device/:deviceId` | Get device details | `devices:core:read` |
| `POST` | `/device/:deviceId/tags` | Update device tags | `devices:core` |
| `POST` | `/device/:deviceId/authorized` | Approve a device | `devices:core` |
| `DELETE` | `/device/:deviceId` | Remove a device | `devices:core` |

### DNS

| Method | Endpoint | Description | Scope required |
|---|---|---|---|
| `GET` | `/tailnet/:tailnet/dns/nameservers` | List global nameservers | `dns:read` |
| `POST` | `/tailnet/:tailnet/dns/nameservers` | Set global nameservers | `dns` |
| `GET` | `/tailnet/:tailnet/dns/preferences` | Get DNS preferences | `dns:read` |
| `POST` | `/tailnet/:tailnet/dns/preferences` | Set DNS preferences | `dns` |
| `GET` | `/tailnet/:tailnet/dns/searchpaths` | List search paths | `dns:read` |
| `POST` | `/tailnet/:tailnet/dns/searchpaths` | Set search paths | `dns` |
| `GET` | `/tailnet/:tailnet/dns/split-dns` | List split DNS config | `dns:read` |
| `PATCH` | `/tailnet/:tailnet/dns/split-dns` | Update split DNS config | `dns` |

### ACL / policy file

| Method | Endpoint | Description | Scope required |
|---|---|---|---|
| `GET` | `/tailnet/:tailnet/acl` | Get the current policy file | `policy_file:read` |
| `POST` | `/tailnet/:tailnet/acl` | Set the policy file | `policy_file` |
| `POST` | `/tailnet/:tailnet/acl/preview` | Preview rule effects | `policy_file:read` |
| `POST` | `/tailnet/:tailnet/acl/validate` | Validate a policy file | `policy_file:read` |

**POST body** (set ACL):
```json
{
  "acl": { "acls": [{ "action": "accept", "src": ["*"], "dst": ["*:*"] }] }
}
```

This replaces the entire policy. The `overwriteExistingContent` query
parameter must be set to `true` when overwriting a non-default policy.

### Tailnet settings

| Method | Endpoint | Description | Scope required |
|---|---|---|---|
| `GET` | `/tailnet/:tailnet/settings` | Get tailnet settings | `feature_settings:read` |
| `PATCH` | `/tailnet/:tailnet/settings` | Update tailnet settings | `feature_settings` |

Settings include: `devicesApprovalOn`, `devicesAutoUpdatesOn`,
`devicesKeyDurationDays`, `usersApprovalOn`, `aclsExternallyManagedOn`,
`postureIdentityCollectionOn`, `httpsEnabled`, `regionalRoutingOn`,
`networkFlowLoggingOn`, `usersRoleAllowedToJoinExternalTailnet`.

### Users

| Method | Endpoint | Description | Scope required |
|---|---|---|---|
| `GET` | `/tailnet/:tailnet/users` | List users | `users:read` |
| `GET` | `/user/:userId` | Get user details | `users:read` |
| `POST` | `/user/:userId/role` | Change user role | `users` |
| `POST` | `/user/:userId/approve` | Approve a user | `users` |
| `POST` | `/user/:userId/suspend` | Suspend a user | `users` |

---

## Scope-to-endpoint mapping

Each OAuth scope grants access to a specific set of endpoints:

| Scope | Accessible endpoints |
|---|---|
| `all` | All endpoints (unrestricted) |
| `auth_keys` | Auth key CRUD (POST/DELETE) |
| `auth_keys:read` | Auth key read (GET) |
| `devices:core` | Device management + tagging |
| `devices:core:read` | Device listing and details |
| `dns` | DNS read + write |
| `dns:read` | DNS read only |
| `policy_file` | ACL read + write |
| `policy_file:read` | ACL read, preview, validate |
| `feature_settings` | Tailnet settings read + write |
| `feature_settings:read` | Tailnet settings read only |
| `users` | User management |
| `users:read` | User read only |
| `devices:routes` | Subnet/exit node routes CRUD |
| `logs:configuration` | Configuration audit logs |
| `logs:network` | Network flow logs |

See the [full scope table](https://tailscale.com/docs/reference/trust-credentials#scopes)
for the complete list.

---

## Rate limiting

Tailscale API rate limits are applied per tailnet. Limits are not publicly
documented but generally sufficient for automation use cases. The Terraform
provider handles retries and backoff automatically.

---

## Terraform provider mapping

`tailscale-manager` manages these API resources through the
[Tailscale Terraform provider](https://registry.terraform.io/providers/tailscale/tailscale):

| Terraform resource | API endpoint(s) | Purpose |
|---|---|---|
| `tailscale_tailnet_key` | `POST/DELETE /keys` | Auth key management |
| `data.tailscale_devices` | `GET /devices` | Device discovery |
| `tailscale_dns_nameservers` | `GET/POST /dns/nameservers` | Global DNS |
| `tailscale_dns_preferences` | `GET/POST /dns/preferences` | MagicDNS |
| `tailscale_dns_split_nameservers` | `GET/PATCH /dns/split-dns` | Split DNS |
| `tailscale_tailnet_settings` | `GET/PATCH /settings` | Tailnet settings |
| `tailscale_acl` | `GET/POST /acl` | ACL policy |

---

## Reference links

| Resource | URL |
|---|---|
| Tailscale API (this doc) | https://tailscale.com/docs/reference/tailscale-api |
| Interactive API docs | https://api.tailscale.com/api/v2/doc |
| OAuth clients | https://tailscale.com/docs/features/oauth-clients |
| Trust credentials | https://tailscale.com/docs/reference/trust-credentials |
| Terraform provider | https://registry.terraform.io/providers/tailscale/tailscale |
| Key prefixes | https://tailscale.com/docs/reference/key-prefixes |
