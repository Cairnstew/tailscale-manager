from __future__ import annotations

from tailscale_manager.services.features.base import BaseFeatureBuilder


__all__ = [
    "DnsFeatureBuilder",
    "build_dns_config",
]


class DnsFeatureBuilder(BaseFeatureBuilder):
    def __init__(
        self,
        nameservers: list[str],
        magic_dns: bool,
        split_nameservers: dict[str, list[str]],
    ) -> None:
        self._nameservers = nameservers
        self._magic_dns = magic_dns
        self._split_nameservers = split_nameservers

    def build(self) -> dict:
        if not self._nameservers and not self._magic_dns and not self._split_nameservers:
            return {}

        cfg: dict[str, dict] = {}

        if self._nameservers:
            cfg["tailscale_dns_nameservers"] = {
                "global": {"nameservers": self._nameservers}
            }

        cfg["tailscale_dns_preferences"] = {
            "prefs": {"magic_dns": self._magic_dns}
        }

        for domain, ns_list in self._split_nameservers.items():
            safe_name = domain.replace(".", "_").replace("-", "_")
            cfg.setdefault("tailscale_dns_split_nameservers", {})[safe_name] = {
                "domain": domain,
                "nameservers": ns_list,
            }

        return {"resource": cfg}


def build_dns_config(
    nameservers: list[str],
    magic_dns: bool,
    split_nameservers: dict[str, list[str]],
) -> dict:
    return DnsFeatureBuilder(
        nameservers=nameservers,
        magic_dns=magic_dns,
        split_nameservers=split_nameservers,
    ).build()
