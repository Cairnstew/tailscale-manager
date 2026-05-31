# Basic example — all policy sections

Demonstrates every section of the Tailscale policy file that can be configured
via the structured `services.tailscale-manager.policy` option.

## Nix config (`policy.nix`)

```nix
services.tailscale-manager = {
  enable = true;
  tailnet = "tail685690.ts.net";
  credentialsFile = config.age.secrets.tailscale-oauth.path;

  acl = {
    enable = true;
    format = "hujson";
  };

  policy = {
    enable = true;

    grants = [
      {
        src = ["autogroup:admin"];
        dst = ["tag:ci"];
        ip = ["*"];
      }
      {
        src = ["autogroup:member"];
        dst = ["autogroup:self"];
        ip = ["*"];
      }
    ];

    ssh = [
      {
        action = "accept";
        src = ["autogroup:member"];
        dst = ["autogroup:self"];
        users = ["autogroup:nonroot" "root"];
      }
    ];

    tagOwners = {
      "tag:ci" = ["autogroup:admin"];
      "tag:server" = [];
      "tag:monitoring" = ["autogroup:member"];
    };

    hosts = {
      bastion = "100.100.100.1";
      monitoring = "100.100.100.2";
    };

    ipsets = {
      "ipset:datacenters" = ["10.0.0.0/8" "172.16.0.0/12"];
      "ipset:cloud-ranges" = ["100.100.0.0/16" "ipset:datacenters"];
    };

    postures = {
      "posture:linux-stable" = [
        "node:os IN ['linux']"
        "node:tsReleaseTrack == 'stable'"
      ];
      "posture:mac-secure" = [
        "node:os IN ['macos']"
        "node:tsReleaseTrack == 'stable'"
      ];
    };

    nodeAttrs = [
      {
        target = ["autogroup:member"];
        attr = ["funnel"];
      }
      {
        target = ["tag:monitoring"];
        attr = ["randomize-client-port"];
      }
    ];

    autoApprovers = {
      routes = {
        "10.0.0.0/8" = ["autogroup:admin"];
        "192.168.0.0/16" = ["tag:ci"];
      };
      exitNode = ["autogroup:admin"];
    };
  };
};
```

## Generated JSON (`policy.json`)

```json
{
  "grants": [
    {
      "src": ["autogroup:admin"],
      "dst": ["tag:ci"],
      "ip":  ["*"]
    },
    {
      "src": ["autogroup:member"],
      "dst": ["autogroup:self"],
      "ip":  ["*"]
    }
  ],
  "ssh": [
    {
      "action": "accept",
      "src":    ["autogroup:member"],
      "dst":    ["autogroup:self"],
      "users":  ["autogroup:nonroot", "root"]
    }
  ],
  "tagOwners": {
    "tag:ci":         ["autogroup:admin"],
    "tag:server":     [],
    "tag:monitoring": ["autogroup:member"]
  },
  "hosts": {
    "bastion":    "100.100.100.1",
    "monitoring": "100.100.100.2"
  },
  "ipsets": {
    "ipset:datacenters":  ["10.0.0.0/8", "172.16.0.0/12"],
    "ipset:cloud-ranges": ["100.100.0.0/16", "ipset:datacenters"]
  },
  "postures": {
    "posture:linux-stable": [
      "node:os IN ['linux']",
      "node:tsReleaseTrack == 'stable'"
    ],
    "posture:mac-secure": [
      "node:os IN ['macos']",
      "node:tsReleaseTrack == 'stable'"
    ]
  },
  "nodeAttrs": [
    {
      "target": ["autogroup:member"],
      "attr":   ["funnel"]
    },
    {
      "target": ["tag:monitoring"],
      "attr":   ["randomize-client-port"]
    }
  ],
  "autoApprovers": {
    "routes": {
      "10.0.0.0/8":     ["autogroup:admin"],
      "192.168.0.0/16": ["tag:ci"]
    },
    "exitNode": ["autogroup:admin"]
  }
}
```

## What it demonstrates

| Section | What to look for |
|---|---|
| `grants` | Preferred access control with `autogroup:` selectors |
| `ssh` | Tailscale SSH with nonroot + root access |
| `tagOwners` | Empty list (`[]`) for admin-only tags |
| `hosts` | Named IP aliases usable in ACLs/grants |
| `ipsets` | Named IP collections with nesting (cloud-ranges references datacenters) |
| `postures` | Device posture conditions with `node:os` and `node:tsReleaseTrack` |
| `nodeAttrs` | Per-device attributes (funnel, randomize-client-port) |
| `autoApprovers` | Route auto-approval by role or tag |

## Notes

- The Nix `policy` block serializes to the JSON verbatim via `policyToJSON`.
- Empty owner lists (`tag:server = []`) survive serialization — Tailscale treats
  them as "admin-only tags", distinct from absent entries.
- The `enable` sentinel is stripped before serialization and does not appear
  in the output.
- Sections not set (`acls`, `tests`, `groups`, `derpMap`, scalars) are omitted
  from the JSON — Tailscale uses defaults for absent keys.
