from __future__ import annotations

__all__ = [
    "APP_NAME",
    "VERSION",
    "DEFAULT_STATE_DIR",
    "PROVIDER_VERSION",
    "LAST_APPLY_FILE",
    "BACKUP_DIR",
    "TERRAFORM_DIR",
    "MAIN_TF_FILE",
    "KEYS_TF_FILE",
    "DATA_TF_FILE",
    "DNS_TF_FILE",
    "ACL_TF_FILE",
    "STATE_FILE",
    "AUTH_KEYS_FILE",
    "LOCAL_PROVIDER_VERSION",
]

APP_NAME = "tailscale-manager"
VERSION = "0.5.2"
DEFAULT_STATE_DIR = "/var/lib/tailscale-manager"
PROVIDER_VERSION = "~> 0.29"
LAST_APPLY_FILE = "last-apply.json"
BACKUP_DIR = "backups"
TERRAFORM_DIR = ".terraform"
MAIN_TF_FILE = "main.tf.json"
KEYS_TF_FILE = "keys.tf.json"
DATA_TF_FILE = "data.tf.json"
DNS_TF_FILE = "dns.tf.json"
ACL_TF_FILE = "acl.tf.json"
STATE_FILE = "terraform.tfstate"
AUTH_KEYS_FILE = "auth-keys.json"
LOCAL_PROVIDER_VERSION = "~> 2.4"
