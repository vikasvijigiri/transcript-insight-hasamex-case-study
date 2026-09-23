"""Authentication and tenant boundary for the HTTP API.

Supabase Auth owns sign-in. The API validates the signed access token locally
against Supabase's public JWKS, so the service never handles a Google client
secret, Supabase service-role key, or a shared JWT secret.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, status

from .config import get_settings


@dataclass(frozen=True)
class Principal:
    """The authenticated subject and the tenant to which data access is scoped."""

    user_id: str
    tenant_id: str
    roles: frozenset[str]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


@lru_cache
def _jwks_client(supabase_url: str) -> jwt.PyJWKClient:
    """Cache signing keys; PyJWKClient refreshes on an unknown key id."""
    return jwt.PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json")


def _claims_for(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.supabase_url:
        raise _unauthorized("Authentication is enabled but SUPABASE_URL is not configured")
    try:
        signing_key = _jwks_client(settings.supabase_url).get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["ES256", "RS256"],
            audience=settings.supabase_jwt_audience,
            issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
            options={"require": ["exp", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise _unauthorized("Invalid or expired access token") from exc


def get_current_principal(authorization: Annotated[str | None, Header()] = None) -> Principal:
    """Return local development identity or verify a production Supabase JWT.

    Tenant is controlled from *app_metadata*, which clients cannot change. It
    defaults to the user's subject for safe per-user isolation until an
    organization provisioning workflow assigns a shared tenant id.
    """
    settings = get_settings()
    if not settings.auth_required:
        return Principal(user_id="local", tenant_id="local", roles=frozenset({"admin"}))
    if not authorization or not authorization.startswith("Bearer "):
        raise _unauthorized("A Bearer access token is required")
    claims = _claims_for(authorization.removeprefix("Bearer ").strip())
    subject = claims["sub"]
    app_metadata = claims.get("app_metadata") or {}
    tenant_id = app_metadata.get("tenant_id", subject)
    if not isinstance(tenant_id, str) or not tenant_id:
        raise _unauthorized("Token has an invalid tenant claim")
    role = app_metadata.get("role", "researcher")
    roles = frozenset(role if isinstance(role, list) else [str(role)])
    return Principal(user_id=subject, tenant_id=tenant_id, roles=roles)


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def require_research_write_access(principal: CurrentPrincipal) -> Principal:
    """Limit corpus mutation to explicitly provisioned research/admin roles."""
    if not principal.roles.intersection({"admin", "researcher"}):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient project role"
        )
    return principal


WritePrincipal = Annotated[Principal, Depends(require_research_write_access)]
