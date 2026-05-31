{ config, lib, pkgs, ... }:

{
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
}
