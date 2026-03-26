from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import WeekendAuthorization, User, UserRole
from app.core.deps import require_admin, get_current_user
from pydantic import BaseModel
from datetime import date
from typing import Optional
import calendar

router = APIRouter(prefix="/weekend-auth", tags=["weekend-auth"])

class WeekendAuthCreate(BaseModel):
    user_id: int
    auth_date: date
    note: Optional[str] = None

class WeekendAuthRead(BaseModel):
    id: int
    user_id: int
    authorized_by_id: int
    auth_date: date
    note: Optional[str] = None

    model_config = {"from_attributes": True}

@router.get("/", response_model=list[WeekendAuthRead])
def list_authorizations(
    year: int | None = Query(None),
    month: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    q = db.query(WeekendAuthorization).filter(
        WeekendAuthorization.organization_id == current_user.organization_id
    )
    if year:
        q = q.filter(WeekendAuthorization.auth_date >= date(year, 1, 1))
        q = q.filter(WeekendAuthorization.auth_date <= date(year, 12, 31))
    if year and month:
        last_day = calendar.monthrange(year, month)[1]
        q = q.filter(WeekendAuthorization.auth_date >= date(year, month, 1))
        q = q.filter(WeekendAuthorization.auth_date <= date(year, month, last_day))
    return q.order_by(WeekendAuthorization.auth_date.desc()).all()

@router.get("/my", response_model=list[WeekendAuthRead])
def my_authorizations(
    year: int | None = Query(None),
    month: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(WeekendAuthorization).filter(
        WeekendAuthorization.user_id == current_user.id
    )
    # Filtriamo solo i weekend del periodo richiesto per ridurre il payload
    if year:
        q = q.filter(WeekendAuthorization.auth_date >= date(year, 1, 1))
        q = q.filter(WeekendAuthorization.auth_date <= date(year, 12, 31))
    if year and month:
        last_day = calendar.monthrange(year, month)[1]
        q = q.filter(WeekendAuthorization.auth_date >= date(year, month, 1))
        q = q.filter(WeekendAuthorization.auth_date <= date(year, month, last_day))
    return q.order_by(WeekendAuthorization.auth_date.desc()).all()

@router.post("/", response_model=WeekendAuthRead, status_code=status.HTTP_201_CREATED)
def create_authorization(
    payload: WeekendAuthCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Verifica che la data sia un weekend
    if payload.auth_date.weekday() not in (5, 6):
        raise HTTPException(status_code=400, detail="La data deve essere un sabato o domenica")

    # Verifica che l'utente appartenga alla stessa org
    user = db.get(User, payload.user_id)
    if not user or user.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Utente non trovato")

    # Verifica duplicato
    existing = db.query(WeekendAuthorization).filter(
        WeekendAuthorization.user_id == payload.user_id,
        WeekendAuthorization.auth_date == payload.auth_date,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Autorizzazione già esistente per questa data")

    auth = WeekendAuthorization(
        organization_id=current_user.organization_id,
        user_id=payload.user_id,
        authorized_by_id=current_user.id,
        auth_date=payload.auth_date,
        note=payload.note,
    )
    db.add(auth)
    db.commit()
    db.refresh(auth)
    return auth

@router.delete("/{auth_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_authorization(
    auth_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    auth = db.get(WeekendAuthorization, auth_id)
    if not auth or auth.organization_id != current_user.organization_id:
        raise HTTPException(status_code=404, detail="Autorizzazione non trovata")
    db.delete(auth)
    db.commit()