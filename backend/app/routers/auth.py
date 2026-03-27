from datetime import datetime, timedelta, timezone
import secrets
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.auth import get_current_principal, login_and_issue_token
from app.config import preview_auth_methods_enabled
from app.db import (
    authenticate_user,
    count_users,
    consume_invite,
    create_user_if_not_exists,
    get_user_by_email,
    get_invite_status,
    save_audit_log,
    update_user_password,
)
from app.rate_limit import enforce_rate_limit, get_request_ip
from app.schemas import (
    AcceptInviteRequest,
    InvitePublicStatusResponse,
    LoginRequest,
    LoginResponse,
    OAuthSignupRequest,
    PasswordChangeRequest,
    PhoneSignupStartRequest,
    PhoneSignupStartResponse,
    PhoneSignupVerifyRequest,
    SetupStatusResponse,
    SignupBootstrapResponse,
    SignupEmailRequest,
    UserRole,
)


router = APIRouter(tags=["auth"])
_pending_phone_codes: Dict[str, tuple[str, datetime]] = {}


def _ensure_preview_auth_enabled() -> None:
    if not preview_auth_methods_enabled():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview auth methods are disabled")


def _tenant_from_email(email: str) -> str:
    domain = (email.split("@", 1)[1] if "@" in email else "demo.local").strip().lower()
    safe = "".join(character if character.isalnum() else "-" for character in domain).strip("-")
    return f"tenant-{safe or 'demo'}"


@router.get("/auth/setup-status", response_model=SetupStatusResponse)
def auth_setup_status(request: Request) -> SetupStatusResponse:
    client_ip = get_request_ip(request)
    enforce_rate_limit("auth", f"setup_status:{client_ip}")

    user_count = count_users()
    return SetupStatusResponse(
        workspace_ready=user_count > 0,
        user_count=user_count,
        first_signup_becomes_admin=user_count == 0,
    )


@router.post("/auth/login", response_model=LoginResponse)
def auth_login(payload: LoginRequest, request: Request) -> LoginResponse:
    client_ip = get_request_ip(request)
    enforce_rate_limit("auth", f"login:{client_ip}")

    result = login_and_issue_token(payload.email, payload.password)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token, email, tenant_id, role = result
    created_at = datetime.now(timezone.utc).isoformat()
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=email,
        action="auth.login",
        target="session",
        details=f"User logged in with role={role}",
        created_at=created_at,
    )
    return LoginResponse(access_token=token, tenant_id=tenant_id, email=email, role=role)


@router.post("/auth/signup", response_model=LoginResponse)
def auth_signup(payload: SignupEmailRequest, request: Request) -> LoginResponse:
    client_ip = get_request_ip(request)
    enforce_rate_limit("auth", f"signup:{client_ip}")

    created_at = datetime.now(timezone.utc).isoformat()
    tenant_id = _tenant_from_email(payload.email)
    normalized_email = payload.email.strip().lower()
    if get_user_by_email(normalized_email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Sign in instead.",
        )
    assigned_role: UserRole = "admin" if count_users() == 0 else payload.role

    create_user_if_not_exists(
        email=normalized_email,
        password=payload.password,
        tenant_id=tenant_id,
        role=assigned_role,
        created_at=created_at,
    )

    result = login_and_issue_token(normalized_email, payload.password)
    if not result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to create account")

    token, email, tenant_id, role = result
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=email,
        action="auth.signup",
        target=email,
        details=f"New account created via email signup role={role}",
        created_at=created_at,
    )
    return LoginResponse(access_token=token, tenant_id=tenant_id, email=email, role=role)


@router.post("/auth/signup/oauth", response_model=SignupBootstrapResponse)
def auth_signup_oauth(payload: OAuthSignupRequest, request: Request) -> SignupBootstrapResponse:
    _ensure_preview_auth_enabled()
    client_ip = get_request_ip(request)
    enforce_rate_limit("auth", f"oauth_signup:{client_ip}")

    created_at = datetime.now(timezone.utc).isoformat()
    tenant_id = _tenant_from_email(payload.email)
    normalized_email = payload.email.strip().lower()
    temp_password = f"oauth-{payload.provider}-{secrets.token_urlsafe(12)}"

    create_user_if_not_exists(
        email=normalized_email,
        password=temp_password,
        tenant_id=tenant_id,
        role="analyst",
        created_at=created_at,
    )

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=normalized_email,
        action=f"auth.signup.{payload.provider}",
        target=normalized_email,
        details=f"OAuth bootstrap created for provider={payload.provider}",
        created_at=created_at,
    )
    return SignupBootstrapResponse(
        message=f"{payload.provider.capitalize()} signup bootstrap completed. Please sign in with your email and password flow until full OAuth redirect is enabled.",
    )


@router.post("/auth/signup/phone/start", response_model=PhoneSignupStartResponse)
def auth_signup_phone_start(payload: PhoneSignupStartRequest, request: Request) -> PhoneSignupStartResponse:
    _ensure_preview_auth_enabled()
    client_ip = get_request_ip(request)
    enforce_rate_limit("auth", f"phone_start:{client_ip}")

    phone = payload.phone.strip()
    code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    _pending_phone_codes[phone] = (code, expires_at)
    return PhoneSignupStartResponse(
        message="Verification code generated. Use this code in the verify step.",
        code_hint=f"demo-{code}",
    )


@router.post("/auth/signup/phone/verify", response_model=LoginResponse)
def auth_signup_phone_verify(payload: PhoneSignupVerifyRequest, request: Request) -> LoginResponse:
    _ensure_preview_auth_enabled()
    client_ip = get_request_ip(request)
    enforce_rate_limit("auth", f"phone_verify:{client_ip}")

    phone = payload.phone.strip()
    pending = _pending_phone_codes.get(phone)
    if not pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No verification request for this phone",
        )

    expected_code, expires_at = pending
    if datetime.now(timezone.utc) > expires_at:
        _pending_phone_codes.pop(phone, None)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired")

    if payload.code.strip() != expected_code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code")

    normalized_phone = "".join(character for character in phone if character.isdigit()) or "user"
    email = f"phone-{normalized_phone}@phone.demo"
    tenant_id = "tenant-phone"
    created_at = datetime.now(timezone.utc).isoformat()
    bootstrap_password = f"phone-{normalized_phone}-verified"

    create_user_if_not_exists(
        email=email,
        password=bootstrap_password,
        tenant_id=tenant_id,
        role="analyst",
        created_at=created_at,
    )

    result = login_and_issue_token(email, bootstrap_password)
    if not result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone verification failed")

    token, login_email, login_tenant, role = result
    _pending_phone_codes.pop(phone, None)
    save_audit_log(
        tenant_id=login_tenant,
        actor_email=login_email,
        action="auth.signup.phone",
        target=login_email,
        details="Account verified via phone code",
        created_at=created_at,
    )
    return LoginResponse(access_token=token, tenant_id=login_tenant, email=login_email, role=role)


@router.post("/auth/accept-invite", response_model=LoginResponse)
def auth_accept_invite(payload: AcceptInviteRequest, request: Request) -> LoginResponse:
    client_ip = get_request_ip(request)
    enforce_rate_limit("auth", f"accept_invite:{client_ip}")

    accepted_at = datetime.now(timezone.utc).isoformat()
    consumed = consume_invite(payload.token, accepted_at)
    if not consumed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite")

    email, tenant_id, role = consumed
    user = create_user_if_not_exists(
        email=email,
        password=payload.password,
        tenant_id=tenant_id,
        role=role,
        created_at=accepted_at,
    )
    update_user_password(user.email, payload.password)

    token, login_email, login_tenant, login_role = login_and_issue_token(user.email, payload.password) or (
        "",
        "",
        "",
        "viewer",
    )
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invite acceptance failed")

    save_audit_log(
        tenant_id=tenant_id,
        actor_email=login_email,
        action="auth.accept_invite",
        target="session",
        details=f"Accepted invite as role={login_role}",
        created_at=accepted_at,
    )
    return LoginResponse(
        access_token=token,
        tenant_id=login_tenant,
        email=login_email,
        role=login_role,
    )


@router.get("/auth/invite-status", response_model=InvitePublicStatusResponse)
def auth_invite_status(token: str, request: Request) -> InvitePublicStatusResponse:
    client_ip = get_request_ip(request)
    enforce_rate_limit("invite_status", client_ip)

    status_info = get_invite_status(token)
    if not status_info:
        return InvitePublicStatusResponse(token=token, status="expired")

    invite_token, email, role, expires_at, status_value = status_info
    return InvitePublicStatusResponse(
        token=invite_token,
        status=status_value,
        email=email,
        role=role,
        expires_at=expires_at,
    )


@router.post("/auth/change-password")
def auth_change_password(
    payload: PasswordChangeRequest,
    request: Request,
    principal: tuple[str, UserRole, str] = Depends(get_current_principal),
) -> dict[str, str]:
    tenant_id, _, actor_email = principal
    client_ip = get_request_ip(request)
    enforce_rate_limit("auth", f"change_password:{client_ip}")

    if actor_email == "api-key-user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password change requires user session token",
        )

    authed = authenticate_user(actor_email, payload.current_password)
    if not authed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect")

    update_user_password(actor_email, payload.new_password)
    changed_at = datetime.now(timezone.utc).isoformat()
    save_audit_log(
        tenant_id=tenant_id,
        actor_email=actor_email,
        action="auth.change_password",
        target=actor_email,
        details="User changed own password",
        created_at=changed_at,
    )
    return {"status": "ok"}