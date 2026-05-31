from __future__ import annotations


def build_dns_config(
    nameservers: list[str],
    magic_dns: bool,
    split_nameservers: dict[str, list[str]],
) -> dict:
    if not nameservers and not magic_dns and not split_nameservers:
        return {}

    cfg: dict[str, dict] = {}

    if nameservers:
        cfg["tailscale_dns_nameservers"] = {
            "global": {"nameservers": nameservers}
        }

    cfg["tailscale_dns_preferences"] = {
        "prefs": {"magic_dns": magic_dns}
    }

    for domain, ns_list in split_nameservers.items():
        safe_name = domain.replace(".", "_").replace("-", "_")
        cfg.setdefault("tailscale_dns_split_nameservers", {})[safe_name] = {
            "domain": domain,
            "nameservers": ns_list,
        }

    return {"resource": cfg}
