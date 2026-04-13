import pytest
from fastapi.testclient import TestClient
from sqlmodel import select
from unittest.mock import patch

from app.api.dependencies import get_current_api_user
from app.common.alchemy import get_session
from app.db.models import ApiKey
from app.extensions.honeypot.blueprint import HoneypotChannel, HoneypotSettings
from app.main_api import app

# All tests in this file are integration tests (FastAPI TestClient, DB sessions).
pytestmark = pytest.mark.integration


@pytest.fixture
def auth_cookies():
    # Simulate an authenticated session by posting to the login endpoint.
    # Mocking auth is tricky without knowing the exact test auth setup in powercord,
    # but based on common Fasthtml setups, session data is stored in a signed cookie.
    pass


def test_honeypot_update_settings(session):
    guild_id = 998

    # Needs auth in real scenario, assuming tests bypass or client is mocked appropriately.
    # The tests in powercord (like test_admin_routes) often use just the client. Let's try it.

    # Setup fake API Key directly in test Database
    test_key = "test_bearer_token"
    api_key = ApiKey(key=test_key, name="system_test", is_active=True, scopes='["global"]')
    session.add(api_key)
    session.commit()

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session

    with patch("app.api.dependencies.init_connection_engine", return_value=session.get_bind()), \
         patch("app.api.dependencies.get_or_create_internal_key", return_value="__not_the_test_key__"):
        with TestClient(app) as client:
            response = client.post(
                f"/honeypot/config/{guild_id}/settings",
                headers={"Authorization": f"Bearer {test_key}"},
                data={"time_limit": 120, "log_channel_id": 0, "shame_mode": False},
                follow_redirects=False,
            )

    # Check that it redirects or returns success
    print("STATUS", response.status_code)
    try:
        print("JSON", response.json())
    except:
        print("TEXT", response.text)
    assert response.status_code in [200, 302, 303]

    # Check DB
    settings = session.exec(select(HoneypotSettings).where(HoneypotSettings.guild_id == guild_id)).first()
    assert settings is not None
    assert settings.time_limit == 120
    assert settings.log_channel_id is None
    assert settings.shame_mode is False

    app.dependency_overrides.clear()


def test_honeypot_remove_channel(session):
    guild_id = 999
    chan_id = 888

    # Setup
    session.add(HoneypotChannel(guild_id=guild_id, channel_id=chan_id))
    session.commit()

    # Setup fake API Key directly in test Database
    test_key_2 = "test_bearer_token_2"
    api_key_2 = ApiKey(key=test_key_2, name="system_test_2", is_active=True, scopes='["global"]')
    session.add(api_key_2)
    session.commit()

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session

    with patch("app.api.dependencies.init_connection_engine", return_value=session.get_bind()), \
         patch("app.api.dependencies.get_or_create_internal_key", return_value="__not_the_test_key__"):
        with TestClient(app) as client:
            response = client.post(
                f"/honeypot/config/{guild_id}/remove_channel",
                headers={"Authorization": f"Bearer {test_key_2}"},
                data={"channel_id": chan_id},
                follow_redirects=False,
            )

    print("STATUS", response.status_code)
    try:
        print("JSON", response.json())
    except:
        print("TEXT", response.text)
    assert response.status_code in [200, 302, 303]

    # Check DB
    channel = session.exec(
        select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id, HoneypotChannel.channel_id == chan_id)
    ).first()
    assert channel is None

    app.dependency_overrides.clear()
