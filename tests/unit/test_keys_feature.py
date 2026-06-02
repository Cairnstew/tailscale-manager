from __future__ import annotations

from tailscale_manager.services.features.keys import (
    _sanitize_resource_name,
    build_keys_config,
)


class TestSanitizeResourceName:
    def test_hyphens(self) -> None:
        assert _sanitize_resource_name("ci-key") == "ci_key"

    def test_dots(self) -> None:
        assert _sanitize_resource_name("my.key.name") == "my_key_name"

    def test_numbers(self) -> None:
        assert _sanitize_resource_name("key123") == "key123"

    def test_special_chars(self) -> None:
        assert _sanitize_resource_name("key@name!") == "key_name_"

    def test_already_valid(self) -> None:
        assert _sanitize_resource_name("valid_name") == "valid_name"

    def test_multiple_hyphens(self) -> None:
        assert _sanitize_resource_name("a-b-c") == "a_b_c"

    def test_leading_digit(self) -> None:
        assert _sanitize_resource_name("123abc") == "_123abc"

    def test_leading_digit_with_hyphen(self) -> None:
        result = _sanitize_resource_name("1-ci-key")
        assert result == "_1_ci_key"
        assert result[0].isdigit() is False


class TestBuildKeysConfigExports:
    def test_no_exports(self) -> None:
        result = build_keys_config(
            tags=["tag:test"],
            recreate_if_invalid="always",
        )
        assert "local_sensitive_file" not in result.get("resource", {})

    def test_empty_exports(self) -> None:
        result = build_keys_config(
            tags=["tag:test"],
            recreate_if_invalid="always",
            auth_key_exports={},
        )
        assert "local_sensitive_file" not in result.get("resource", {})

    def test_none_exports(self) -> None:
        result = build_keys_config(
            tags=["tag:test"],
            recreate_if_invalid="always",
            auth_key_exports=None,
        )
        assert "local_sensitive_file" not in result.get("resource", {})

    def test_single_export(self) -> None:
        result = build_keys_config(
            tags=["tag:test"],
            recreate_if_invalid="always",
            auth_key_exports={
                "ci-key": {
                    "path": "/tmp/ci-key",
                    "owner": "root",
                    "group": "root",
                    "mode": "0600",
                },
            },
        )
        resource = result["resource"]
        assert "local_sensitive_file" in resource
        lsf = resource["local_sensitive_file"]
        assert "key_ci_key" in lsf
        assert lsf["key_ci_key"]["content"] == "${tailscale_tailnet_key.ci_key.key}"
        assert lsf["key_ci_key"]["filename"] == "/tmp/ci-key"
        assert lsf["key_ci_key"]["file_permission"] == "0600"

    def test_multiple_exports(self) -> None:
        result = build_keys_config(
            tags=["tag:test"],
            recreate_if_invalid="always",
            auth_key_exports={
                "ci-key": {
                    "path": "/tmp/ci-key",
                    "owner": "root",
                    "group": "root",
                    "mode": "0600",
                },
                "server-key": {
                    "path": "/tmp/server-key",
                    "owner": "myuser",
                    "group": "mygroup",
                    "mode": "0640",
                },
            },
        )
        lsf = result["resource"]["local_sensitive_file"]
        assert "key_ci_key" in lsf
        assert "key_server_key" in lsf
        assert lsf["key_server_key"]["filename"] == "/tmp/server-key"
        assert lsf["key_server_key"]["file_permission"] == "0600"

    def test_export_path_matches_sanitized_tf_key(self) -> None:
        auth_keys = {
            "my-ci-key": {
                "description": "CI key",
                "tags": [],
            },
        }
        result = build_keys_config(
            tags=[],
            recreate_if_invalid="always",
            auth_keys=auth_keys,
            auth_key_exports={
                "my-ci-key": {
                    "path": "/tmp/my-ci-key",
                    "owner": "root",
                    "group": "root",
                    "mode": "0600",
                },
            },
        )
        resource = result["resource"]
        tf_key = resource["tailscale_tailnet_key"]
        assert "my_ci_key" in tf_key
        lsf = resource["local_sensitive_file"]
        assert lsf["key_my_ci_key"]["content"] == "${tailscale_tailnet_key.my_ci_key.key}"

    def test_export_leading_digit_sanitized(self) -> None:
        result = build_keys_config(
            tags=[],
            recreate_if_invalid="always",
            auth_key_exports={
                "123key": {
                    "path": "/tmp/123key",
                    "owner": "root",
                    "group": "root",
                    "mode": "0600",
                },
            },
        )
        lsf = result["resource"]["local_sensitive_file"]
        assert "key__123key" in lsf
        assert lsf["key__123key"]["content"] == "${tailscale_tailnet_key._123key.key}"

    def test_export_always_uses_0600_permission(self) -> None:
        result = build_keys_config(
            tags=[],
            recreate_if_invalid="always",
            auth_key_exports={
                "test-key": {
                    "path": "/tmp/test-key",
                    "owner": "myuser",
                    "group": "mygroup",
                    "mode": "0640",
                },
            },
        )
        lsf = result["resource"]["local_sensitive_file"]["key_test_key"]
        assert lsf["file_permission"] == "0600"
