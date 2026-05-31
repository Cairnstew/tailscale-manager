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
