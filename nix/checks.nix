{ pkgs, lib, pythonSet, system }:

let
  pkg = pythonSet."tailscale-manager";
in

{

  tailscale-manager-build = pkg;

  tailscale-manager-venv = pythonSet.mkVirtualEnv "app-env" { tailscale-manager = [ ]; };

}
