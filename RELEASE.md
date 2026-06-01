# Release process

## Before you cut

```bash
# 1. Bump version in both places
pyproject.toml          # [project].version
src/tailscale_manager/core/constants.py  # VERSION

# 2. Regenerate lock if dependencies changed
# nix develop .#bootstrap   # if uv isn't available
# uv lock

# 3. Verify everything
pytest tests/unit/ -v
nix build .#default
nix flake check --no-build   # ignore overrideDerivation noise
```

## Cut the release

```bash
git add -A
git commit -m "chore: bump version to x.y.z"
git tag -a vx.y.z -m "vx.y.z — short description"
git push origin master
git push origin vx.y.z
```

## What happens next

The `.github/workflows/release.yml` workflow triggers on tag push `v*`:

1. Builds via Nix
2. Publishes to PyPI (if CLI is detected — gated behind `has_cli`)
3. Creates a GitHub release with changelog

No manual PyPI or GitHub steps required.

## Post-release

Confirm the release appeared:

```bash
# PyPI
pip install tailscale-manager==x.y.z

# GitHub releases page — check the tag
```

If CI fails, fix the issue, bump the patch version, and re-tag.
