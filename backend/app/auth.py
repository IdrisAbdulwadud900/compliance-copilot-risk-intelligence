from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from app.config import api_key_principals, jwt_algo, jwt_secret, token_minutes
from app.db import authenticate_user, init_db
from app.schemas import UserRole


def create_access_token(email: str, tenant_id: str, role: UserRole) -> str:
    minutes = token_minutes()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": email,
        "tenant": tenant_id,
        "role": role,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, jwt_secret(), algorithm=jwt_algo())


def login_and_issue_token(
    email: str, password: str
) -> Optional[Tuple[str, str, str, UserRole]]:
    init_db()
    authed = authenticate_user(email, password)
    if not authed:
        return None

    normalized_email, tenant_id, role = authed
    token = create_access_token(normalized_email, tenant_id, role)
    return token, normalized_email, tenant_id, role


def _tenant_from_api_key(x_api_key: str) -> str:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    principal = api_key_principals().get(x_api_key)
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    tenant, _ = principal
    return tenant


def _principal_from_api_key(x_api_key: str) -> Tuple[str, UserRole, str]:
    principal = api_key_principals().get(x_api_key)
    if not principal:
        _tenant_from_api_key(x_api_key)
    tenant, role = principal or ("", "viewer")
    return tenant, role, "api-key-user"


def get_current_principal(
    authorization: str = Header(default="", alias="Authorization"),
    x_api_key: str = Header(default="", alias="x-api-key"),
) -> Tuple[str, UserRole, str]:
    if authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "", 1).strip()
        try:
            payload = jwt.decode(token, jwt_secret(), algorithms=[jwt_algo()])
            tenant = str(payload.get("tenant", ""))
            role = str(payload.get("role", ""))
            email = str(payload.get("sub", ""))
            if not tenant or role not in ("admin", "analyst", "viewer") or not email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload",
                )
            return tenant, role, email
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from exc

    return _principal_from_api_key(x_api_key)


def get_current_tenant(
    authorization: str = Header(default="", alias="Authorization"),
    x_api_key: str = Header(default="", alias="x-api-key"),
) -> str:
    tenant, _, _ = get_current_principal(authorization, x_api_key)
    return tenant


def get_current_role(
    authorization: str = Header(default="", alias="Authorization"),
    x_api_key: str = Header(default="", alias="x-api-key"),
) -> UserRole:
    _, role, _ = get_current_principal(authorization, x_api_key)
    return role
