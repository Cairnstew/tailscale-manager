{ pkgs, workspace, pyproject-build-systems, pyproject-nix, pythonSet }:

final: prev: {

  tailscale-manager = pythonSet."tailscale-manager";

  tailscale-manager-env = pythonSet.mkVirtualEnv "app-env" workspace.deps.default;

}
