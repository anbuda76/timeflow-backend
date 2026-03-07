from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import Holiday, User
from app.core.deps import get_current_user, require_admin, same_org_or_admin
from app.schemas.schemas import HolidayCreate, HolidayRead

router = APIRouter(prefix="/holidays", tags=["holidays"])


@router.get("/", response_model=list[HolidayRead])
def list_holidays(
    year: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Holiday).filter(Holiday.organization_id == current_user.organization_id)
    if year:
        q = q.filter(Holiday.holiday_date >= f"{year}-01-01", Holiday.holiday_date <= f"{year}-12-31")
    return q.order_by(Holiday.holiday_date).all()


@router.post("/", response_model=HolidayRead, status_code=status.HTTP_201_CREATED)
def create_holiday(
    payload: HolidayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    existing = db.query(Holiday).filter(
        Holiday.organization_id == current_user.organization_id,
        Holiday.holiday_date == payload.holiday_date,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Festività già presente per questa data")

    holiday = Holiday(
        organization_id=current_user.organization_id,
        **payload.model_dump(),
    )
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holiday(
    holiday_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    holiday = db.get(Holiday, holiday_id)
    if not holiday:
        raise HTTPException(status_code=404, detail="Festività non trovata")
    same_org_or_admin(holiday.organization_id, current_user)
    db.delete(holiday)
    db.commit()