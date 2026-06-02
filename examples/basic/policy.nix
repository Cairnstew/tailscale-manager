{ config, lib, pkgs, ... }:

{
  services.tailscale-manager = {
    enable = true;
    tailnet = "tail685690.ts.net";
    credentialsFile = config.age.secrets.tailscale-oauth.path;

    # Declare multiple auth keys — replaces the top-level `tags` option.
    # Each key becomes a tailscale_tailnet_key Terraform resource.
    # Keys are created on `tailscale-manager apply` (runs on every nixos-rebuild).
    authKeys = {
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
        {
          src = ["autogroup:member"];
          dst = ["tag:github-connector"];
          ip = ["*"];
        }
        {
          src = ["autogroup:member"];
          dst = ["tag:internal-connector"];
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
        "tag:github-connector" = ["autogroup:admin"];
        "tag:internal-connector" = ["autogroup:admin"];
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

      appConnectors = [
        {
          name = "GitHub";
          connectors = ["tag:github-connector"];
          domains = ["github.com" "*.github.com"];
          routes = ["140.82.114.0/24"];
        }
        {
          name = "Internal Apps";
          connectors = ["tag:internal-connector"];
          domains = ["internal.example.com"];
        }
      ];

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
          "140.82.114.0/24" = ["tag:github-connector"];
        };
        exitNode = ["autogroup:admin"];
      };
    };
  };
}
