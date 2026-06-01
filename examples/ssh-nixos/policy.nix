{ config, lib, pkgs, ... }:

{
  services.tailscale-manager = {
    enable = true;
    tailnet = "your-tailnet.ts.net";
    credentialsFile = config.age.secrets.tailscale-oauth.path;

    acl.enable = true;

    policy = {
      enable = true;

      # Grant TCP port 22 so SSH traffic is allowed at the network layer.
      # Without these, SSH rules have nothing to operate on.
      grants = [
        # Members can reach NixOS servers on SSH port
        {
          src = ["autogroup:member"];
          dst = ["tag:nixos"];
          ip = ["tcp:22"];
        }
        # NixOS servers can reach each other (orchestration, rsync, etc.)
        {
          src = ["tag:nixos"];
          dst = ["tag:nixos"];
          ip = ["tcp:22"];
        }
      ];

      ssh = [
        # Admin: full root + nonroot access, no re-auth
        {
          action = "accept";
          src = ["autogroup:admin"];
          dst = ["tag:nixos"];
          users = ["autogroup:nonroot" "root"];
        }
        # Members: nonroot only, with periodic re-authentication
        {
          action = "check";
          src = ["autogroup:member"];
          dst = ["tag:nixos"];
          users = ["autogroup:nonroot"];
          checkPeriod = "12h";
        }
        # Machine-to-machine: root access for automation (ansible, salt, etc.)
        {
          action = "accept";
          src = ["tag:nixos"];
          dst = ["tag:nixos"];
          users = ["root"];
        }
      ];

      tagOwners = {
        "tag:nixos" = ["autogroup:admin"];
      };
    };
  };
}
