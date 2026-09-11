"""
Regression tests for the MFA challenge-token / access-token type confusion bug.

Previously, create_token() spread caller data *before* setting "type": "access",
so the literal default silently overwrote any type the caller supplied (e.g.
"mfa_challenge"). Combined with decode_access_token() only denylisting
type == "refresh", the MFA challenge token issued after password verification
was a fully valid access token — anyone with an MFA-enabled account's password
could skip the second factor entirely.
"""
import pyotp
import pytest
from fastapi.testclient import TestClient

from app.core.config import Setting
from app.utils.security import TokenError, create_token, decode_access_token, decode_challenge_token

_USER = {
    "email": "mfauser@test.com",
    "password": "MfaTest1",
    "first_name": "Mfa",
    "last_name": "User",
    "phone": "0922222222",
}


def _register_verify_login(client: TestClient, db_session) -> dict:
    from app.models.user import User

    client.post("/users/register", json=_USER)
    user = db_session.query(User).filter(User.email == _USER["email"]).first()
    client.get(f"/users/verify-email?token={user.verification_token}")

    resp = client.post(
        "/users/login",
        json={"email": _USER["email"], "password": _USER["password"]},
    )
    assert resp.status_code == 200
    return resp.json()


def _enable_mfa(client: TestClient, access_token: str) -> str:
    headers = {"Authorization": f"Bearer {access_token}"}
    setup_resp = client.post("/users/mfa/setup", headers=headers)
    assert setup_resp.status_code == 200
    secret = setup_resp.json()["secret"]

    code = pyotp.TOTP(secret).now()
    enable_resp = client.post("/users/mfa/enable", json={"code": code}, headers=headers)
    assert enable_resp.status_code == 200
    return secret


class TestMfaChallengeTokenCannotAuthenticate:
    def test_challenge_token_is_rejected_as_bearer_token(self, client: TestClient, db_session):
        """The mfa_challenge_token must not grant access to protected routes."""
        tokens = _register_verify_login(client, db_session)
        _enable_mfa(client, tokens["access_token"])

        login_resp = client.post(
            "/users/login",
            json={"email": _USER["email"], "password": _USER["password"]},
        )
        assert login_resp.status_code == 200
        body = login_resp.json()
        assert body["mfa_required"] is True
        challenge_token = body["mfa_challenge_token"]

        me_resp = client.get("/users/me", headers={"Authorization": f"Bearer {challenge_token}"})
        assert me_resp.status_code == 401

    def test_full_mfa_login_flow_succeeds_with_correct_code(self, client: TestClient, db_session):
        tokens = _register_verify_login(client, db_session)
        secret = _enable_mfa(client, tokens["access_token"])

        login_resp = client.post(
            "/users/login",
            json={"email": _USER["email"], "password": _USER["password"]},
        )
        challenge_token = login_resp.json()["mfa_challenge_token"]

        code = pyotp.TOTP(secret).now()
        verify_resp = client.post(
            "/users/mfa/verify",
            json={"challenge_token": challenge_token, "data": {"code": code}},
        )
        assert verify_resp.status_code == 200
        real_access_token = verify_resp.json()["access_token"]

        me_resp = client.get("/users/me", headers={"Authorization": f"Bearer {real_access_token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == _USER["email"]


class TestTokenTypeAllowlisting:
    """Unit-level checks on the security helpers, independent of the HTTP layer."""

    def test_create_token_preserves_caller_supplied_type(self):
        token = create_token(data={"sub": "1", "type": "mfa_challenge"})
        payload = decode_challenge_token(token)
        assert payload["type"] == "mfa_challenge"

    def test_decode_access_token_rejects_challenge_token(self):
        token = create_token(data={"sub": "1", "type": "mfa_challenge"})
        with pytest.raises(TokenError):
            decode_access_token(token)

    def test_decode_access_token_accepts_plain_access_token(self):
        token = create_token(data={"sub": "1"})
        payload = decode_access_token(token)
        assert payload["type"] == "access"


class TestJwtSecretKeyIsRequired:
    def test_missing_secret_fails_validation(self):
        with pytest.raises(Exception):
            Setting(_env_file=None, JWT_SECRET_KEY="")

    def test_short_secret_fails_validation(self):
        with pytest.raises(Exception):
            Setting(_env_file=None, JWT_SECRET_KEY="too-short")

    def test_sufficiently_long_secret_is_accepted(self):
        setting = Setting(_env_file=None, JWT_SECRET_KEY="a" * 32)
        assert setting.JWT_SECRET_KEY == "a" * 32
