# Network Policy Options

Rarely-used network-wide settings in the tailnet policy file.

> **Source**: [Tailscale Docs — Policy file syntax](https://tailscale.com/docs/reference/syntax/policy-file)
> Last validated: Apr 8, 2026

---

## Structure

```json
{
  "derpMap":              {},
  "disableIPv4":          false,
  "randomizeClientPort":  false,
  "OneCGNATRoute":        ""
}
```

---

## `derpMap`

Custom DERP relay servers. Use to add your own relays or disable Tailscale's.

```json
{
  "derpMap": {
    "omitDefaultRegions": true,
    "regions": {
      "900": {
        "regionID":   900,
        "regionCode": "my-region",
        "regionName": "My Custom Region",
        "nodes": [
          {
            "name":     "1",
            "regionID": 900,
            "hostName": "derp.example.com",
            "stunPort": 3478,
            "stunOnly": false
          }
        ]
      }
    }
  }
}
```

| Field | Type | Description |
|---|---|---|
| `omitDefaultRegions` | bool | Set to `true` to disable Tailscale-provided DERP servers. |
| `regions` | object | Map of region ID to region config. |

Useful for air-gapped deployments or compliance requirements.

---

## `disableIPv4`

```json
{ "disableIPv4": true }
```

- Stops assigning IPv4 Tailscale addresses (100.x.y.z).
- All devices get exclusively IPv6 addresses.
- **Recommended alternative**: use `disable-ipv4` node attribute per-device.

Intended for networks with pre-existing conflicts with `100.64.0.0/10`
(CGNAT range).

---

## `randomizeClientPort`

```json
{ "randomizeClientPort": true }
```

- Makes devices use a **random port** for WireGuard traffic instead of the
  default static port `41641`.
- Only use as a workaround for firewall issues after consulting Tailscale
  Support.

---

## `OneCGNATRoute`

Controls how Tailscale clients generate CGNAT routes.

| Value | Behavior |
|---|---|
| `""` (default) | Per-platform heuristics: fine-grained /32 on most platforms; one `100.64/10` route on macOS. |
| `"mac-always"` | macOS always uses one `100.64/10` route. |
| `"mac-never"` | macOS always uses fine-grained /32 routes. |

The `100.64/10` route avoids routing table churn (which disrupts
Chromium-based browsers on macOS). Won't be used if other interfaces
already route that range.
