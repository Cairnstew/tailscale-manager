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

  # ── Serialization ────────────────────────────────────────────────

  policyToJSON = policy:
    let
      withoutEnable = builtins.removeAttrs policy [ "enable" ];
      # Top-level-only filter.  NOT recursive: we must not reach into
      # nested attrsets (tagOwners, groups, …) because empty-list
      # values are semantically meaningful there (e.g.
      #   "tag:server" = []
      # means "admin-only tag").  Inside lists (grants, ssh, …) the
      # submodule defaults are harmless — Tailscale ignores
      # null / [] / {} in those positions.
      cleaned = lib.filterAttrs
        (name: value: value != [] && value != {} && value != null)
        withoutEnable;
    in builtins.toJSON cleaned;

  policyFile =
    if cfg.policy.enable then
      pkgs.writeText "tailscale-policy.json" (policyToJSON cfg.policy)
    else if cfg.acl.policy != "" then
      pkgs.writeText "tailscale-policy.json" cfg.acl.policy
    else
      null;

  hasPolicyFile = policyFile != null;

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
      description = "Your Tailscale tailnet name, e.g. example.com";
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

    tailnetSettings = lib.mkOption {
      type = lib.types.nullOr (lib.types.submodule {
        freeformType = lib.types.attrs;
        options = {
          devicesApprovalOn = lib.mkOption {
            type = lib.types.bool;
            default = false;
            description = "Require approval for new devices";
          };
          devicesAutoUpdatesOn = lib.mkOption {
            type = lib.types.bool;
            default = false;
            description = "Enable automatic client updates";
          };
          devicesKeyDurationDays = lib.mkOption {
            type = lib.types.nullOr lib.types.int;
            default = null;
            description = "Auth key expiry in days. null = no limit";
          };
          usersApprovalOn = lib.mkOption {
            type = lib.types.bool;
            default = false;
            description = "Require approval for new users";
          };
          aclsExternallyManagedOn = lib.mkOption {
            type = lib.types.bool;
            default = false;
            description = "Mark ACLs as externally managed";
          };
          aclsExternalLink = lib.mkOption {
            type = lib.types.nullOr lib.types.str;
            default = null;
            description = "URL to external ACL documentation";
          };
          postureIdentityCollectionOn = lib.mkOption {
            type = lib.types.bool;
            default = false;
            description = "Enable posture identity collection";
          };
          httpsEnabled = lib.mkOption {
            type = lib.types.bool;
            default = false;
            description = "Enforce HTTPS for tailnet services";
          };
          regionalRoutingOn = lib.mkOption {
            type = lib.types.bool;
            default = false;
            description = "Enable regional routing";
          };
          usersRoleAllowedToJoinExternalTailnet = lib.mkOption {
            type = lib.types.nullOr lib.types.str;
            default = null;
            description = "User role allowed to join external tailnets";
          };
        };
      });
      default = null;
      description = "Declarative tailnet-wide settings. Active when non-null.";
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
            appConnector = lib.mkOption {
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

    assertions = [
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
      after = [ "network.target" ];

      serviceConfig = {
        Type = "oneshot";
        StateDirectory = [ "tailscale-manager" ];
        WorkingDirectory = cfg.stateDir;
        EnvironmentFile = cfg.credentialsFile;
        Environment = [
          "TAILSCALE_TAILNET=${cfg.tailnet}"
          "TAILSCALE_MANAGER_STATE_DIR=${cfg.stateDir}"
          "TAILSCALE_MANAGER_TERRAFORM_BIN=${cfg.terraformBin}"
          "TAILSCALE_MANAGER_BACKUP_COUNT=${toString cfg.backupCount}"
          "TAILSCALE_MANAGER_TAGS=${lib.concatStringsSep "," cfg.tags}"
          "TAILSCALE_MANAGER_RECREATE_IF_INVALID=${cfg.recreateIfInvalid}"
          "TAILSCALE_MANAGER_PROVIDER_VERSION=${cfg.providerVersion}"
          "TAILSCALE_MANAGER_DNS_NAMESERVERS=${lib.concatStringsSep "," cfg.dns.nameservers}"
          "TAILSCALE_MANAGER_DNS_MAGIC_DNS=${if cfg.dns.magicDns then "true" else "false"}"
          "TAILSCALE_MANAGER_ACL_ENABLE=${if cfg.acl.enable then "true" else "false"}"
          "TAILSCALE_MANAGER_ACL_FORMAT=${cfg.acl.format}"
        ] ++ lib.optional hasPolicyFile "TAILSCALE_MANAGER_ACL_POLICY_PATH=${policyFile}";
        ExecStart = "${cfg.package}/bin/tailscale-manager apply";
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        PrivateTmp = true;
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
