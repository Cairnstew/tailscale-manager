# Multi-machine setups

When running `tailscale-manager` on multiple machines, the default
local-only state causes each machine to create its own Terraform state and,
consequently, its own auth key. This document covers the problem and the
two primary solutions.

## The problem

By default, `tailscale-manager` stores `terraform.tfstate` in a local
directory (`/var/lib/tailscale-manager`). Each machine that runs
`tailscale-manager apply` creates its own independent set of managed keys.

If you have N machines all configured identically, you get N auth keys
instead of one. This is wasteful, harder to audit, and means key rotation
requires updating N consumers instead of one.

## Option A: single key-manager host

Designate **one** machine to run `tailscale-manager apply`. All other
machines consume the auth key value via `tailscale-manager output`.

### Workflow

1. On the manager host: `tailscale-manager output` prints the raw key to
   stdout. Use this with a secrets manager (agenix, sops) to distribute
   the key to other machines.
2. On consumer machines: `tailscale-manager output --output-file <path>`
   reads the key from a shared, read-only copy of the state file, or the
   key secret is delivered via agenix.

### Pros and cons

- **Pros**: simple, no shared infrastructure, works with or without NixOS.
- **Cons**: the manager host is a single point of failure for key
  creation/rotation; consumers must have the key delivered out of band.

### agenix example

```nix
# On the manager host — extract the key and encrypt it
# $ tailscale-manager output | age -e -R <pubkey> > secrets/ts-key.age

# On consumer machines, decrypt at boot:
age.secrets.ts-key = {
  file = ./secrets/ts-key.age;
};
```

## Option B: shared remote state

Configure `stateBackend` so all machines share a single Terraform state
file and therefore a single managed auth key.

### S3 example

```nix
services.tailscale-manager = {
  enable = true;
  tailnet = "-";
  credentialsFile = "/run/secrets/tailscale-oauth";
  stateBackend = {
    s3 = {
      bucket = "my-tailscale-tfstate";
      key = "tailscale/terraform.tfstate";
      region = "us-east-1";
    };
  };
};
```

When `stateBackend` is set, the generated `main.tf.json` includes a
`terraform.backend` block. Every machine that runs `tailscale-manager apply`
reads and writes the same state file — they all manage the same keys.

### Required IAM permissions

For the S3 backend, the machine must have credentials with at least:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::my-tailscale-tfstate",
        "arn:aws:s3:::my-tailscale-tfstate/*"
      ]
    }
  ]
}
```

Other backends (GCS, Azure RM, etc.) have similar requirements. See the
[Terraform backend docs](https://developer.hashicorp.com/terraform/language/settings/backends/configuration)
for details.

### Migrating from local state

If a local `terraform.tfstate` already exists when a remote backend is
configured, `tailscale-manager` will refuse to run. Migrate with:

```bash
terraform state push
rm /var/lib/tailscale-manager/terraform.tfstate
```

### Pros and cons

- **Pros**: single source of truth; all machines manage the same keys; no
  out-of-band secret distribution needed.
- **Cons**: requires shared infrastructure (S3 bucket, etc.); all machines
  need credentials for the backend; locking is backend-dependent.

## Key rotation

When `recreateIfInvalid = "always"` is set (the default), Terraform
replaces an expired key on the next `apply`. The new key value is stored
in the shared state.

**State file consumers** (including `tailscale-manager output`) will return
the new value on the next read. If you use `--output-file`, the file is
**not** updated automatically — you must re-run `tailscale-manager output
--output-file <path>` after rotation.

For automatic key distribution after rotation, consider:

- A systemd timer that runs `tailscale-manager output --output-file <path>`
  periodically.
- A credential watcher pattern (similar to the built-in
  `watchCredentials` option) that triggers on state file changes.
- CI/CD that re-runs the output command as a post-apply step.

## CI/CD pattern

In CI/CD pipelines where a build machine needs the auth key but should
never run `tailscale-manager apply`:

```yaml
steps:
  - name: Apply
    run: tailscale-manager apply

  - name: Extract key
    run: |
      KEY=$(tailscale-manager output)
      echo "::add-mask::$KEY"
      echo "TS_AUTH_KEY=$KEY" >> $GITHUB_ENV

  - name: Build
    run: ./build.sh  # consumes $TS_AUTH_KEY
```

The build step uses the key from the environment. The `output` command is
pure-read — it never calls `terraform init` or modifies state.
