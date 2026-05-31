{ pkgs, pythonSet, editablePythonSet, workspace, python }:

let
  virtualenv = editablePythonSet.mkVirtualEnv "dev-env" workspace.deps.all;
in

{
  default = pkgs.mkShell {
    packages = [
      virtualenv
      pkgs.uv
    ];

    env = {
      UV_NO_SYNC = "1";
      UV_PYTHON = "${python.interpreter}";
      UV_PYTHON_DOWNLOADS = "never";
    };

    shellHook = ''
      unset PYTHONPATH
      export REPO_ROOT=$(git rev-parse --show-toplevel)
    '';
  };

  bootstrap = pkgs.mkShell {
    packages = [
      pkgs.python3
      pkgs.uv
    ];
  };
}
