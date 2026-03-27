import os
from typing import Dict, List, Tuple

from app.schemas import UserRole
from app.storage.runtime import database_url, resolve_database_runtime


DEFAULT_LOCAL_ORIGINS: Tuple[str, ...] = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)
INSECURE_JWT_SECRET = "dev-secret-change-me"
INSECURE_WEBHOOK_SECRET = "changeme-webhook-secret"
INSECURE_ADMIN_PASSWORD = "ChangeMe123!"
PREVIEW_BOOTSTRAP_ENV = "COMPLIANCE_ENABLE_PREVIEW_BOOTSTRAP"
PREVIEW_AUTH_METHODS_ENV = "COMPLIANCE_ENABLE_PREVIEW_AUTH_METHODS"


def app_env() -> str:
    return os.getenv("COMPLIANCE_ENV", "development").strip().lower() or "development"


def is_production() -> bool:
    return app_env() == "production"


def preview_bootstrap_enabled() -> bool:
    raw = os.getenv(PREVIEW_BOOTSTRAP_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def preview_auth_methods_enabled() -> bool:
    raw = os.getenv(PREVIEW_AUTH_METHODS_ENV, "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def database_backend() -> str:
    return resolve_database_runtime().backend


def database_runtime_summary() -> Dict[str, str]:
    runtime = resolve_database_runtime()
    persistence = "persistent"
    if runtime.backend == "sqlite":
        persistence = "ephemeral" if uses_ephemeral_sqlite_storage() else "local-disk"
    return {"backend": runtime.backend, "target": runtime.target, "persistence": persistence}


def uses_ephemeral_sqlite_storage() -> bool:
    runtime = resolve_database_runtime()
    if runtime.backend != "sqlite":
        return False
    target = runtime.target.strip().lower()
    return target == ":memory:" or target.startswith("/tmp/") or target.startswith("/var/tmp/")


def _split_csv_env(name: str) -> List[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def allowed_origins() -> Tuple[str, ...]:
    configured = tuple(_split_csv_env("COMPLIANCE_ALLOWED_ORIGINS"))
    if configured:
        return configured
    return tuple() if is_production() else DEFAULT_LOCAL_ORIGINS


def jwt_secret() -> str:
    return os.getenv("COMPLIANCE_JWT_SECRET", INSECURE_JWT_SECRET)


def jwt_algo() -> str:
    return os.getenv("COMPLIANCE_JWT_ALG", "HS256")


def token_minutes() -> int:
    try:
        return max(5, int(os.getenv("COMPLIANCE_TOKEN_MINUTES", "480")))
    except ValueError:
        return 480


def webhook_secret() -> str:
    return os.getenv("COMPLIANCE_WEBHOOK_SECRET", INSECURE_WEBHOOK_SECRET)


def webhook_timeout_seconds() -> int:
    try:
        return max(1, int(os.getenv("COMPLIANCE_WEBHOOK_TIMEOUT", "5")))
    except ValueError:
        return 5


def api_key_principals() -> Dict[str, Tuple[str, UserRole]]:
    raw_pairs = _split_csv_env("COMPLIANCE_API_KEYS")
    mapping: Dict[str, Tuple[str, UserRole]] = {}
    for pair in raw_pairs:
        parts = [part.strip() for part in pair.split(":")]
        if len(parts) == 2:
            key, tenant = parts
            role: UserRole = "viewer"
        elif len(parts) == 3:
            key, tenant, role_raw = parts
            role = role_raw if role_raw in ("admin", "analyst", "viewer") else "viewer"
        else:
            continue
        if key and tenant:
            mapping[key] = (tenant, role)
    return mapping


def config_warnings() -> List[str]:
    warnings: List[str] = []
    origins = allowed_origins()
    if not origins:
        warnings.append("cors_origins_not_configured")
    if "*" in origins:
        warnings.append("cors_all_origins_enabled")
    if jwt_secret() == INSECURE_JWT_SECRET:
        warnings.append("jwt_secret_uses_default")
    if webhook_secret() == INSECURE_WEBHOOK_SECRET:
        warnings.append("webhook_secret_uses_default")
    if not api_key_principals():
        warnings.append("api_key_auth_disabled")
    if preview_bootstrap_enabled():
        warnings.append("preview_bootstrap_enabled")
    if preview_auth_methods_enabled():
        warnings.append("preview_auth_methods_enabled")
    admin_password = os.getenv("COMPLIANCE_ADMIN_PASSWORD", "")
    if admin_password == INSECURE_ADMIN_PASSWORD:
        warnings.append(
            "preview_default_admin_enabled"
            if preview_bootstrap_enabled()
            else "default_admin_password_configured"
        )
    backend = database_backend()
    if is_production() and backend == "sqlite":
        warnings.append("sqlite_in_production")
    if is_production() and uses_ephemeral_sqlite_storage():
        warnings.append("ephemeral_sqlite_storage")
    if backend == "postgres":
        warnings.append("postgres_runtime_enabled_unvalidated")
    if backend == "unknown":
        warnings.append("unsupported_database_url_scheme")
    return warnings


def validate_runtime_config() -> None:
    if not is_production():
        return

    errors: List[str] = []
    origins = allowed_origins()
    if not origins:
        errors.append("COMPLIANCE_ALLOWED_ORIGINS must be set in production")
    if "*" in origins:
        errors.append("Wildcard CORS is forbidden in production")
    if jwt_secret() in ("", INSECURE_JWT_SECRET):
        errors.append("COMPLIANCE_JWT_SECRET must be set to a non-default value")
    if webhook_secret() in ("", INSECURE_WEBHOOK_SECRET):
        errors.append("COMPLIANCE_WEBHOOK_SECRET must be set to a non-default value")
    if preview_bootstrap_enabled():
        errors.append(f"{PREVIEW_BOOTSTRAP_ENV} must be disabled in production")
    if preview_auth_methods_enabled():
        errors.append(f"{PREVIEW_AUTH_METHODS_ENV} must be disabled in production")
    if os.getenv("COMPLIANCE_ADMIN_PASSWORD", "") == INSECURE_ADMIN_PASSWORD:
        errors.append("COMPLIANCE_ADMIN_PASSWORD cannot use the default password")

    if errors:
        raise RuntimeError("Invalid production configuration: " + "; ".join(errors))