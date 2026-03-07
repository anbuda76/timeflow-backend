from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import User, UserRole
from app.core.security import hash_password, verify_password
from app.core.deps import get_current_user, require_admin, same_org_or_admin
from app.schemas.schemas import UserCreate, UserUpdate, UserRead, UserPasswordUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.SUPER_ADMIN:
        return db.query(User).order_by(User.last_name).all()
    return (
        db.query(User)
        .filter(User.organization_id == current_user.organization_id)
        .order_by(User.last_name)
        .all()
    )


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    org_id = current_user.organization_id

    existing = db.query(User).filter(
        User.organization_id == org_id,
        User.email == payload.email.lower(),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email già registrata in questa organizzazione")

    user = User(
        organization_id=org_id,
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=payload.role,
        hourly_rate=payload.hourly_rate,
        manager_id=payload.manager_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    same_org_or_admin(user.organization_id, current_user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    same_org_or_admin(user.organization_id, current_user)

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: UserPasswordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Password attuale non corretta")
    current_user.hashed_password = hash_password(payload.new_password)
    db.commit()