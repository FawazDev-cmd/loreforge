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
