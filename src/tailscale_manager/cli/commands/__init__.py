from tailscale_manager.cli.app import app
from tailscale_manager.cli.commands import auth_keys, doctor, lifecycle, status, version


def register_all() -> None:
    lifecycle.register(app)
    status.register(app)
    doctor.register(app)
    version.register(app)
    auth_keys.register(app)
