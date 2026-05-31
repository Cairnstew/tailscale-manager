# OAuth Clients & Trust Credentials

A reference on Tailscale's authentication model for API access — OAuth clients,
trust credentials, scopes, and how `tailscale-manager` uses them.

> **Sources**:
> - [OAuth clients](https://tailscale.com/docs/features/oauth-clients)
> - [Trust credentials](https://tailscale.com/docs/reference/trust-credentials)
> - [Tailscale API](https://tailscale.com/docs/reference/tailscale-api)

---

## Overview

Tailscale offers two mutually exclusive ways to authenticate to the API:

| Method | Secret lifetime | Use case |
|---|---|---|
| **API access token** (legacy) | 1–90 days, user-configured | Manual scripts, short-lived automation |
| **OAuth client** (trust credential) | Client secret is long-lived; access tokens expire in 1 hour | Automated services, CI/CD, Terraform |

`tailscale-manager` uses **OAuth clients** exclusively. The client ID and
secret are passed via `TAILSCALE_OAUTH_CLIENT_ID` and
`TAILSCALE_OAUTH_CLIENT_SECRET`, and the Terraform provider handles token
generation and renewal automatically.

---

## How OAuth works in Tailscale

```
┌──────────────┐    1. POST client_id + client_secret     ┌──────────────┐
│              │  ──────────────────────────────────────►  │              │
│  Application │         https://api.tailscale.com/        │   Tailscale  │
│  (Terraform) │           /api/v2/oauth/token             │   OAuth      │
│              │  ◄──────────────────────────────────────  │   Endpoint   │
└──────────────┘    2. access_token (expires 1 hour)       └──────────────┘
       │
       │  3. GET /api/v2/tailnet/:tailnet/devices
       │     Authorization: Bearer <access_token>
       ▼
┌──────────────┐
│  Tailscale   │
│  API         │
└──────────────┘
```

1. The application presents the client ID + secret to the OAuth token endpoint.
2. Tailscale returns a short-lived API access token (1 hour).
3. The application uses that token for subsequent API calls.
4. Before expiry, a new token is requested — this is handled transparently by
   the Terraform Tailscale provider.

---

## Scopes

Scopes define which API operations a credential can perform. Available scopes
and their granularity are documented in the [trust credentials reference](https://tailscale.com/docs/reference/trust-credentials#scopes).

### Scopes relevant to tailscale-manager

| Scope | Required for | Feature |
|---|---|---|
| `auth_keys` | Create/manage auth keys | Key management (always required) |
| `devices:core:read` | List/read devices | `tailscale-manager devices` |
| `dns` (or `dns:write`) | Read + write DNS settings | DNS nameservers, MagicDNS, split DNS |
| `policy_file` | Read + write ACL policy | ACL management |
| `devices:core` | Manage device tags/lifecycle | Tagged device operations |
| `feature_settings` | Read + write tailnet settings | Tailnet settings management |
| `logs:network` | Read network flow logs | `tailnet_settings.network_flow_logging_on` |

### Legacy scopes

OAuth clients created before November 2024 may use legacy scope names:

| Legacy | Modern equivalent |
|---|---|
| `devices` | `auth_keys` + `devices:core` + `devices:posture_attributes` |
| `devices:read` | `auth_keys:read` + `devices:core:read` |
| `acl` | `policy_file` + `devices:posture_attributes` |
| `dns` | `dns` |
| `routes` | `devices:routes` |
| `logs` | `logs:configuration` |
| `network-logs` | `logs:network` |

---

## Tag ownership

Tags used by auth keys created via OAuth must be owned (directly or indirectly)
by the OAuth client. Two approaches:

### 1. Tag ownership in the policy file

Define `tagOwners` in the tailnet ACL policy so the OAuth client's tags can
assign the target tags:

```json
{
  "tagOwners": {
    "tag:terraform-owner": ["autogroup:admin"],
    "tag:ci":             ["tag:terraform-owner"],
    "tag:server":         ["tag:terraform-owner"]
  }
}
```

Create the OAuth client with tag `tag:terraform-owner`. Now it can create
auth keys tagged `tag:ci` or `tag:server`.

### 2. Direct tag assignment

If the OAuth client was created with `autogroup:admin` (shown as `[]` in the
admin console), it can use any tag in the tailnet. This is the simplest
approach but grants broad tag access.

### Common error

```
Error creating tailnet key: requested tags [tag:ci] are invalid or not permitted (400)
```

The OAuth client does not own `tag:ci`. Fix by adding tag ownership or using
a tag the client already owns.

---

## Tailnet shorthand

API calls can use `-` as the tailnet ID to auto-resolve from the credential:

```
GET https://api.tailscale.com/api/v2/tailnet/-/devices
```

This is why `tailnet = "-"` works in the NixOS module configuration.

---

## Creating an OAuth client

1. Go to [Trust credentials](https://login.tailscale.com/admin/settings/trust-credentials) in the admin console.
2. Select **Credential → OAuth**.
3. Select the required scopes (see table above).
4. If selecting `auth_keys` or `devices:core`, choose the tag(s) the client will own.
5. Copy the **Client ID** and **Client Secret**.
6. Store them in a secure location (e.g. agenix, sops-nix).

The client secret is shown only once — store it immediately.

### Recommended scopes for tailscale-manager

When creating an OAuth client:

- `auth_keys` (write) — required for key creation
- `devices:core` (read) — required for device discovery
- `dns` (write) — required for DNS management (if used)
- `policy_file` (write) — required for ACL management (if used)
- `feature_settings` (write) — required for tailnet settings (if used)

---

## Limitations

| Property | Value |
|---|---|
| Access token lifetime | 1 hour (not configurable) |
| Client secret visibility | Shown once at creation; must be stored securely |
| Tag ownership | Must be configured if using `auth_keys` or `devices:core` scope |
| Revocation | Revoking the OAuth client immediately invalidates all its tokens |
| Node registration | OAuth secret can be used directly with `tailscale up --auth-key` |

---

## Reference links

| Resource | URL |
|---|---|
| OAuth clients (this doc) | https://tailscale.com/docs/features/oauth-clients |
| Trust credentials | https://tailscale.com/docs/reference/trust-credentials |
| Tailscale API | https://tailscale.com/docs/reference/tailscale-api |
| Key prefixes | https://tailscale.com/docs/reference/key-prefixes |
| Tag ownership | https://tailscale.com/docs/features/tags#ownership |
