"""
Tests for OAuth login/signup and account linking
(/users/oauth/{provider}/authorize, /callback, /link, /oauth/linked,
DELETE /oauth/{provider}).

app.services.oauth_provider.exchange_code_and_fetch_profile is always
mocked — this is the module's own integration boundary with each
provider's HTTP API, and testing against real Google/Facebook endpoints
isn't feasible in a test suite. The actual URL-building it depends on is
covered directly in tests/test_oauth_provider.py without any mocking.

The state-token CSRF check runs against the test client's mocked Redis
(see tests/conftest.py's MockRedisClientInstance), exercising the same
setex/get/delete calls UserService makes against real Redis.
"""
from unittest.mock import AsyncMock, patch

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.oauth_account import OAuthAccount
from app.models.user import User
from app.services.oauth_provider import OAuthProfile


def _profile(**overrides) -> OAuthProfile:
    defaults = dict(
        provider_user_id="provider-uid-1",
        email="oauth_user@test.com",
        email_verified=True,
        name="OAuth User",
    )
    defaults.update(overrides)
    return OAuthProfile(**defaults)


def _get_state(client: TestClient, provider: str = "google") -> str:
    resp = client.get(f"/users/oauth/{provider}/authorize")
    assert resp.status_code == 200, resp.json()
    return resp.json()["state"]


def _callback(client: TestClient, provider: str, code: str, state: str):
    return client.post(f"/users/oauth/{provider}/callback", json={"code": code, "state": state})


def _register_verify_login(client: TestClient, db_session, email: str, password: str) -> dict:
    payload = {
        "email": email, "password": password,
        "first_name": "Pw", "last_name": "User", "phone": "0988800001",
    }
    client.post("/users/register", json=payload)
    resp = client.post("/users/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.json()
    return resp.json()


class TestAuthorize:
    def test_returns_a_url_and_state_for_google(self, client: TestClient):
        resp = client.get("/users/oauth/google/authorize")
        assert resp.status_code == 200, resp.json()
        assert "accounts.google.com" in resp.json()["authorization_url"]
        assert resp.json()["state"]

    def test_returns_a_url_and_state_for_facebook(self, client: TestClient):
        resp = client.get("/users/oauth/facebook/authorize")
        assert resp.status_code == 200, resp.json()
        assert "facebook.com" in resp.json()["authorization_url"]

    def test_rejects_an_unsupported_provider(self, client: TestClient):
        resp = client.get("/users/oauth/twitter/authorize")
        assert resp.status_code == 404


class TestOAuthLoginSignup:
    def test_creates_a_new_verified_user_on_first_login(self, client: TestClient, db_session: Session):
        state = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="new_oauth@test.com")
            resp = _callback(client, "google", "auth-code-1", state)

        assert resp.status_code == 200, resp.json()
        assert "access_token" in resp.json()

        db_session.expire_all()
        user = db_session.query(User).filter_by(email="new_oauth@test.com").first()
        assert user is not None
        assert user.is_verified is True
        assert user.has_password is False

        link = db_session.query(OAuthAccount).filter_by(user_id=user.id).first()
        assert link.provider == "google"
        assert link.provider_user_id == "provider-uid-1"

    def test_second_login_with_the_same_identity_reuses_the_same_user(
        self, client: TestClient, db_session: Session
    ):
        profile = _profile(email="repeat_oauth@test.com")
        state1 = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = profile
            _callback(client, "google", "code-a", state1)

        state2 = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = profile
            resp = _callback(client, "google", "code-b", state2)

        assert resp.status_code == 200, resp.json()
        db_session.expire_all()
        users = db_session.query(User).filter_by(email="repeat_oauth@test.com").all()
        assert len(users) == 1
        links = db_session.query(OAuthAccount).filter_by(provider_user_id="provider-uid-1").all()
        assert len(links) == 1

    def test_rejects_signup_with_an_unverified_email(self, client: TestClient, db_session: Session):
        state = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="unverified@test.com", email_verified=False)
            resp = _callback(client, "google", "code", state)

        assert resp.status_code == 400
        db_session.expire_all()
        assert db_session.query(User).filter_by(email="unverified@test.com").first() is None

    def test_auto_links_to_an_existing_verified_password_account_by_email(
        self, client: TestClient, db_session: Session
    ):
        _register_verify_login(client, db_session, "merge_me@test.com", "MergeMe123")
        db_session.expire_all()
        existing_user = db_session.query(User).filter_by(email="merge_me@test.com").first()

        state = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="merge_me@test.com", email_verified=True)
            resp = _callback(client, "google", "code", state)

        assert resp.status_code == 200, resp.json()
        db_session.expire_all()
        assert db_session.query(User).filter_by(email="merge_me@test.com").count() == 1
        link = db_session.query(OAuthAccount).filter_by(user_id=existing_user.id).first()
        assert link is not None and link.provider == "google"

    def test_rejects_auto_link_when_the_oauth_email_is_not_verified(
        self, client: TestClient, db_session: Session
    ):
        """Otherwise anyone could take over an existing account just by
        registering an OAuth identity under the victim's (unverified,
        provider-side) email address."""
        _register_verify_login(client, db_session, "takeover_target@test.com", "TargetPw123")

        state = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="takeover_target@test.com", email_verified=False)
            resp = _callback(client, "google", "code", state)

        assert resp.status_code == 409

    def test_rejects_an_invalid_state(self, client: TestClient, db_session: Session):
        resp = _callback(client, "google", "code", "not-a-real-state")
        assert resp.status_code == 400

    def test_state_is_single_use(self, client: TestClient, db_session: Session):
        state = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="onceonly@test.com")
            first = _callback(client, "google", "code", state)
            second = _callback(client, "google", "code", state)

        assert first.status_code == 200
        assert second.status_code == 400

    def test_mfa_enabled_account_gets_a_challenge_instead_of_tokens(
        self, client: TestClient, db_session: Session
    ):
        tokens = _register_verify_login(client, db_session, "mfa_oauth@test.com", "MfaOauth123")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        secret = client.post("/users/mfa/setup", headers=headers).json()["secret"]
        code = pyotp.TOTP(secret).now()
        assert client.post("/users/mfa/enable", json={"code": code}, headers=headers).status_code == 200

        state = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="mfa_oauth@test.com", email_verified=True)
            resp = _callback(client, "google", "code", state)

        assert resp.status_code == 200
        assert resp.json().get("mfa_required") is True
        assert "access_token" not in resp.json()


class TestLinkAndUnlink:
    def test_link_requires_authentication(self, client: TestClient):
        resp = client.post("/users/oauth/google/link", json={"code": "c", "state": "s"})
        assert resp.status_code == 401

    def test_links_a_new_provider_to_a_logged_in_account(self, client: TestClient, db_session: Session):
        tokens = _register_verify_login(client, db_session, "link_me@test.com", "LinkMe123")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        state = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="link_me@test.com")
            resp = client.post("/users/oauth/google/link", json={"code": "c", "state": state}, headers=headers)

        assert resp.status_code == 201, resp.json()
        linked = client.get("/users/oauth/linked", headers=headers).json()
        assert len(linked) == 1 and linked[0]["provider"] == "google"

    def test_relinking_the_same_identity_is_idempotent(self, client: TestClient, db_session: Session):
        tokens = _register_verify_login(client, db_session, "relink@test.com", "Relink1234")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        for _ in range(2):
            state = _get_state(client)
            with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
                mock_exchange.return_value = _profile(email="relink@test.com", provider_user_id="pid-a")
                resp = client.post("/users/oauth/google/link", json={"code": "c", "state": state}, headers=headers)

        assert resp.status_code == 201, resp.json()
        assert len(client.get("/users/oauth/linked", headers=headers).json()) == 1

    def test_cannot_link_a_second_distinct_identity_for_the_same_provider(
        self, client: TestClient, db_session: Session
    ):
        """A user can have at most one linked identity per provider —
        linking a *different* google identity while one is already linked
        must be rejected rather than silently replacing it."""
        tokens = _register_verify_login(client, db_session, "double_link@test.com", "DoubleLink1")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        state1 = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="double_link@test.com", provider_user_id="pid-a")
            client.post("/users/oauth/google/link", json={"code": "c", "state": state1}, headers=headers)

        state2 = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="double_link@test.com", provider_user_id="pid-b")
            resp = client.post("/users/oauth/google/link", json={"code": "c", "state": state2}, headers=headers)

        assert resp.status_code == 409

    def test_cannot_link_an_identity_already_linked_to_someone_else(
        self, client: TestClient, db_session: Session
    ):
        owner_tokens = _register_verify_login(client, db_session, "identity_owner@test.com", "IdOwner123")
        owner_headers = {"Authorization": f"Bearer {owner_tokens['access_token']}"}
        state1 = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="identity_owner@test.com", provider_user_id="shared-pid")
            client.post("/users/oauth/google/link", json={"code": "c", "state": state1}, headers=owner_headers)

        other_tokens = _register_verify_login(client, db_session, "identity_thief@test.com", "IdThief123")
        other_headers = {"Authorization": f"Bearer {other_tokens['access_token']}"}
        state2 = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="identity_thief@test.com", provider_user_id="shared-pid")
            resp = client.post("/users/oauth/google/link", json={"code": "c", "state": state2}, headers=other_headers)

        assert resp.status_code == 409

    def test_unlink_removes_it(self, client: TestClient, db_session: Session):
        tokens = _register_verify_login(client, db_session, "unlink_me@test.com", "UnlinkMe123")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}
        state = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="unlink_me@test.com")
            client.post("/users/oauth/google/link", json={"code": "c", "state": state}, headers=headers)

        resp = client.delete("/users/oauth/google", headers=headers)

        assert resp.status_code == 204
        assert client.get("/users/oauth/linked", headers=headers).json() == []

    def test_cannot_unlink_the_only_sign_in_method(self, client: TestClient, db_session: Session):
        """A pure-OAuth account (no password) with exactly one linked
        provider must not be able to unlink it — that would lock them out
        of their own account with no way back in."""
        state = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="lockout_risk@test.com")
            login_resp = _callback(client, "google", "code", state)
        headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

        resp = client.delete("/users/oauth/google", headers=headers)

        assert resp.status_code == 400
        assert len(client.get("/users/oauth/linked", headers=headers).json()) == 1

    def test_can_unlink_after_setting_a_password(self, client: TestClient, db_session: Session):
        state = _get_state(client)
        with patch("app.services.oauth_provider.exchange_code_and_fetch_profile", new_callable=AsyncMock) as mock_exchange:
            mock_exchange.return_value = _profile(email="set_pw_then_unlink@test.com")
            login_resp = _callback(client, "google", "code", state)
        headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

        set_pw_resp = client.post(
            "/users/me/password/set", json={"new_password": "NewPassword1"}, headers=headers
        )
        assert set_pw_resp.status_code == 204

        resp = client.delete("/users/oauth/google", headers=headers)

        assert resp.status_code == 204

    def test_set_password_rejects_when_a_password_already_exists(
        self, client: TestClient, db_session: Session
    ):
        tokens = _register_verify_login(client, db_session, "already_has_pw@test.com", "AlreadyPw1")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        resp = client.post(
            "/users/me/password/set", json={"new_password": "AnotherOne1"}, headers=headers
        )

        assert resp.status_code == 400
