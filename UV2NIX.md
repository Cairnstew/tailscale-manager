# uv2nix Reference

> uv2nix takes a `uv` workspace and generates Nix derivations dynamically using pure Nix code.
> Heavily based on [`pyproject.nix`](https://pyproject-nix.github.io/pyproject.nix).

**Docs:** https://pyproject-nix.github.io/uv2nix/introduction.html
**Repo:** https://github.com/pyproject-nix/uv2nix

---

## Core Concept

uv's `uv.lock` + `pyproject.toml` → pure-Nix overlay → `pyproject.nix` builders → derivations.

No import-from-derivation for production builds. Editable packages for dev shells.

---

## Quick Reference

| Step | Function / Snippet | Purpose |
|---|---|---|
| Pick Python | `pyproject-nix.lib.util.filterPythonInterpreters` | Auto-detect from `requires-python` |
| Base set | `pkgs.callPackage pyproject-nix.build.packages { inherit python; }` | Creates builder infrastructure (no packages yet) |
| Load workspace | `uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; }` | Discovers & parses all member projects |
| Generate overlay | `workspace.mkPyprojectOverlay { sourcePreference = "wheel"; }` | Turns `uv.lock` into an overlay for pyproject.nix |
| Editable overlay | `workspace.mkEditablePyprojectOverlay { root = "$REPO_ROOT"; }` | For dev shells — points to source tree |
| Build systems | `pyproject-build-systems.overlays.wheel` (or `.sdist`) | Provides build dependencies not in `uv.lock` |
| Compose set | `pythonBase.overrideScope (lib.composeManyExtensions [ ... overlays ... ])` | Glue it all together |
| Virtual env | `pythonSet.mkVirtualEnv "name" workspace.deps.all` | Aggregate packages into a venv |
| Package app | `mkApplication { venv = ...; package = ...; }` | Wrap venv hiding Python internals |
| Dev shell | `pkgs.mkShell { packages = [ virtualenv pkgs.uv ]; }` | Interactive development |

---

## sourcePreference

| Value | Meaning |
|---|---|
| `"wheel"` | Prefer binary wheels (more likely to "just work") |
| `"sdist"` | Prefer building from source (needs more overrides) |

Can be overridden per-package: `prev.pkg.override { sourcePreference = "sdist"; }`.

---

## Dependency Presets (workspace.deps)

| Preset | Content |
|---|---|
| `.default` | No optional-deps or dependency-groups |
| `.optionals` | All optional-dependencies enabled |
| `.groups` | All dependency-groups enabled |
| `.all` | Everything |

---

## Dev Shell Setup

```nix
pkgs.mkShell {
  packages = [ virtualenv pkgs.uv ];
  env = {
    UV_NO_SYNC         = "1";          # Don't let uv manage venv
    UV_PYTHON          = python.interpreter;  # Use Nix Python
    UV_PYTHON_DOWNLOADS = "never";     # Don't download managed interpreters
  };
  shellHook = ''
    unset PYTHONPATH
    export REPO_ROOT=$(git rev-parse --show-toplevel)
  '';
}
```

- `unset PYTHONPATH`: avoid side effects from Nixpkgs Python builders
- `REPO_ROOT`: tells editable packages where the source tree is

---

## Source Filtering

**Don't** filter at workspace root level (causes IFD + breaks editables).

**Do** filter per-package via overlay:

```nix
final: prev: {
  mypkg = prev.mypkg.overrideAttrs (old: {
    src = lib.fileset.toSource {
      root = ./.;
      fileset = lib.fileset.unions [
        ./pyproject.toml
        ./src/mypkg/__init__.py
      ];
    };
  });
}
```

---

## Overriding Packages

### Sdist (source builds)

```nix
final: prev: {
  pyzmq = prev.pyzmq.overrideAttrs (old: {
    buildInputs = (old.buildInputs or []) ++ [ pkgs.zeromq ];
    nativeBuildInputs = old.nativeBuildInputs ++ [
      (final.resolveBuildSystem { cmake = []; ninja = []; })
    ];
  });
}
```

### Wheels (binary)

```nix
final: prev: {
  numba = prev.numba.overrideAttrs (old: {
    buildInputs = (old.buildInputs or []) ++ [ pkgs.tbb_2021_11 ];
  });
}
```

---

## Shipping Applications

```nix
inherit (pkgs.callPackages pyproject-nix.build.util { }) mkApplication;

mkApplication {
  venv   = pythonSet.mkVirtualEnv "app-env" workspace.deps.default;
  package = pythonSet.hello-world;
}
```

Hides venv internals (interpreter, activation scripts, pyvenv.cfg) — only ships binaries, man pages, etc.

---

## Advanced Build Systems (Editables)

For `meson-python`, `cython`, etc. — add `build-editable` hook:

```nix
pkgs.mkShell {
  packages = [ virtualenv pkgs.uv pyproject-nix.packages.${system}.build-editable ];
  shellHook = ''
    unset PYTHONPATH
    export REPO_ROOT=$(git rev-parse --show-toplevel)
    build-editable   # re-runs build for side effects (.so's etc.)
  '';
}
```

---

## Cross Compilation

Build systems must be overridden twice (build host + target host): use `pythonPkgsBuildHost.overrideScope` in the overlay.

---

## Platform Quirks

**macOS SDK version** — override in package set creation:

```nix
pkgs.callPackage pyproject-nix.build.packages {
  inherit python;
  stdenv = pkgs.stdenv.override {
    targetPlatform = pkgs.stdenv.targetPlatform // {
      darwinSdkVersion = "15.1";
    };
  };
}
```

**Linux kernel version** — in `mkPyprojectOverlay`:

```nix
workspace.mkPyprojectOverlay {
  sourcePreference = "wheel";
  environ = { platform_release = "5.10.65"; };
}
```

---

## Conflicting Dependencies

```nix
workspace.mkPyprojectOverlay {
  sourcePreference = "wheel";
  dependencies = {
    hello-world = [ "extra1" ];
  };
}
```

---

## Inline Script Metadata

Per-script uv2nix from PEP-723 locked scripts. Uses `uv2nix.lib.scripts.loadScript`. See [docs](https://pyproject-nix.github.io/uv2nix/usage/inline-metadata.html).

---

## Older nixpkgs (<=24.11)

Needs `uv` >= 0.5.7 via overlay:

```nix
import nixpkgs {
  overlays = [ (final: prev: { uv = inputs.uv2nix.packages.${system}.uv-bin; }) ];
}
```

---

## Flake Inputs Template

```nix
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
```

---

## Key Commands

| Command | What it does |
|---|---|
| `uv init --app --package` | Bootstrap a new uv project |
| `uv lock` | Generate/lock `uv.lock` |
| `uv add <pkg>` | Add a dependency |
| `nix build .#<name>` | Build a package |
| `nix develop` | Enter uv2nix dev shell (requires uv.lock) |
| `nix develop .#bootstrap` | Enter bootstrap shell (python + uv only, no uv.lock needed) |
| `nix flake init --template github:pyproject-nix/uv2nix#hello-world` | Use official template |

## Project Structure & Package Layout

uv2nix doesn't prescribe a specific project layout — it follows standard Python packaging conventions and what `uv init` generates.

### `uv init` default (src layout)

```
uv init --app --package .
```
produces:
```
├── pyproject.toml
├── src/
│   └── <package_name>/       # underscored: e.g. uv2nix_template/
│       └── __init__.py
└── uv.lock
```

### Flat layout (this template)

```
├── pyproject.toml
├── <package_name>/           # underscored: e.g. uv2nix_template/
│   └── __init__.py
└── uv.lock
```

### Name conventions

| Field | Format | Example |
|---|---|---|
| `[project].name` in pyproject.toml | Hyphens | `uv2nix-template` |
| Python import directory | Underscores | `uv2nix_template/` |
| Nix overlay attribute in flake.nix | Hyphens | `pythonSet."uv2nix-template"` |

Setuptools discovers packages using `find` by default (flat or src layout). To switch to a `src/` layout, add to `pyproject.toml`:

```toml
[tool.setuptools.packages.find]
where = ["src"]
```

See [setuptools docs](https://setuptools.pypa.io/en/latest/userguide/package_discovery.html) and [uv project docs](https://docs.astral.sh/uv/reference/cli/#uv-init) for more.

## Bootstrap devShell

A `.#bootstrap` devShell is provided that doesn't depend on uv2nix at all — just `python3` and `uv` from nixpkgs. Use it when you don't have a `uv.lock` yet:

```bash
nix develop .#bootstrap
uv init --app --package
uv add <dependencies>
uv lock
# Now the default devShell is usable
```

---

## Links

- [uv2nix docs](https://pyproject-nix.github.io/uv2nix/)
- [pyproject.nix docs](https://pyproject-nix.github.io/pyproject.nix/)
- [build-system-pkgs](https://github.com/pyproject-nix/build-system-pkgs)
- [uv docs](https://docs.astral.sh/uv/)
- [uv2nix_hammer_overrides](https://github.com/TyberiusPrime/uv2nix_hammer_overrides/) — third-party overrides
- [pyproject.nix overrides](https://pyproject-nix.github.io/pyproject.nix/builders/overriding.html)
- [pyproject.nix override hacks](https://pyproject-nix.github.io/pyproject.nix/builders/hacks.html)
