from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session
from app.core.security import decode_token
from app.db.session import get_db
from app.models.models import User, UserRole

bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise JWTError("Wrong token type")
        user_id: int = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto",
        )

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utente non trovato o disabilitato",
        )
    return user


def require_role(*roles: UserRole):
    def guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accesso riservato a: {[r.value for r in roles]}",
            )
        return user
    return guard


require_super_admin = require_role(UserRole.SUPER_ADMIN)
require_admin = require_role(UserRole.SUPER_ADMIN, UserRole.ADMIN)
require_manager = require_role(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER)


def same_org_or_admin(target_org_id: int, current_user: User) -> None:
    if current_user.role == UserRole.SUPER_ADMIN:
        return
    if current_user.organization_id != target_org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accesso negato: organizzazione diversa",
        )