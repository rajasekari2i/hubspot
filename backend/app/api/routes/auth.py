"""Auth routes - OIDC login/callback/me/logout."""

import secrets
from urllib.parse import urlencode

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db
from app.api.middleware.auth import get_current_user
from app.models.user_config import UserConfig

logger = structlog.get_logger()
router = APIRouter(prefix="/auth", tags=["Auth"])

# In-memory state store for OIDC flow (use Redis in production)
_oauth_states: dict[str, str] = {}


@router.get("/login")
async def initiate_login() -> RedirectResponse:
    """Redirect to Google OIDC login."""
    settings = get_settings()
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = state

    params = {
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def oidc_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle OIDC callback, exchange code for tokens."""
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    del _oauth_states[state]

    settings = get_settings()

    # Exchange authorization code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
                "redirect_uri": settings.oidc_redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Token exchange failed")

    token_data = token_resp.json()
    id_token = token_data.get("id_token", "")

    # Verify user exists in the system
    from jose import jwt as jose_jwt

    claims = jose_jwt.get_unverified_claims(id_token)
    email = claims.get("email")

    result = await db.execute(select(UserConfig).where(UserConfig.email == email))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=403, detail="User not registered in the system")

    # In production: set a session cookie with the access token
    # For now, redirect to dashboard with token as query param
    redirect_url = f"http://localhost:3000/auth/callback?token={token_data.get('access_token', '')}"
    return RedirectResponse(url=redirect_url)


@router.get("/me")
async def get_me(user: UserConfig = Depends(get_current_user)) -> dict:
    """Get current authenticated user."""
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value,
        "hubspot_owner_id": user.hubspot_owner_id,
        "slack_user_id": user.slack_user_id,
        "is_active": user.is_active,
    }


@router.post("/logout")
async def logout() -> dict:
    """Logout and clear session."""
    # In production: invalidate session/token
    return {"status": "logged_out"}
