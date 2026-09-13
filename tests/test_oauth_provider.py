"""
Pure unit tests for app/services/oauth_provider.py's URL-building —
no network involved, so these run without mocking anything. The actual
code-exchange/profile-fetch calls (_google_profile/_facebook_profile) are
exercised indirectly through tests/test_oauth_login.py, which mocks
exchange_code_and_fetch_profile at the module boundary rather than faking
aiohttp's async response protocol.
"""
import pytest
from fastapi import HTTPException

from app.services import oauth_provider


class TestRequireSupportedProvider:
    def test_accepts_google(self):
        oauth_provider.require_supported_provider("google")

    def test_accepts_facebook(self):
        oauth_provider.require_supported_provider("facebook")

    def test_rejects_github(self):
        """github was deliberately dropped in favor of facebook."""
        with pytest.raises(HTTPException) as exc_info:
            oauth_provider.require_supported_provider("github")
        assert exc_info.value.status_code == 404

    def test_rejects_unknown_provider(self):
        with pytest.raises(HTTPException) as exc_info:
            oauth_provider.require_supported_provider("twitter")
        assert exc_info.value.status_code == 404


class TestBuildAuthorizationUrl:
    def test_google_url_has_expected_params(self):
        url = oauth_provider.build_authorization_url("google", "state123")
        assert url.startswith(oauth_provider.GOOGLE_AUTH_URL)
        assert "state=state123" in url
        assert "response_type=code" in url
        assert "scope=" in url

    def test_facebook_url_has_expected_params(self):
        url = oauth_provider.build_authorization_url("facebook", "state456")
        assert url.startswith(oauth_provider.FACEBOOK_AUTH_URL)
        assert "state=state456" in url
        assert "scope=email" in url

    def test_rejects_unsupported_provider(self):
        with pytest.raises(HTTPException) as exc_info:
            oauth_provider.build_authorization_url("github", "state")
        assert exc_info.value.status_code == 404
