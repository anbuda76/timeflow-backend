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

from datetime import date

ITALIAN_HOLIDAYS = [
    (1, 1, "Capodanno"),
    (1, 6, "Epifania"),
    (4, 25, "Festa della Liberazione"),
    (5, 1, "Festa del Lavoro"),
    (6, 2, "Festa della Repubblica"),
    (8, 15, "Ferragosto"),
    (11, 1, "Ognissanti"),
    (12, 8, "Immacolata Concezione"),
    (12, 25, "Natale"),
    (12, 26, "Santo Stefano"),
]

def get_easter(year: int):
    """Algoritmo di Gauss per calcolo Pasqua."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)

@router.post("/preload/{year}", response_model=list[HolidayRead], status_code=status.HTTP_201_CREATED)
def preload_italian_holidays(
    year: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    from datetime import timedelta
    easter = get_easter(year)
    easter_monday = easter + timedelta(days=1)

    holidays_to_add = [(m, d, label) for m, d, label in ITALIAN_HOLIDAYS]
    holidays_to_add.append((easter.month, easter.day, "Pasqua"))
    holidays_to_add.append((easter_monday.month, easter_monday.day, "Lunedì dell'Angelo"))

    created = []
    for month, day, label in holidays_to_add:
        holiday_date = date(year, month, day)
        existing = db.query(Holiday).filter(
            Holiday.organization_id == current_user.organization_id,
            Holiday.holiday_date == holiday_date,
        ).first()
        if not existing:
            h = Holiday(
                organization_id=current_user.organization_id,
                holiday_date=holiday_date,
                label=label,
                type="national",
            )
            db.add(h)
            created.append(h)
    db.commit()
    for h in created:
        db.refresh(h)
    return created