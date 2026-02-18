"""OIDC authentication + RBAC authorization middleware."""

import httpx
import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_db
from app.models.user_config import UserConfig, UserRole

logger = structlog.get_logger()

security = HTTPBearer(auto_error=False)

# Cache for OIDC provider keys
_jwks_cache: dict | None = None


async def _get_google_jwks() -> dict:
    """Fetch Google's OIDC JWKS (JSON Web Key Set)."""
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://www.googleapis.com/oauth2/v3/certs")
        resp.raise_for_status()
        _jwks_cache = resp.json()
        return _jwks_cache


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> UserConfig:
    """Validate OIDC token and return the current user.

    In development mode, allows a bypass header for testing.
    """
    settings = get_settings()

    # Development bypass: X-Dev-User-Email header
    if settings.is_development:
        dev_email = request.headers.get("X-Dev-User-Email")
        if dev_email:
            result = await db.execute(
                select(UserConfig).where(UserConfig.email == dev_email)
            )
            user = result.scalar_one_or_none()
            if user:
                return user

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
        )

    try:
        jwks = await _get_google_jwks()
        # Decode without verification first to get the key ID
        unverified = jwt.get_unverified_header(credentials.credentials)
        kid = unverified.get("kid")

        # Find the matching key
        rsa_key = {}
        for key in jwks.get("keys", []):
            if key["kid"] == kid:
                rsa_key = key
                break

        if not rsa_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find matching key",
            )

        payload = jwt.decode(
            credentials.credentials,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer,
        )
        email = payload.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing email claim",
            )

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        )

    # Lookup user in database
    result = await db.execute(select(UserConfig).where(UserConfig.email == email))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found or inactive",
        )

    return user


def require_roles(*roles: UserRole):
    """Dependency that enforces role-based access control."""

    async def check_role(user: UserConfig = Depends(get_current_user)) -> UserConfig:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role.value}' not authorized. Required: {[r.value for r in roles]}",
            )
        return user

    return check_role
