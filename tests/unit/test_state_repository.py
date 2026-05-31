from __future__ import annotations

from pathlib import Path

from tailscale_manager.repositories.state_repository import StateRepository


def test_read_state_returns_none_when_no_file(tmp_path: Path) -> None:
    repo = StateRepository(tmp_path)
    assert repo.read_state() is None


def test_read_state_parses_valid_tfstate(tmp_path: Path) -> None:
    state_file = tmp_path / "terraform.tfstate"
    state_file.write_text('{"version": 1, "resources": []}')
    repo = StateRepository(tmp_path)
    state = repo.read_state()
    assert state is not None
    assert state["version"] == 1


def test_get_managed_keys_empty_when_no_state(tmp_path: Path) -> None:
    repo = StateRepository(tmp_path)
    keys = repo.get_managed_keys()
    assert keys == []


def test_get_managed_keys_parses_instances(tmp_path: Path) -> None:
    state_file = tmp_path / "terraform.tfstate"
    state_file.write_text("""
    {
      "version": 1,
      "resources": [
        {
          "type": "tailscale_tailnet_key",
          "instances": [
            {
              "attributes": {
                "id": "k123",
                "description": "managed key",
                "tags": ["tag:infra"],
                "reusable": true,
                "ephemeral": false,
                "preauthorized": true,
                "revoked": false
              }
            }
          ]
        }
      ]
    }
    """)
    repo = StateRepository(tmp_path)
    keys = repo.get_managed_keys()
    assert len(keys) == 1
    assert keys[0].id == "k123"
    assert keys[0].description == "managed key"
    assert keys[0].tags == ["tag:infra"]
    assert keys[0].reusable is True
    assert keys[0].revoked is False


def test_get_managed_keys_skips_other_resource_types(tmp_path: Path) -> None:
    state_file = tmp_path / "terraform.tfstate"
    state_file.write_text("""
    {
      "version": 1,
      "resources": [
        {
          "type": "tailscale_device",
          "instances": [{"attributes": {"id": "d1"}}]
        }
      ]
    }
    """)
    repo = StateRepository(tmp_path)
    keys = repo.get_managed_keys()
    assert keys == []


def test_get_devices_empty_when_no_state(tmp_path: Path) -> None:
    repo = StateRepository(tmp_path)
    devices = repo.get_devices()
    assert devices == []


def test_get_devices_parses_instances(tmp_path: Path) -> None:
    state_file = tmp_path / "terraform.tfstate"
    state_file.write_text("""
    {
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
                    "user": "admin@example.com"
                  }
                ]
              }
            }
          ]
        }
      ]
    }
    """)
    repo = StateRepository(tmp_path)
    devices = repo.get_devices()
    assert len(devices) == 1
    assert devices[0].id == "d1"
    assert devices[0].hostname == "node1"
    assert devices[0].addresses == ["100.1.2.3"]
    assert devices[0].tags == ["tag:server"]
    assert devices[0].user == "admin@example.com"


def test_get_devices_skips_non_device_resources(tmp_path: Path) -> None:
    state_file = tmp_path / "terraform.tfstate"
    state_file.write_text("""
    {
      "version": 1,
      "resources": [
        {
          "type": "tailscale_device",
          "instances": [{"attributes": {"id": "d1"}}]
        },
        {
          "type": "tailscale_tailnet_key",
          "instances": [{"attributes": {"id": "k1"}}]
        }
      ]
    }
    """)
    repo = StateRepository(tmp_path)
    devices = repo.get_devices()
    assert devices == []


def test_get_devices_skips_non_data_resource(tmp_path: Path) -> None:
    """A resource (not data source) of type tailscale_devices should be skipped."""
    state_file = tmp_path / "terraform.tfstate"
    state_file.write_text("""
    {
      "version": 1,
      "resources": [
        {
          "type": "tailscale_devices",
          "instances": [{"attributes": {"devices": []}}]
        }
      ]
    }
    """)
    repo = StateRepository(tmp_path)
    devices = repo.get_devices()
    assert devices == []


def test_read_last_apply_returns_none_when_no_file(tmp_path: Path) -> None:
    repo = StateRepository(tmp_path)
    assert repo.read_last_apply() is None


def test_write_and_read_last_apply(tmp_path: Path) -> None:
    repo = StateRepository(tmp_path)
    data = {"timestamp": "2024-01-01T00:00:00", "result": "ok"}
    repo.write_last_apply(data)
    result = repo.read_last_apply()
    assert result is not None
    assert result["result"] == "ok"
    assert result["timestamp"] == "2024-01-01T00:00:00"
