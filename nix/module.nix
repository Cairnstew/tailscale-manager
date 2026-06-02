{ config, lib, pkgs, ... }:

let
  cfg = config.services.tailscale-manager;

  # ── Policy type helpers ────────────────────────────────────────────

  # App capabilities: "tailscale.com/cap/<name>" → list of opaque objects.
  # Each inner object is schema-less — the application defines its shape.
  appCapabilityType = lib.types.attrsOf (lib.types.listOf (
    lib.types.submodule {
      freeformType = lib.types.attrs;
      description = ''
        Application-defined capability parameter object.
        Schema depends on the capability:
          tailscale.com/cap/tailsql    → { dataSrc = ["*"] }
          tailscale.com/cap/golink     → { admin = true }
          tailscale.com/cap/kubernetes → { impersonate.groups = ["system:masters"] }
      '';
    }
  ));

  # DERP region node
  derpNodeType = lib.types.submodule {
    options = {
      name = lib.mkOption {
        type = lib.types.str;
        description = "Node name (e.g. '1')";
      };
      regionID = lib.mkOption {
        type = lib.types.int;
        description = "Must match parent region regionID";
      };
      hostName = lib.mkOption {
        type = lib.types.str;
        description = "FQDN of the DERP relay (e.g. derp.example.com)";
      };
      stunPort = lib.mkOption {
        type = lib.types.int;
        default = 3478;
        description = "STUN port for NAT detection";
      };
      stunOnly = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Set true for STUN-only nodes (no relay)";
      };
    };
  };

  # DERP region
  derpRegionType = lib.types.submodule {
    options = {
      regionID = lib.mkOption {
        type = lib.types.int;
        description = "Numeric region ID (e.g. 900)";
      };
      regionCode = lib.mkOption {
        type = lib.types.str;
        description = "Short region code (e.g. 'my-region')";
      };
      regionName = lib.mkOption {
        type = lib.types.str;
        description = "Human-readable region name";
      };
      nodes = lib.mkOption {
        type = lib.types.listOf derpNodeType;
        description = "DERP relay nodes in this region";
      };
    };
  };

  # ── App connector serialization helpers ────────────────────────────

  # Build the tailscale.com/app-connectors array from the user's list.
  # Strip empty routes per connector (filterAttrs can't reach inside lists).
  buildConnectorsArray = appConnectors:
    map (c:
      builtins.removeAttrs c [ "routes" ]
      // lib.optionalAttrs (c.routes != []) { routes = c.routes; }
    ) appConnectors;

  # Build the single nodeAttrs entry wrapping all connectors.
  buildAppConnectorAttrs = appConnectors:
    if appConnectors == [] then [] else [{
      target = ["*"];
      app = {
        "tailscale.com/app-connectors" = buildConnectorsArray appConnectors;
      };
    }];

  # Merge synthesized app connector entry with user's nodeAttrs.
  # Entries without an `app` field pass through unchanged.
  # Entries with an `app` field are dropped (mutual exclusion enforced
  # by assertion — but we guard anyway to avoid eval errors).
  mergeNodeAttrs = userNodeAttrs: synthesizedEntry:
    let
      nonAppEntries = builtins.filter
        (e: !(e ? app) || e.app == null || e.app == {})
        userNodeAttrs;
    in
      nonAppEntries ++ synthesizedEntry;

  # Strip empty sub-fields from autoApprovers (which is a submodule with
  # all-optional fields).  Unlike tagOwners/groups, empty lists here have
  # no semantic meaning and can cause Tailscale API rejection.
  stripAutoApprovers = autoApprovers:
    if builtins.isAttrs autoApprovers then
      lib.filterAttrs
        (name: value: value != [] && value != {} && value != null)
        autoApprovers
    else
      autoApprovers;

  # ── Serialization ────────────────────────────────────────────────

  # Strip null / [] / {} from an entry's direct fields (non-recursive).
  # Suitable for submodule entries where empty defaults carry no meaning.
  # TagOwners and groups are NOT processed here — empty list values are
  # semantically meaningful in those positions.
  cleanEntry = entry:
    if builtins.isAttrs entry
    then lib.filterAttrs (name: value: value != null && value != [] && value != {}) entry
    else entry;

  policyToJSON = policy:
    let
      withoutEnable = builtins.removeAttrs policy [ "enable" ];
      # Synthesize and merge app connector nodeAttrs entry
      appConnectorAttrs = buildAppConnectorAttrs policy.appConnectors;
      withoutAppConnectors = builtins.removeAttrs withoutEnable [ "appConnectors" ];
      mergedNodeAttrs = mergeNodeAttrs withoutAppConnectors.nodeAttrs appConnectorAttrs;
      withMergedAttrs = withoutAppConnectors // { nodeAttrs = mergedNodeAttrs; };
      # Strip empty sub-fields from autoApprovers before top-level filter
      withCleanApprovers = withMergedAttrs // {
        autoApprovers = stripAutoApprovers withMergedAttrs.autoApprovers;
      };
      # Clean submodule entries in lists where empty/null defaults would
      # either be rejected by the API (e.g. "srcPosture": [] returns 400)
      # or unnecessarily bloat the serialized policy.
      withCleanLists = withCleanApprovers // {
        grants    = map cleanEntry withCleanApprovers.grants;
        ssh       = map cleanEntry withCleanApprovers.ssh;
        acls      = map cleanEntry withCleanApprovers.acls;
        tests     = map cleanEntry withCleanApprovers.tests;
        sshTests  = map cleanEntry withCleanApprovers.sshTests;
        nodeAttrs = map cleanEntry withCleanApprovers.nodeAttrs;
      };
      # Top-level-only filter.  NOT recursive: we must not reach into
      # nested attrsets (tagOwners, groups, …) because empty-list
      # values are semantically meaningful there (e.g.
      #   "tag:server" = []
      # means "admin-only tag").
      cleaned = lib.filterAttrs
        (name: value: value != [] && value != {} && value != null)
        withCleanLists;
    in builtins.toJSON cleaned;

  policyJSON =
    if cfg.policy.enable then policyToJSON cfg.policy
    else if cfg.acl.policy != "" then cfg.acl.policy
    else "";

  hasPolicyFile = policyJSON != "";

  policyStore = pkgs.writeText "tailscale-policy.json" policyJSON;
  policyWriter = pkgs.writeShellScript "write-tailscale-policy" ''
    mkdir -p ${cfg.stateDir}
    install -m 0600 ${policyStore} ${cfg.stateDir}/policy.json
  '';

  # ── Auth keys serialization ───────────────────────────────────────────

  authKeysJSON = builtins.toJSON cfg.authKeys;
  hasAuthKeys = authKeysJSON != "{}";

  authKeysStore = pkgs.writeText "tailscale-auth-keys.json" authKeysJSON;
  authKeysWriter = pkgs.writeShellScript "write-tailscale-auth-keys" ''
    mkdir -p ${cfg.stateDir}
    install -m 0600 ${authKeysStore} ${cfg.stateDir}/auth-keys.json
  '';

  # App connector duplicate name detection
  hasDuplicateConnectorNames =
    let
      names = map (c: c.name) cfg.policy.appConnectors;
      count = n: builtins.length (builtins.filter (m: m == n) names);
    in
      builtins.any (n: count n > 1) names;

in
{

  options.services.tailscale-manager = {

    enable = lib.mkEnableOption "Tailscale auth key manager";

    package = lib.mkOption {
      type = lib.types.package;
      description = ''
        Package providing the tailscale-manager CLI.
        Set automatically when using the flake module via
        nixosModules.default.
      '';
    };

    stateDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/tailscale-manager";
      description = "Directory for Terraform state and backups";
    };

    credentialsFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = ''
        Path to an EnvironmentFile containing TAILSCALE_OAUTH_CLIENT_ID and
        TAILSCALE_OAUTH_CLIENT_SECRET. These are the canonical env var names
        that both the Python CLI and the Tailscale Terraform provider use.
        Use agenix or sops to encrypt this file.
      '';
      example = "/run/secrets/tailscale-oauth";
    };

    tailnet = lib.mkOption {
      type = lib.types.str;
      default = "-";
      description = ''
        Your Tailscale tailnet name. Defaults to "-" which auto-resolves from the
        OAuth credential. Recommended for most users.
      '';
    };

    terraformBin = lib.mkOption {
      type = lib.types.path;
      default = "${pkgs.terraform}/bin/terraform";
      defaultText = lib.literalExpression ''"${pkgs.terraform}/bin/terraform"'';
      description = "Path to the terraform binary";
    };

    tags = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = ''
        Tags to apply to the managed auth key (e.g. tag:infra).
        Set via TAILSCALE_MANAGER_TAGS as comma-separated values when
        running outside NixOS: e.g. TAILSCALE_MANAGER_TAGS='tag:server,tag:ci'.
        All tags must start with 'tag:' and must be owned by the OAuth client.
      '';
    };

    backupCount = lib.mkOption {
      type = lib.types.int;
      default = 5;
      description = "Number of tfstate backups to retain in stateDir/backups/";
    };

    watchCredentials = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = ''
        Create a systemd path unit that re-runs apply when credentialsFile changes
        (e.g. after agenix/sops rotation). Uses PathModified to catch both in-place
        edits and atomic renames (the latter being how agenix writes secrets).
      '';
    };

    enableTimer = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = ''
        Enable a daily systemd timer to automatically re-run apply.
        Useful for catching drift or rotating keys near expiry.
        When false (default), apply only runs on nixos-rebuild switch
        and credential file changes (if watchCredentials is true).
      '';
    };

    recreateIfInvalid = lib.mkOption {
      type = lib.types.enum [ "always" "never" ];
      default = "always";
      description = ''
        Whether to recreate the managed auth key if it becomes invalid
        (expired, revoked, or deleted). "always" enables automatic key
        rotation. "never" requires manual intervention.
      '';
    };

    providerVersion = lib.mkOption {
      type = lib.types.str;
      default = "~> 0.29";
      description = "Tailscale Terraform provider version constraint.";
    };

    authKeys = lib.mkOption {
      type = lib.types.attrsOf (lib.types.submodule {
        options = {
          description = lib.mkOption {
            type = lib.types.str;
            description = "Human-readable description for this auth key";
            example = "CI pipeline key";
          };
          tags = lib.mkOption {
            type = lib.types.listOf lib.types.str;
            default = [];
            description = "Tags to apply to this auth key";
            example = ["tag:ci"];
          };
          reusable = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Allow multiple devices to use this key";
          };
          ephemeral = lib.mkOption {
            type = lib.types.bool;
            default = false;
            description = "Ephemeral devices are removed on disconnect";
          };
          preauthorized = lib.mkOption {
            type = lib.types.bool;
            default = true;
            description = "Pre-approve devices using this key";
          };
          recreateIfInvalid = lib.mkOption {
            type = lib.types.enum [ "always" "never" ];
            default = "always";
            description = ''
              Whether to recreate this key if it becomes invalid
              (expired, revoked, or deleted).
            '';
          };
        };
      });
      default = {};
      description = ''
        Declare multiple auth keys. When non-empty, these replace the
        top-level tags and recreateIfInvalid options.

        Each attr name becomes the Terraform resource name (hyphens
        are converted to underscores).
      '';
      example = {
        ci-key = {
          description = "CI pipeline key";
          tags = ["tag:ci"];
          ephemeral = true;
        };
        monitoring = {
          description = "Monitoring service key";
          tags = ["tag:monitoring"];
          reusable = false;
        };
      };
    };

    dns = {
      nameservers = lib.mkOption {
        type = lib.types.listOf lib.types.str;
        default = [ ];
        description = "Global DNS nameserver IPs (e.g. [\"1.1.1.1\" \"8.8.8.8\"])";
        example = [ "1.1.1.1" "8.8.8.8" ];
      };

      magicDns = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Enable MagicDNS for this tailnet";
      };

      splitNameservers = lib.mkOption {
        type = lib.types.attrsOf (lib.types.listOf lib.types.str);
        default = { };
        description = ''
          Split DNS mapping: domain → list of nameserver IPs.
          Each key becomes a separate tailscale_dns_split_nameservers resource.
        '';
        example = {
          "corp.example.com" = [ "10.0.0.53" ];
        };
      };
    };

    acl = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          Enable ACL management. WARNING: applying overwrites the entire tailnet
          policy. Current policy is backed up before every apply and restored on
          failure.
        '';
      };

      format = lib.mkOption {
        type = lib.types.enum [ "hujson" "json" ];
        default = "hujson";
        description = "Policy file format. hujson is native Tailscale; json is standard JSON.";
      };

      policy = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = ''
          DEPRECATED: use services.tailscale-manager.policy (structured) instead.
          Full ACL policy string (HuJSON or JSON). Must be valid for the chosen format.
          If both policy.enable and this option are set, an assertion error is raised.
        '';
        example = ''
          {
            "acls": [{ "action": "accept", "src": ["autogroup:member"], "dst": ["autogroup:member:*"] }]
          }
        '';
      };
    };

    # ── Structured policy ──────────────────────────────────────────────

    policy = {
      enable = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = ''
          Enable the structured tailnet policy options below.

          When true, the options in policy.{grants,acls,ssh,...} are serialized
          to JSON and passed to tailscale-manager. This replaces the raw string
          policy in acl.policy — do not set both.
        '';
      };

      grants = lib.mkOption {
        type = lib.types.listOf (lib.types.submodule {
          options = {
            src = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              description = "Source selectors (users, groups, tags, autogroups)";
              example = ["group:engineering"];
            };
            dst = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              description = "Destination selectors";
              example = ["tag:server"];
            };
            ip = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "Network-layer capability selectors (ports/protocols)";
              example = ["*" "tcp:443"];
            };
            app = lib.mkOption {
              type = lib.types.nullOr appCapabilityType;
              default = null;
              description = "Application-layer capabilities (e.g. tailsql, golink)";
              example = {
                "tailscale.com/cap/tailsql" = [
                  { dataSrc = ["*"]; }
                ];
              };
            };
            srcPosture = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "Posture conditions restricting the source";
              example = ["posture:latestMac"];
            };
            via = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "Route traffic through specific exit nodes or subnet routers";
              example = ["tag:corp-exit"];
            };
          };
        });
        default = [];
        description = "Grant entries — the preferred access control mechanism";
      };

      acls = lib.mkOption {
        type = lib.types.listOf (lib.types.submodule {
          options = {
            action = lib.mkOption {
              type = lib.types.enum ["accept"];
              description = "Rule action (only 'accept' — Tailscale is deny-by-default)";
            };
            src = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              description = "Source selectors";
              example = ["autogroup:member"];
            };
            proto = lib.mkOption {
              type = lib.types.nullOr lib.types.str;
              default = null;
              description = "Protocol filter. Omit for all TCP+UDP";
              example = "tcp";
            };
            dst = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              description = "Destinations in host:port format";
              example = ["autogroup:member:*"];
            };
          };
        });
        default = [];
        description = "ACL rules (legacy — prefer grants for new policies)";
      };

      ssh = lib.mkOption {
        type = lib.types.listOf (lib.types.submodule {
          options = {
            action = lib.mkOption {
              type = lib.types.enum ["accept" "check"];
              description = "accept = allow, check = allow with periodic re-auth";
            };
            src = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              description = "SSH client selectors";
              example = ["autogroup:member"];
            };
            dst = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              description = "SSH destination selectors";
              example = ["autogroup:self"];
            };
            users = lib.mkOption {
              type = lib.types.nullOr (lib.types.listOf lib.types.str);
              default = null;
              description = "Allowed SSH usernames on the destination (null = connecting user's login)";
              example = ["autogroup:nonroot" "root"];
            };
            checkPeriod = lib.mkOption {
              type = lib.types.nullOr lib.types.str;
              default = null;
              description = "Re-auth interval for 'check' action (e.g. '12h', '90m', 'always')";
              example = "12h";
            };
            acceptEnv = lib.mkOption {
              type = lib.types.nullOr (lib.types.listOf lib.types.str);
              default = null;
              description = "Environment variable patterns clients can forward via SendEnv";
              example = ["FOO_*"];
            };
            srcPosture = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "Posture conditions restricting the SSH client";
              example = ["posture:latestMac"];
            };
          };
        });
        default = [];
        description = "Tailscale SSH rules — require matching ACL or grant for port 22";
      };

      tagOwners = lib.mkOption {
        type = lib.types.attrsOf (lib.types.listOf lib.types.str);
        default = {};
        description = "Who can assign each tag to a device. Empty list = admin-only.";
        example = {
          "tag:ci" = ["autogroup:admin"];
          "tag:server" = [];
        };
      };

      groups = lib.mkOption {
        type = lib.types.attrsOf (lib.types.listOf lib.types.str);
        default = {};
        description = "Named groups of users. Groups cannot contain other groups.";
        example = {
          "group:engineering" = ["alice@example.com" "bob@example.com"];
          "group:sre" = ["carol@example.com"];
        };
      };

      hosts = lib.mkOption {
        type = lib.types.attrsOf lib.types.str;
        default = {};
        description = "Named IP/CIDR aliases for use in access rules";
        example = {
          "jump-box" = "100.100.100.100";
          "office-net" = "203.0.113.0/24";
        };
      };

      ipsets = lib.mkOption {
        type = lib.types.attrsOf (lib.types.listOf lib.types.str);
        default = {};
        description = "Named IP collections. Can reference other ipsets, hosts, CIDRs, or IPs.";
        example = {
          "ipset:prod" = ["10.0.1.0/24" "10.0.2.0/24"];
          "ipset:all-regions" = ["ipset:us-east" "ipset:us-west"];
        };
      };

      postures = lib.mkOption {
        type = lib.types.attrsOf (lib.types.listOf lib.types.str);
        default = {};
        description = "Device posture condition expressions";
        example = {
          "posture:latestMac" = [
            "node:os IN ['macos']"
            "node:tsReleaseTrack == 'stable'"
          ];
        };
      };

      nodeAttrs = lib.mkOption {
        type = lib.types.listOf (lib.types.submodule {
          options = {
            target = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              description = "Which nodes the attributes apply to";
              example = ["tag:server"];
            };
            attr = lib.mkOption {
              type = lib.types.nullOr (lib.types.listOf lib.types.str);
              default = null;
              description = "Device attributes (funnel, nextdns:<id>, disable-ipv4, etc.)";
              example = ["funnel"];
            };
            app = lib.mkOption {
              type = lib.types.nullOr appCapabilityType;
              default = null;
              description = "App-layer capabilities (app connectors)";
              example = {
                "tailscale.com/app-connectors" = [
                  {
                    name = "internal-apps";
                    connectors = ["tag:app-connector"];
                    domains = ["internal.example.com"];
                    routes = ["10.0.0.0/8"];
                  }
                ];
              };
            };
          };
        });
        default = [];
        description = "Per-device attributes (NextDNS, Funnel, randomize-client-port, app connectors)";
      };

      appConnectors = lib.mkOption {
        type = lib.types.listOf (lib.types.submodule {
          options = {
            name = lib.mkOption {
              type = lib.types.str;
              description = "Human-readable connector name (e.g. 'GitHub')";
              example = "GitHub";
            };
            connectors = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              description = "Tags of devices acting as app connectors";
              example = ["tag:github-connector"];
            };
            domains = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              description = "Domains the connector proxies (e.g. ['github.com'])";
              example = ["github.com" "*.github.com"];
            };
            routes = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "Optional CIDR routes the connector proxies";
              example = ["140.82.114.0/24"];
            };
          };
        });
        default = [];
        description = ''
          Declarative app connector configuration.

          This option synthesizes the correct nodeAttrs entry with the
          tailscale.com/app-connectors capability. It merges with any
          existing policy.nodeAttrs entries that do not have an `app` field.

          IMPORTANT: This is only the policy-file half. You must also:
          1. Configure the connector host device (tailscale up --advertise-connector)
          2. Declare tag ownership via policy.tagOwners for every connector tag
          3. Optionally declare access grants via policy.grants
          4. Optionally declare route auto-approval via policy.autoApprovers
        '';
      };

      autoApprovers = lib.mkOption {
        type = lib.types.submodule {
          options = {
            routes = lib.mkOption {
              type = lib.types.attrsOf (lib.types.listOf lib.types.str);
              default = {};
              description = "CIDR range → authorized approvers";
              example = {
                "10.0.0.0/8" = ["group:neteng"];
              };
            };
            exitNode = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "Authorized approvers for exit node advertisements";
              example = ["tag:corp-exit"];
            };
            appConnectors = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "Authorized approvers for app connector advertisements";
              example = ["tag:app-connector-manager"];
            };
          };
        };
        default = {};
        description = "Users/groups/tags that can bypass approval for routes and exit nodes";
      };

      tests = lib.mkOption {
        type = lib.types.listOf (lib.types.submodule {
          options = {
            src = lib.mkOption {
              type = lib.types.str;
              description = "Source identity to test from (user, group, tag, or host)";
              example = "alice@example.com";
            };
            srcPostureAttrs = lib.mkOption {
              type = lib.types.nullOr (lib.types.attrsOf lib.types.str);
              default = null;
              description = "Posture attributes to simulate for this test";
              example = { "node:os" = "windows"; };
            };
            proto = lib.mkOption {
              type = lib.types.nullOr lib.types.str;
              default = null;
              description = "Protocol to test (tcp, udp, icmp). Defaults to TCP+UDP.";
              example = "tcp";
            };
            accept = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "Destinations that should be reachable for src";
              example = ["tag:prod:22"];
            };
            deny = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "Destinations that should be blocked for src";
              example = ["tag:prod:3389"];
            };
          };
        });
        default = [];
        description = "ACL/grant assertion tests — policy is rejected if they fail";
      };

      sshTests = lib.mkOption {
        type = lib.types.listOf (lib.types.submodule {
          options = {
            src = lib.mkOption {
              type = lib.types.str;
              description = "SSH client identity";
              example = "sre-lead@example.com";
            };
            dst = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              description = "SSH destinations";
              example = ["tag:prod"];
            };
            accept = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "SSH usernames that should be accepted without checks";
              example = ["root"];
            };
            check = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "SSH usernames that should require re-auth checks";
              example = ["admin"];
            };
            deny = lib.mkOption {
              type = lib.types.listOf lib.types.str;
              default = [];
              description = "SSH usernames that should be denied";
              example = ["alice"];
            };
            srcPostureAttrs = lib.mkOption {
              type = lib.types.nullOr (lib.types.attrsOf lib.types.str);
              default = null;
              description = "Posture attributes to simulate for this test";
              example = { "node:os" = "windows"; };
            };
          };
        });
        default = [];
        description = "SSH assertion tests — policy is rejected if they fail";
      };

      derpMap = lib.mkOption {
        type = lib.types.nullOr (lib.types.submodule {
          options = {
            omitDefaultRegions = lib.mkOption {
              type = lib.types.bool;
              default = false;
              description = "Set true to disable Tailscale-provided DERP servers";
            };
            regions = lib.mkOption {
              type = lib.types.attrsOf derpRegionType;
              default = {};
              description = "Custom DERP regions (map of regionID → region config)";
            };
          };
        });
        default = null;
        description = "Custom DERP relay server configuration";
      };

      disableIPv4 = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Stop assigning IPv4 Tailscale addresses (100.x.y.z)";
      };

      randomizeClientPort = lib.mkOption {
        type = lib.types.bool;
        default = false;
        description = "Use random WireGuard port instead of 41641";
      };

      oneCGNATRoute = lib.mkOption {
        type = lib.types.str;
        default = "";
        description = "CGNAT route behavior: '' (default), 'mac-always', or 'mac-never'";
        example = "mac-always";
      };
    };
  };

  config = lib.mkIf cfg.enable {
    assertions =
      [
      {
        assertion = lib.hasPrefix "/nix/store" (toString cfg.terraformBin);
        message = ''
          services.tailscale-manager.terraformBin must point to a path in the Nix
          store (e.g. "${pkgs.terraform}/bin/terraform"). This ensures the binary's
          integrity and reproducibility. Arbitrary paths are not permitted.
        '';
      }
    ] ++ lib.optionals (hasDuplicateConnectorNames && cfg.policy.enable) [{
        assertion = false;
        message = ''
          services.tailscale-manager.policy.appConnectors: duplicate connector
          name detected.  Connector names must be unique — the Tailscale API
          will reject the policy.
        '';
      }]
      ++ [
      {
        assertion = cfg.credentialsFile != null;
        message = ''
          services.tailscale-manager.credentialsFile must be set.

          Example with agenix:
            credentialsFile = config.age.secrets.tailscale-oauth.path;
          Example with sops-nix:
            credentialsFile = config.sops.secrets.tailscale-oauth.path;

          The file must be in EnvironmentFile format with these variables:
            TAILSCALE_OAUTH_CLIENT_ID=<value>
            TAILSCALE_OAUTH_CLIENT_SECRET=<value>
        '';
      }
      {
        assertion = !(cfg.policy.enable && cfg.acl.policy != "");
        message = ''
          services.tailscale-manager.policy (structured) and
          services.tailscale-manager.acl.policy (raw string) are both set.
          Use only one. The structured policy takes precedence when enabled.
        '';
      }
      {
        assertion = !cfg.policy.enable || cfg.acl.enable;
        message = ''
          services.tailscale-manager.policy is enabled but
          services.tailscale-manager.acl.enable is false.
          Set acl.enable = true to manage the tailnet policy.
        '';
      }
      {
        assertion = !(cfg.policy.appConnectors != [] && !cfg.policy.enable);
        message = ''
          services.tailscale-manager.policy.appConnectors is non-empty but
          services.tailscale-manager.policy.enable is false.
          Set policy.enable = true to use structured app connector options.
        '';
      }
      {
        assertion = !(cfg.policy.appConnectors != [] && !cfg.acl.enable);
        message = ''
          services.tailscale-manager.policy.appConnectors is non-empty but
          services.tailscale-manager.acl.enable is false.
          Set acl.enable = true to manage the tailnet policy including app connectors.
        '';
      }
      {
        assertion = !(
          cfg.policy.appConnectors != []
          && builtins.any
              (e: (e ? app) && e.app != null && e.app != {})
              cfg.policy.nodeAttrs
        );
        message = ''
          services.tailscale-manager.policy.appConnectors is set alongside a
          services.tailscale-manager.policy.nodeAttrs entry with an `app` field.
          These are mutually exclusive. Either:
          - Use appConnectors (typed, recommended) and remove the nodeAttrs.app entry, or
          - Remove appConnectors and manage the app connector nodeAttrs entry manually.
        '';
      }
    ];

    environment.systemPackages = [ cfg.package ];

    # Print the last apply result on every nixos-rebuild switch.
    # Informational only — does not trigger re-apply.
    system.activationScripts.tailscale-manager-status = let
      lastApplyFile = "${cfg.stateDir}/last-apply.json";
      jqBin = "${pkgs.jq}/bin/jq";
    in ''
      if [ -f "${lastApplyFile}" ]; then
        RESULT=$(${jqBin} -r '.result // "unknown"' "${lastApplyFile}" 2>/dev/null)
        echo "tailscale-manager: last apply [$RESULT]"
      fi
    '';

    systemd.services.tailscale-manager = {
      description = "Tailscale auth key manager";
      documentation = [ "https://github.com/user/tailscale-manager" ];
      wantedBy = [ "multi-user.target" ];
      partOf = [ "multi-user.target" ];
      wants = [ "network-online.target" ];
      after = [ "network-online.target" ];

      path = [ pkgs.getent ];

      # Use the environment attrset (not serviceConfig.Environment) so NixOS
      # handles quoting automatically — essential for values containing spaces
      # like providerVersion = "~> 0.29" which would otherwise be split by
      # systemd's Environment= directive.
      environment = {
        GODEBUG = "netdns=go";
        # Terraform writes its plugin cache to $HOME/.terraform.d/.
        # ProtectHome=true remounts /root/ as read-only, so redirect HOME
        # to the writable state directory.
        HOME = "${cfg.stateDir}";
        TAILSCALE_TAILNET = "${cfg.tailnet}";
        TAILSCALE_MANAGER_STATE_DIR = "${cfg.stateDir}";
        TAILSCALE_MANAGER_TERRAFORM_BIN = "${cfg.terraformBin}";
        TAILSCALE_MANAGER_BACKUP_COUNT = "${toString cfg.backupCount}";
        TAILSCALE_MANAGER_TAGS = "${lib.concatStringsSep "," cfg.tags}";
        TAILSCALE_MANAGER_RECREATE_IF_INVALID = "${cfg.recreateIfInvalid}";
        TAILSCALE_MANAGER_PROVIDER_VERSION = "${cfg.providerVersion}";
        TAILSCALE_MANAGER_DNS_NAMESERVERS = "${lib.concatStringsSep "," cfg.dns.nameservers}";
        TAILSCALE_MANAGER_DNS_MAGIC_DNS = "${if cfg.dns.magicDns then "true" else "false"}";
        TAILSCALE_MANAGER_ACL_ENABLE = "${if cfg.acl.enable then "true" else "false"}";
        TAILSCALE_MANAGER_ACL_FORMAT = "${cfg.acl.format}";
      } // lib.optionalAttrs hasPolicyFile {
        TAILSCALE_MANAGER_ACL_POLICY_PATH = "${cfg.stateDir}/policy.json";
      } // lib.optionalAttrs hasAuthKeys {
        TAILSCALE_MANAGER_AUTH_KEYS_PATH = "${cfg.stateDir}/auth-keys.json";
      };

      restartIfChanged = true;

      serviceConfig = {
        Type = "oneshot";
        StateDirectory = [ "tailscale-manager" ];
        StateDirectoryMode = "0700";
        WorkingDirectory = cfg.stateDir;
        LoadCredential = "tailscale-oauth:${cfg.credentialsFile}";
        ExecStartPre = lib.optional hasPolicyFile (toString policyWriter)
          ++ lib.optional hasAuthKeys (toString authKeysWriter);
        ExecStart = "${cfg.package}/bin/tailscale-manager apply";
        ReadWritePaths = [ cfg.stateDir ];
        NoNewPrivileges = true;
        PrivateTmp = true;
        PrivateMounts = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        CapabilityBoundingSet = "";
        MemoryDenyWriteExecute = true;
        RestrictNamespaces = true;
        LockPersonality = true;
        RestrictSUIDSGID = true;
        SystemCallFilter = "@system-service";
        RemoveIPC = true;
      };
    };

    # Path unit: re-run apply when credentials file is updated (e.g. agenix rotation)
    # Uses PathModified (not PathChanged) because agenix writes atomically via rename,
    # which PathChanged may not detect on all systemd versions.
    systemd.paths.tailscale-manager-watch = lib.mkIf cfg.watchCredentials {
      description = "Tailscale manager credential watcher";
      wantedBy = [ "multi-user.target" ];
      pathConfig = {
        PathModified = cfg.credentialsFile;
        Unit = "tailscale-manager.service";
        MakeDirectory = "auto";
      };
    };

    systemd.timers.tailscale-manager = lib.mkIf cfg.enableTimer {
      description = "Daily Tailscale manager apply timer";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "daily";
        Persistent = true;
        Unit = "tailscale-manager.service";
      };
    };

  };
}
