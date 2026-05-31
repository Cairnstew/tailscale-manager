from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from tailscale_manager.cli import app

runner = CliRunner()


def test_devices_no_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TAILSCALE_TAILNET", "test.ts.net")
    monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
    result = runner.invoke(app, ["devices"])
    assert result.exit_code == 0
    assert "No devices discovered" in result.stdout


def test_devices_json_no_state(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TAILSCALE_TAILNET", "test.ts.net")
    monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))
    result = runner.invoke(app, ["devices", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data == []


def test_devices_json_with_devices(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TAILSCALE_TAILNET", "test.ts.net")
    monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))

    state_file = tmp_path / "terraform.tfstate"
    state_file.write_text(json.dumps({
        "version": 1,
        "resources": [
            {
                "type": "tailscale_devices",
                "mode": "data",
                "instances": [
                    {
                        "attributes": {
                            "devices": [
                                {
                                    "addresses": ["100.1.2.3"],
                                    "hostname": "node1",
                                    "id": "d1",
                                    "name": "node1.ts.net",
                                    "node_id": "n1",
                                    "tags": ["tag:server"],
                                    "user": "admin@example.com",
                                },
                                {
                                    "addresses": ["100.1.2.4"],
                                    "hostname": "node2",
                                    "id": "d2",
                                    "name": "node2.ts.net",
                                    "node_id": "n2",
                                    "tags": [],
                                    "user": "",
                                },
                            ]
                        }
                    }
                ],
            }
        ],
    }))

    result = runner.invoke(app, ["devices", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 2
    assert data[0]["hostname"] == "node1"
    assert data[0]["id"] == "d1"
    assert data[1]["hostname"] == "node2"


def test_devices_text_with_devices(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TAILSCALE_TAILNET", "test.ts.net")
    monkeypatch.setenv("TAILSCALE_MANAGER_STATE_DIR", str(tmp_path))

    state_file = tmp_path / "terraform.tfstate"
    state_file.write_text(json.dumps({
        "version": 1,
        "resources": [
            {
                "type": "tailscale_devices",
                "mode": "data",
                "instances": [
                    {
                        "attributes": {
                            "devices": [
                                {
                                    "addresses": ["100.1.2.3"],
                                    "hostname": "node1",
                                    "id": "d1",
                                    "name": "node1.ts.net",
                                    "node_id": "n1",
                                    "tags": ["tag:server"],
                                    "user": "admin@example.com",
                                },
                            ]
                        }
                    }
                ],
            }
        ],
    }))

    result = runner.invoke(app, ["devices"])
    assert result.exit_code == 0
    assert "Discovered 1 device(s)" in result.stdout
    assert "node1" in result.stdout
    assert "d1" in result.stdout
