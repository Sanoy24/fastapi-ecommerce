"""Tests for the extended auth flows: refresh tokens, logout, and password management."""
import pytest
from fastapi.testclient import TestClient


_USER = {
    "email": "authext@test.com",
    "password": "AuthExt1",
    "first_name": "Auth",
    "last_name": "Extended",
    "phone": "0911111111",
}


def _register_login(client: TestClient) -> dict:
    client.post("/users/register", json=_USER)
    resp = client.post(
        "/users/login",
        json={"email": _USER["email"], "password": _USER["password"]},
    )
    assert resp.status_code == 200
    return resp.json()


class TestTokenSchema:
    def test_login_returns_both_tokens(self, client: TestClient):
        tokens = _register_login(client)
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "Bearer"
        assert "expires_in" in tokens

    def test_access_token_is_not_empty(self, client: TestClient):
        tokens = _register_login(client)
        assert len(tokens["access_token"]) > 20
        assert len(tokens["refresh_token"]) > 20


class TestRefreshToken:
    def test_refresh_issues_new_tokens(self, client: TestClient):
        tokens = _register_login(client)
        resp = client.post(
            "/users/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert resp.status_code == 200
        new_tokens = resp.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

    def test_refresh_with_invalid_token_returns_401(self, client: TestClient):
        resp = client.post(
            "/users/refresh",
            json={"refresh_token": "this.is.not.valid"},
        )
        assert resp.status_code == 401

    def test_refresh_with_access_token_fails(self, client: TestClient):
        """Access tokens must not be accepted as refresh tokens."""
        tokens = _register_login(client)
        resp = client.post(
            "/users/refresh",
            json={"refresh_token": tokens["access_token"]},
        )
        assert resp.status_code == 401


class TestLogout:
    def test_logout_succeeds(self, client: TestClient):
        tokens = _register_login(client)
        resp = client.post(
            "/users/logout",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert resp.status_code == 204

    def test_logout_with_garbage_token_does_not_error(self, client: TestClient):
        """Logout with an already-invalid token should not raise an error."""
        resp = client.post(
            "/users/logout",
            json={"refresh_token": "garbage.token.here"},
        )
        assert resp.status_code == 204


class TestChangePassword:
    def test_change_password_wrong_current_fails(self, client: TestClient):
        tokens = _register_login(client)
        resp = client.put(
            "/users/me/password",
            json={"current_password": "WrongPass1", "new_password": "NewPass1"},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 400

    def test_change_password_requires_auth(self, client: TestClient):
        resp = client.put(
            "/users/me/password",
            json={"current_password": "AuthExt1", "new_password": "NewPass1"},
        )
        assert resp.status_code == 401

    def test_change_password_weak_new_password_fails(self, client: TestClient):
        tokens = _register_login(client)
        resp = client.put(
            "/users/me/password",
            json={"current_password": _USER["password"], "new_password": "weakpass"},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 422


class TestForgotPassword:
    def test_forgot_password_always_returns_200(self, client: TestClient):
        """Should return 200 even for unknown emails (no enumeration)."""
        resp = client.post(
            "/users/forgot-password",
            json={"email": "nonexistent@nowhere.com"},
        )
        assert resp.status_code == 200

    def test_forgot_password_known_email_returns_200(self, client: TestClient):
        _register_login(client)
        resp = client.post(
            "/users/forgot-password",
            json={"email": _USER["email"]},
        )
        assert resp.status_code == 200

    def test_reset_password_invalid_token_fails(self, client: TestClient):
        resp = client.post(
            "/users/reset-password",
            json={"token": "invalid_token_xyz", "new_password": "NewValid1"},
        )
        # Redis not running in tests → 503 or 400
        assert resp.status_code in (400, 503)


class TestPasswordValidation:
    def test_register_weak_password_no_uppercase_fails(self, client: TestClient):
        resp = client.post(
            "/users/register",
            json={
                "email": "weak@test.com",
                "password": "alllowercase1",
                "first_name": "Weak",
                "last_name": "Pass",
                "phone": "0900000000",
            },
        )
        assert resp.status_code == 422

    def test_register_weak_password_no_digit_fails(self, client: TestClient):
        resp = client.post(
            "/users/register",
            json={
                "email": "weak2@test.com",
                "password": "NoDigitsHere",
                "first_name": "Weak",
                "last_name": "Pass",
                "phone": "0900000001",
            },
        )
        assert resp.status_code == 422

    def test_register_too_short_password_fails(self, client: TestClient):
        resp = client.post(
            "/users/register",
            json={
                "email": "short@test.com",
                "password": "Ab1",
                "first_name": "Short",
                "last_name": "Pass",
                "phone": "0900000002",
            },
        )
        assert resp.status_code == 422
