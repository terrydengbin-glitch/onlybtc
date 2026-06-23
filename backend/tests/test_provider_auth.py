from onlybtc.sources.provider_auth import (
    _safe_url,
    auth_status,
    get_provider_auth_config,
    provider_auth_paths,
)


def test_glassnode_auth_config_exists() -> None:
    config = get_provider_auth_config("glassnode")

    assert config.provider_id == "glassnode"
    assert config.login_url.startswith("https://")
    assert "log in" in config.logged_out_markers


def test_provider_auth_paths_are_under_ignored_artifacts_dir() -> None:
    auth_paths = provider_auth_paths("glassnode")

    assert "playwright-artifacts" in str(auth_paths.auth_dir)
    assert auth_paths.profile_dir.name == "profile"
    assert auth_paths.storage_state_path.name == "storage-state.json"


def test_missing_auth_status_is_safe() -> None:
    status = auth_status("glassnode")

    assert status["provider_id"] == "glassnode"
    assert "configured" in status
    assert "message" in status


def test_safe_url_strips_query_and_fragment() -> None:
    url = "https://accounts.google.com/signin?token=secret#fragment"

    assert _safe_url(url) == "https://accounts.google.com/signin"
