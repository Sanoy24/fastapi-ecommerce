from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

import aiohttp
from fastapi import HTTPException

from app.core.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

FACEBOOK_GRAPH_VERSION = "v19.0"
FACEBOOK_AUTH_URL = f"https://www.facebook.com/{FACEBOOK_GRAPH_VERSION}/dialog/oauth"
FACEBOOK_TOKEN_URL = f"https://graph.facebook.com/{FACEBOOK_GRAPH_VERSION}/oauth/access_token"
FACEBOOK_PROFILE_URL = f"https://graph.facebook.com/{FACEBOOK_GRAPH_VERSION}/me"

SUPPORTED_PROVIDERS = ("google", "facebook")


@dataclass
class OAuthProfile:
    provider_user_id: str
    email: str
    # Whether the provider itself vouches for this email — Google's
    # email_verified claim, or the fact that Facebook only ever returns the
    # `email` field for a confirmed address at all. Account creation and
    # auto-linking to an existing password account both require this; see
    # UserService.oauth_login.
    email_verified: bool
    name: Optional[str]


def require_supported_provider(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown OAuth provider '{provider}'")


def build_authorization_url(provider: str, state: str) -> str:
    require_supported_provider(provider)
    if provider == "google":
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"

    params = {
        "client_id": settings.FACEBOOK_CLIENT_ID,
        "redirect_uri": settings.OAUTH_REDIRECT_URI,
        "state": state,
        "scope": "email,public_profile",
        "response_type": "code",
    }
    return f"{FACEBOOK_AUTH_URL}?{urlencode(params)}"


async def exchange_code_and_fetch_profile(provider: str, code: str) -> OAuthProfile:
    require_supported_provider(provider)
    async with aiohttp.ClientSession() as session:
        if provider == "google":
            return await _google_profile(session, code)
        return await _facebook_profile(session, code)


async def _google_profile(session: aiohttp.ClientSession, code: str) -> OAuthProfile:
    async with session.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    ) as token_resp:
        if token_resp.status != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange Google authorization code")
        token_data = await token_resp.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google did not return an access token")

    async with session.get(
        GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
    ) as profile_resp:
        if profile_resp.status != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch Google profile")
        data = await profile_resp.json()

    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    return OAuthProfile(
        provider_user_id=str(data["sub"]),
        email=email,
        email_verified=bool(data.get("email_verified", False)),
        name=data.get("name"),
    )


async def _facebook_profile(session: aiohttp.ClientSession, code: str) -> OAuthProfile:
    async with session.get(
        FACEBOOK_TOKEN_URL,
        params={
            "code": code,
            "client_id": settings.FACEBOOK_CLIENT_ID,
            "client_secret": settings.FACEBOOK_CLIENT_SECRET,
            "redirect_uri": settings.OAUTH_REDIRECT_URI,
        },
    ) as token_resp:
        if token_resp.status != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange Facebook authorization code")
        token_data = await token_resp.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Facebook did not return an access token")

    async with session.get(
        FACEBOOK_PROFILE_URL,
        params={"fields": "id,name,email", "access_token": access_token},
    ) as profile_resp:
        if profile_resp.status != 200:
            raise HTTPException(status_code=400, detail="Failed to fetch Facebook profile")
        data = await profile_resp.json()

    # Facebook only ever includes `email` in this response for an address
    # it has already confirmed belongs to the account — there is no
    # separate "unverified" state to check for, unlike Google.
    email = data.get("email")
    if not email:
        raise HTTPException(
            status_code=400,
            detail="Facebook account has no accessible email — grant email access and try again",
        )

    return OAuthProfile(
        provider_user_id=str(data["id"]),
        email=email,
        email_verified=True,
        name=data.get("name"),
    )
