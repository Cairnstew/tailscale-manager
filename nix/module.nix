{ config, lib, pkgs, ... }:

let
  cfg = config.services.tailscale-manager;
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
        description = "Full ACL policy string (HuJSON or JSON). Must be valid for the chosen format.";
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
        ];
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
