from uuid import UUID

import pytest

from loreforge.settings import AuthProvider, SettingsError, load_settings

USER_ID = UUID("00000000-0000-0000-0000-000000000111")


def test_api_key_auth_settings_parse_configured_credentials() -> None:
    settings = load_settings(
        {
            "LOREFORGE_AUTH_PROVIDER": "api_key",
            "LOREFORGE_AUTH_API_KEYS": f"{USER_ID}:secret-key:Demo User",
        }
    )

    assert settings.auth.provider is AuthProvider.API_KEY
    assert len(settings.auth.api_keys) == 1
    assert settings.auth.api_keys[0].user_id == USER_ID
    assert settings.auth.api_keys[0].api_key == "secret-key"
    assert settings.auth.api_keys[0].display_name == "Demo User"


def test_api_key_auth_requires_credentials_when_enabled() -> None:
    with pytest.raises(SettingsError, match="LOREFORGE_AUTH_API_KEYS"):
        load_settings({"LOREFORGE_AUTH_PROVIDER": "api_key"})


@pytest.mark.parametrize(
    "value",
    [
        "not-a-uuid:secret",
        f"{USER_ID}",
        f"{USER_ID}: ",
    ],
)
def test_api_key_auth_rejects_invalid_credentials(value: str) -> None:
    with pytest.raises(SettingsError, match="LOREFORGE_AUTH_API_KEYS"):
        load_settings(
            {
                "LOREFORGE_AUTH_PROVIDER": "api_key",
                "LOREFORGE_AUTH_API_KEYS": value,
            }
        )


def test_demo_identity_settings_parse_without_credentials_in_source() -> None:
    settings = load_settings(
        {
            "LOREFORGE_AUTH_PROVIDER": "api_key",
            "LOREFORGE_AUTH_API_KEYS": f"{USER_ID}:secret-key:Demo User",
            "LOREFORGE_AUTH_DEMO_USER_IDS": str(USER_ID),
            "LOREFORGE_DEMO_ASK_RATE_LIMIT_REQUESTS": "3",
            "LOREFORGE_DEMO_ASK_RATE_LIMIT_WINDOW_SECONDS": "30",
        }
    )

    assert settings.auth.demo_user_ids == (USER_ID,)
    assert settings.auth.demo_ask_rate_limit_requests == 3
    assert settings.auth.demo_ask_rate_limit_window_seconds == 30


def test_demo_identity_settings_default_to_no_demo_users() -> None:
    settings = load_settings(
        {
            "LOREFORGE_AUTH_PROVIDER": "api_key",
            "LOREFORGE_AUTH_API_KEYS": f"{USER_ID}:secret-key:Normal User",
        }
    )

    assert settings.auth.demo_user_ids == ()
    assert settings.auth.demo_ask_rate_limit_requests == 10
    assert settings.auth.demo_ask_rate_limit_window_seconds == 60


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("LOREFORGE_AUTH_DEMO_USER_IDS", "not-a-uuid"),
        ("LOREFORGE_DEMO_ASK_RATE_LIMIT_REQUESTS", "0"),
        ("LOREFORGE_DEMO_ASK_RATE_LIMIT_WINDOW_SECONDS", "0"),
    ],
)
def test_demo_identity_settings_reject_invalid_values(name: str, value: str) -> None:
    with pytest.raises(SettingsError, match=name):
        load_settings(
            {
                "LOREFORGE_AUTH_PROVIDER": "api_key",
                "LOREFORGE_AUTH_API_KEYS": f"{USER_ID}:secret-key:Demo User",
                name: value,
            }
        )
