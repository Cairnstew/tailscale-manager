{ pkgs, pythonSet, workspace, pyproject-nix }:

let
  inherit (pkgs.callPackages pyproject-nix.build.util { }) mkApplication;
in

mkApplication {
  venv = pythonSet.mkVirtualEnv "app-env" workspace.deps.default;
  package = pythonSet."tailscale-manager";
}
