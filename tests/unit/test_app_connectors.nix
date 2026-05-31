#! /usr/bin/env nix-instantiate --eval --json
# Serialization tests for policy.appConnectors -> nodeAttrs merge.
# Each test returns the serialized JSON for manual or automated inspection.
# Run:  nix-instantiate --eval --json --strict tests/unit/test_app_connectors.nix

let
  lib = (import <nixpkgs> {}).lib;

  buildConnectorsArray = appConnectors:
    map (c:
      builtins.removeAttrs c [ "routes" ]
      // lib.optionalAttrs (c.routes != []) { routes = c.routes; }
    ) appConnectors;

  buildAppConnectorAttrs = appConnectors:
    if appConnectors == [] then [] else [{
      target = ["*"];
      app = {
        "tailscale.com/app-connectors" = buildConnectorsArray appConnectors;
      };
    }];

  mergeNodeAttrs = userNodeAttrs: synthesizedEntry:
    let
      nonAppEntries = builtins.filter
        (e: !(e ? app) || e.app == null || e.app == {})
        userNodeAttrs;
    in
      nonAppEntries ++ synthesizedEntry;

  serializedJSON = policy:
    let
      withoutEnable = builtins.removeAttrs policy [ "enable" ];
      appConnectorAttrs = buildAppConnectorAttrs policy.appConnectors;
      withoutAppConnectors = builtins.removeAttrs withoutEnable [ "appConnectors" ];
      mergedNodeAttrs = mergeNodeAttrs withoutAppConnectors.nodeAttrs appConnectorAttrs;
      withMergedAttrs = withoutAppConnectors // { nodeAttrs = mergedNodeAttrs; };
      cleaned = lib.filterAttrs
        (name: value: value != [] && value != {} && value != null)
        withMergedAttrs;
    in builtins.toJSON cleaned;

in builtins.toJSON {
  test1_singleConnector = serializedJSON {
    enable = true;
    appConnectors = [{ name = "GitHub"; connectors = ["tag:gh"]; domains = ["github.com"]; routes = []; }];
    grants = [];
    nodeAttrs = [];
  };

  test2_withRoutes = serializedJSON {
    enable = true;
    appConnectors = [{ name = "G"; connectors = ["tag:g"]; domains = ["g.com"]; routes = ["140.82.114.0/24"]; }];
    grants = [];
    nodeAttrs = [];
  };

  test3_withoutRoutes = serializedJSON {
    enable = true;
    appConnectors = [{ name = "G"; connectors = ["tag:g"]; domains = ["g.com"]; routes = []; }];
    grants = [];
    nodeAttrs = [];
  };

  test4_multipleConnectors = serializedJSON {
    enable = true;
    appConnectors = [
      { name = "GH"; connectors = ["tag:gh"]; domains = ["github.com"]; routes = []; }
      { name = "Okta"; connectors = ["tag:ok"]; domains = ["okta.com"]; routes = []; }
    ];
    grants = [];
    nodeAttrs = [];
  };

  test5_empty = serializedJSON {
    enable = true;
    appConnectors = [];
    grants = [];
    nodeAttrs = [];
  };

  test6_mergeWithFunnel = serializedJSON {
    enable = true;
    appConnectors = [{ name = "G"; connectors = ["tag:g"]; domains = ["g.com"]; routes = []; }];
    grants = [];
    nodeAttrs = [{ target = ["autogroup:member"]; attr = ["funnel"]; }];
  };

  test7_mergeWithAttrOnly = serializedJSON {
    enable = true;
    appConnectors = [{ name = "G"; connectors = ["tag:g"]; domains = ["g.com"]; routes = []; }];
    grants = [];
    nodeAttrs = [{ target = ["tag:iot"]; attr = ["randomize-client-port"]; }];
  };

  test8_mergeWithGranularTargets = serializedJSON {
    enable = true;
    appConnectors = [{ name = "G"; connectors = ["tag:g"]; domains = ["g.com"]; routes = []; }];
    grants = [];
    nodeAttrs = [
      { target = ["autogroup:admin"]; attr = ["funnel"]; }
      { target = ["tag:iot"]; attr = ["randomize-client-port"]; }
    ];
  };
}
