import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from app.common.alchemy import get_session
from app.extensions.honeypot.blueprint import HoneypotChannel, HoneypotSettings
from app.main_api import app


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

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        response = client.post(
            f"/honeypot/config/{guild_id}/settings",
            data={"time_limit": 120, "log_channel_id": 0, "shame_mode": False},
            follow_redirects=False,
        )

    # Check that it redirects or returns success
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

    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        response = client.post(
            f"/honeypot/config/{guild_id}/remove_channel", data={"channel_id": chan_id}, follow_redirects=False
        )

    assert response.status_code in [200, 302, 303]

    # Check DB
    channel = session.exec(
        select(HoneypotChannel).where(HoneypotChannel.guild_id == guild_id, HoneypotChannel.channel_id == chan_id)
    ).first()
    assert channel is None

    app.dependency_overrides.clear()
