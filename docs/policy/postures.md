# Postures

Device posture conditions that can be applied to sources in access rules,
restricting access to devices meeting specific security criteria.

> **Source**: [Tailscale Docs — Device posture](https://tailscale.com/docs/features/device-posture)
> Last validated: Apr 8, 2026

---

## Structure

```json
{
  "postures": {
    "posture:latestMac": [
      "node:os IN ['macos']",
      "node:tsReleaseTrack == 'stable'",
      "node:tsVersion >= '1.40'"
    ],
    "posture:windowsSecured": [
      "node:os IN ['windows']",
      "node:tsReleaseTrack == 'stable'",
      "node:diskEncryption == true"
    ]
  }
}
```

## Rules

| Rule | Detail |
|---|---|
| Prefix | Must start with `posture:`. |
| Value | Array of string conditions. |
| Conditions | Each condition is a comparison expression against a posture attribute. |

## Usage in ACLs

```json
{
  "acls": [
    {
      "action":      "accept",
      "src":         ["group:engineering"],
      "srcPosture":  ["posture:latestMac"],
      "dst":         ["tag:prod:22"]
    }
  ]
}
```

## Usage in grants

```json
{
  "grants": [
    {
      "src":        ["group:engineering"],
      "dst":        ["tag:prod"],
      "ip":         ["tcp:22"],
      "srcPosture": ["posture:latestMac"]
    }
  ]
}
```

## Usage in SSH rules

```json
{
  "ssh": [
    {
      "action":     "accept",
      "src":        ["autogroup:member"],
      "dst":        ["tag:prod"],
      "users":      ["autogroup:nonroot"],
      "srcPosture": ["posture:latestMac"]
    }
  ]
}
```
