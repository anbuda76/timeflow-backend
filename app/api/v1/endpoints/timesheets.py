from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from app.db.session import get_db
from app.models.models import (
    Timesheet, TimesheetEntry, TimesheetStatus,
    User, UserRole, Holiday, WeekendAuthorization
)
from app.core.deps import get_current_user, require_manager, same_org_or_admin
from app.schemas.schemas import (
    TimesheetCreate, TimesheetUpdate, TimesheetRead, TimesheetReadBrief,
    TimesheetEntryCreate, TimesheetEntryRead,
    TimesheetSubmit, TimesheetReview,
)

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


def _get_timesheet_or_404(ts_id: int, db: Session) -> Timesheet:
    ts = db.query(Timesheet).options(
        joinedload(Timesheet.entries)
    ).filter(Timesheet.id == ts_id).first()
    if not ts:
        raise HTTPException(status_code=404, detail="Timesheet non trovato")
    return ts


# ── Timesheet CRUD ────────────────────────────────────────────────────────────

@router.get("/", response_model=list[TimesheetReadBrief])
def list_timesheets(
    year: int | None = Query(None),
    month: int | None = Query(None),
    user_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Timesheet)

    if current_user.role == UserRole.EMPLOYEE:
        # Vede solo i propri
        q = q.filter(Timesheet.user_id == current_user.id)
    elif current_user.role == UserRole.MANAGER:
        # Vede i propri + quelli del suo team
        from app.models.models import User as U
        team_ids = [
            u.id for u in db.query(U).filter(U.manager_id == current_user.id).all()
        ]
        team_ids.append(current_user.id)
        q = q.filter(Timesheet.user_id.in_(team_ids))
    elif current_user.role == UserRole.ADMIN:
        # Vede tutta la propria org
        from app.models.models import User as U
        org_user_ids = [
            u.id for u in db.query(U).filter(U.organization_id == current_user.organization_id).all()
        ]
        q = q.filter(Timesheet.user_id.in_(org_user_ids))
    # SUPER_ADMIN vede tutto

    if year:
        q = q.filter(Timesheet.year == year)
    if month:
        q = q.filter(Timesheet.month == month)
    if user_id and current_user.role != UserRole.EMPLOYEE:
        q = q.filter(Timesheet.user_id == user_id)

    return q.order_by(Timesheet.year.desc(), Timesheet.month.desc()).all()


@router.post("/", response_model=TimesheetRead, status_code=status.HTTP_201_CREATED)
def create_timesheet(
    payload: TimesheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Timesheet).filter(
        Timesheet.user_id == current_user.id,
        Timesheet.year == payload.year,
        Timesheet.month == payload.month,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Timesheet per questo mese già esistente")

    ts = Timesheet(
        user_id=current_user.id,
        year=payload.year,
        month=payload.month,
        notes=payload.notes,
    )
    db.add(ts)
    db.commit()
    db.refresh(ts)
    return ts


@router.get("/{ts_id}", response_model=TimesheetRead)
def get_timesheet(
    ts_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ts = _get_timesheet_or_404(ts_id, db)
    # Verifica accesso
    if current_user.role == UserRole.EMPLOYEE and ts.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accesso negato")
    return ts


@router.patch("/{ts_id}", response_model=TimesheetRead)
def update_timesheet(
    ts_id: int,
    payload: TimesheetUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ts = _get_timesheet_or_404(ts_id, db)
    if ts.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Non puoi modificare il timesheet di un altro utente")
    if ts.status not in (TimesheetStatus.DRAFT, TimesheetStatus.REJECTED):
        raise HTTPException(status_code=400, detail="Solo i timesheet in bozza o rifiutati possono essere modificati")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(ts, field, value)
    db.commit()
    db.refresh(ts)
    return ts


# ── Entries ───────────────────────────────────────────────────────────────────

@router.put("/{ts_id}/entries", response_model=TimesheetRead)
def upsert_entries(
    ts_id: int,
    entries: list[TimesheetEntryCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sostituisce tutte le entries del timesheet.
    Usato dal frontend quando salva l'intera griglia mensile.
    """
    ts = _get_timesheet_or_404(ts_id, db)
    if ts.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accesso negato")
    if ts.status not in (TimesheetStatus.DRAFT, TimesheetStatus.REJECTED):
        raise HTTPException(status_code=400, detail="Timesheet non modificabile")

    non_zero_entries = [e for e in entries if e.hours > 0]
    if non_zero_entries:
        entry_dates = {e.entry_date for e in non_zero_entries}

        # 1) Festività: bloccate SEMPRE
        holiday_rows = db.query(Holiday).filter(
            Holiday.organization_id == current_user.organization_id,
            Holiday.holiday_date.in_(list(entry_dates)),
        ).all()
        holiday_dates = {h.holiday_date for h in holiday_rows}

        # 2) Weekend: accettato solo se autorizzato (e solo se NON è festività)
        weekend_dates = {d for d in entry_dates if d.weekday() in (5, 6)}  # 5=Sab, 6=Dom (Python)
        auth_rows = []
        auth_dates = set()
        if weekend_dates:
            auth_rows = db.query(WeekendAuthorization).filter(
                WeekendAuthorization.organization_id == current_user.organization_id,
                WeekendAuthorization.user_id == current_user.id,
                WeekendAuthorization.auth_date.in_(list(weekend_dates)),
            ).all()
            auth_dates = {a.auth_date for a in auth_rows}

        for e in non_zero_entries:
            if e.entry_date in holiday_dates:
                raise HTTPException(
                    status_code=400,
                    detail=f"Festività bloccata per il {e.entry_date.isoformat()}",
                )
            if e.entry_date in weekend_dates and e.entry_date not in auth_dates:
                raise HTTPException(
                    status_code=403,
                    detail=f"Weekend non autorizzato per il {e.entry_date.isoformat()}",
                )

    # Cancella le entries esistenti e reinserisci
    db.query(TimesheetEntry).filter(TimesheetEntry.timesheet_id == ts_id).delete()

    for e in entries:
        if e.hours > 0:  # ignora righe vuote
            entry = TimesheetEntry(
                timesheet_id=ts_id,
                project_id=e.project_id,
                entry_date=e.entry_date,
                hours=e.hours,
                notes=e.notes,
            )
            db.add(entry)

    db.commit()
    return _get_timesheet_or_404(ts_id, db)


# ── Workflow ──────────────────────────────────────────────────────────────────

@router.post("/{ts_id}/submit", response_model=TimesheetRead)
def submit_timesheet(
    ts_id: int,
    payload: TimesheetSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ts = _get_timesheet_or_404(ts_id, db)
    if ts.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Accesso negato")
    if ts.status not in (TimesheetStatus.DRAFT, TimesheetStatus.REJECTED):
        raise HTTPException(status_code=400, detail="Solo bozze o rifiutati possono essere inviati")
    if not ts.entries:
        raise HTTPException(status_code=400, detail="Non puoi inviare un timesheet vuoto")

    ts.status = TimesheetStatus.SUBMITTED
    ts.submitted_at = datetime.now(timezone.utc)
    if payload.notes:
        ts.notes = payload.notes
    db.commit()
    db.refresh(ts)
    return ts


@router.post("/{ts_id}/review", response_model=TimesheetRead)
def review_timesheet(
    ts_id: int,
    payload: TimesheetReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    ts = _get_timesheet_or_404(ts_id, db)
    if ts.status != TimesheetStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="Solo i timesheet inviati possono essere revisionati")

    ts.status = TimesheetStatus.APPROVED if payload.approved else TimesheetStatus.REJECTED
    ts.reviewed_at = datetime.now(timezone.utc)
    ts.reviewed_by_id = current_user.id
    ts.rejection_note = payload.rejection_note if not payload.approved else None
    db.commit()
    db.refresh(ts)
    return ts
