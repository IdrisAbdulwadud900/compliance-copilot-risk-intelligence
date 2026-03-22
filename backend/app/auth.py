import os
from functools import lru_cache
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

from fastapi import Header, HTTPException, status
from jose import JWTError, jwt

from app.db import authenticate_user, init_db
from app.schemas import UserRole


@lru_cache(maxsize=1)
def _api_key_map() -> Dict[str, str]:
    raw = os.getenv("COMPLIANCE_API_KEYS", "").strip()
    if not raw:
        return {"demo-key": "demo-tenant"}

    mapping: Dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair or ":" not in pair:
            continue
        key, tenant = pair.split(":", 1)
        key = key.strip()
        tenant = tenant.strip()
        if key and tenant:
            mapping[key] = tenant

    if not mapping:
        mapping = {"demo-key": "demo-tenant"}

    return mapping


def _jwt_secret() -> str:
    return os.getenv("COMPLIANCE_JWT_SECRET", "dev-secret-change-me")


def _jwt_algo() -> str:
    return os.getenv("COMPLIANCE_JWT_ALG", "HS256")


def create_access_token(email: str, tenant_id: str, role: UserRole) -> str:
    minutes = int(os.getenv("COMPLIANCE_TOKEN_MINUTES", "480"))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {
        "sub": email,
        "tenant": tenant_id,
        "role": role,
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_jwt_algo())


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

    tenant = _api_key_map().get(x_api_key)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return tenant


def _principal_from_api_key(x_api_key: str) -> Tuple[str, UserRole, str]:
    tenant = _tenant_from_api_key(x_api_key)
    return tenant, "admin", "api-key-user"


def get_current_principal(
    authorization: str = Header(default="", alias="Authorization"),
    x_api_key: str = Header(default="", alias="x-api-key"),
) -> Tuple[str, UserRole, str]:
    if authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "", 1).strip()
        try:
            payload = jwt.decode(token, _jwt_secret(), algorithms=[_jwt_algo()])
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
