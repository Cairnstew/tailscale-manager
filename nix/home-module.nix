{ config, lib, pkgs, ... }:

let
  cfg = config.homeManagerModules.tailscale-manager;
in

{

  options.homeManagerModules.tailscale-manager = {
    enable = lib.mkEnableOption "Tailscale manager CLI tools";

    package = lib.mkOption {
      type = lib.types.package;
      description = ''
        Package providing the tailscale-manager CLI.
        Set automatically when using the flake module via
        homeManagerModules.default.
      '';
    };

    tailnet = lib.mkOption {
      type = lib.types.str;
      default = "";
      description = "Tailscale tailnet name (sets TAILSCALE_TAILNET env)";
    };

    credentialsFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = ''
        Path to an EnvironmentFile containing TAILSCALE_OAUTH_CLIENT_ID and
        TAILSCALE_OAUTH_CLIENT_SECRET. If set, loads vars into the user session.

        NOTE: LoadCredential is not available for Home Manager user services
        (systemd --user scope). The home-module continues to use EnvironmentFile
        for credential delivery. The Python AppConfig falls back to reading
        TAILSCALE_OAUTH_CLIENT_ID/SECRET from the environment when
        CREDENTIALS_DIRECTORY is not set.
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ cfg.package ];

    home.sessionVariables = lib.optionalAttrs (cfg.tailnet != "") {
      TAILSCALE_TAILNET = cfg.tailnet;
    };

    home.file = lib.optionalAttrs (cfg.credentialsFile != null) {
      ".config/tailscale-manager/env".source = cfg.credentialsFile;
    };
  };

}
