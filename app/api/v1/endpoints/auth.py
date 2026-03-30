from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError, ExpiredSignatureError
from app.db.session import get_db
from app.models.models import User
from app.core.security import (
    verify_password, hash_password,
    create_access_token, create_refresh_token,
    create_reset_token, decode_token,
)
from app.schemas.schemas import (
    LoginRequest, TokenResponse, RefreshRequest, UserRead,
    PasswordResetRequest, PasswordResetConfirm,
)
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.email == payload.email.lower(),
        User.is_active == True,
    ).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide",
        )

    extra = {
        "org_id": user.organization_id,
        "role": user.role.value,
    }

    return TokenResponse(
        access_token=create_access_token(user.id, extra),
        refresh_token=create_refresh_token(user.id),
        user=UserRead.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise JWTError()
        user_id = int(data["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token non valido o scaduto",
        )

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente non trovato")

    extra = {"org_id": user.organization_id, "role": user.role.value}
    return TokenResponse(
        access_token=create_access_token(user.id, extra),
        refresh_token=create_refresh_token(user.id),
        user=UserRead.model_validate(user),
    )


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(payload: PasswordResetRequest, db: Session = Depends(get_db)):
    """
    Generates a reset token and logs the reset link to the console.
    In development mode, also returns the reset link in the response.
    Always returns 200 to avoid email enumeration.
    """
    user = db.query(User).filter(
        User.email == payload.email.lower(),
        User.is_active == True,
    ).first()

    reset_link = None
    if user:
        token = create_reset_token(user.email)
        reset_link = f"http://localhost:5173/reset-password?token={token}"
        print(f"\n{'='*60}")
        print(f"[PASSWORD RESET] Utente: {user.email}")
        print(f"[PASSWORD RESET] Link (valido 30 min): {reset_link}")
        print(f"{'='*60}\n")

    response: dict = {"message": "Se l'email esiste, riceverai le istruzioni per il reset."}

    # In development, return the link directly so it can be tested without SMTP
    if settings.APP_ENV == "development" and reset_link:
        response["dev_reset_link"] = reset_link

    return response


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    """Validates the reset token and updates the user password."""
    try:
        data = decode_token(payload.token)
        if data.get("type") != "reset":
            raise JWTError("tipo token errato")
        email = data["sub"]
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Il link di reset è scaduto. Richiedi un nuovo link.",
        )
    except (JWTError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token non valido.",
        )

    user = db.query(User).filter(
        User.email == email,
        User.is_active == True,
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utente non trovato.")

    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    return {"message": "Password aggiornata con successo."}