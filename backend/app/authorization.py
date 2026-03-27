from typing import Iterable

from fastapi import HTTPException, status

from app.schemas import UserRole


def require_role(role: UserRole, *, detail: str = "Admin only") -> None:
    if role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def require_any_role(
    role: UserRole,
    allowed: Iterable[UserRole],
    *,
    detail: str = "Insufficient role",
) -> None:
    if role not in tuple(allowed):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)