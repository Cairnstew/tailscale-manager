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
