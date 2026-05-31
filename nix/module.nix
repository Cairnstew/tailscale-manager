{ config, lib, pkgs, ... }:

let
  cfg = config.services.tailscale-manager;
in

{

  options.services.tailscale-manager = {
    enable = lib.mkEnableOption "Tailscale auth key manager";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.tailscale-manager;
      defaultText = lib.literalExpression "pkgs.tailscale-manager";
      description = "Package providing the tailscale-manager CLI";
    };

    stateDir = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/tailscale-manager";
      description = "Directory for Terraform state and backups";
    };

    credentialsFile = lib.mkOption {
      type = lib.types.path;
      description = ''
        Path to an EnvironmentFile containing TAILSCALE_OAUTH_CLIENT_ID and
        TAILSCALE_OAUTH_CLIENT_SECRET. These are the canonical env var names
        that both the Python CLI and the Tailscale Terraform provider use.
        Use agenix or sops to encrypt this file.
      '';
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
      description = "Tags to apply to the managed auth key (e.g. tag:infra)";
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
  };

  config = lib.mkIf cfg.enable {

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

    # Timer placeholder — uncomment and configure for periodic apply:
    # systemd.timers.tailscale-manager = {
    #   description = "Periodic Tailscale auth key sync";
    #   wantedBy = [ "timers.target" ];
    #   partOf = [ "timers.target" ];
    #   timerConfig = {
    #     OnCalendar = "daily";
    #     Persistent = true;
    #   };
    # };

  };

}
