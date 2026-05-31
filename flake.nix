{
  description = "Tailscale NixOS Manager — manage auth keys via Terraform";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      uv2nix,
      pyproject-nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;

      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

      overlay = workspace.mkPyprojectOverlay {
        sourcePreference = "wheel";
      };

      editableOverlay = workspace.mkEditablePyprojectOverlay {
        root = "$REPO_ROOT";
      };

      pythonSets = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3;

          baseSet = pkgs.callPackage pyproject-nix.build.packages {
            inherit python;
          };

          pythonSet = baseSet.overrideScope (
            lib.composeManyExtensions [
              pyproject-build-systems.overlays.wheel
              overlay
            ]
          );

          editablePythonSet = pythonSet.overrideScope editableOverlay;
        in
        {
          inherit pythonSet editablePythonSet python pkgs;
        }
      );
    in
    {
      packages = forAllSystems (
        system:
        let p = pythonSets.${system}; in
        {
          default = p.pkgs.callPackage ./nix/default.nix {
            inherit (p) pythonSet pkgs;
            inherit workspace pyproject-nix;
          };
        }
      );

      devShells = forAllSystems (
        system:
        let p = pythonSets.${system}; in
        p.pkgs.callPackage ./nix/devshell.nix {
          inherit (p) pythonSet editablePythonSet python pkgs;
          inherit workspace;
        }
      );

      overlays.default = final: prev: {
        tailscale-manager = pythonSets.${prev.stdenv.hostPlatform.system}.pythonSet."tailscale-manager";
      };

      nixosModules.default = { pkgs, ... }: {
        imports = [ ./nix/module.nix ];
        services.tailscale-manager.package = lib.mkDefault self.packages.${pkgs.system}.default;
      };

      homeManagerModules.default = { pkgs, ... }: {
        imports = [ ./nix/home-module.nix ];
        homeManagerModules.tailscale-manager.package = lib.mkDefault self.packages.${pkgs.system}.default;
      };

      checks = forAllSystems (
        system:
        let p = pythonSets.${system}; in
        p.pkgs.callPackage ./nix/checks.nix {
          inherit lib system;
          pythonSet = p.pythonSet;
        }
      );
    };
}
