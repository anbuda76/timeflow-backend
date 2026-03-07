from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.models.models import (
    Timesheet, TimesheetEntry, TimesheetStatus,
    User, UserRole, Project
)
from app.core.deps import require_manager
router = APIRouter(prefix="/reports", tags=["reports"])

@router.get("/costs")
def monthly_costs(
    year: int = Query(...),
    month: int | None = Query(None),
    project_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    q = (
        db.query(
            TimesheetEntry.project_id,
            User.id.label("user_id"),
            User.first_name,
            User.last_name,
            User.hourly_rate,
            func.sum(TimesheetEntry.hours).label("total_hours"),
        )
        .join(Timesheet, TimesheetEntry.timesheet_id == Timesheet.id)
        .join(User, Timesheet.user_id == User.id)
        .filter(
            Timesheet.year == year,
            Timesheet.status == TimesheetStatus.APPROVED,
        )
    )

    if month:
        q = q.filter(Timesheet.month == month)
    if project_id:
        q = q.filter(TimesheetEntry.project_id == project_id)
    if current_user.role != UserRole.SUPER_ADMIN:
        q = q.filter(User.organization_id == current_user.organization_id)
    if current_user.role == UserRole.MANAGER:
        team_ids = [u.id for u in db.query(User).filter(User.manager_id == current_user.id).all()]
        team_ids.append(current_user.id)
        q = q.filter(User.id.in_(team_ids))

    rows = q.group_by(
        TimesheetEntry.project_id, User.id,
        User.first_name, User.last_name, User.hourly_rate
    ).all()

    by_project = {}
    by_user = {}
    total_hours = 0.0
    total_cost = 0.0

    for row in rows:
        rate = row.hourly_rate or 0.0
        cost = row.total_hours * rate
        total_hours += row.total_hours
        total_cost += cost

        project = db.get(Project, row.project_id)
        p_name = project.name if project else f"Progetto #{row.project_id}"
        c_name = project.client_name if project else None
        b_hours = project.budget_hours if project else None

        if row.project_id not in by_project:
            by_project[row.project_id] = {
                "project_id": row.project_id,
                "project_name": p_name,
                "client_name": c_name,
                "budget_hours": b_hours,
                "hours": 0.0,
                "cost": 0.0,
            }
        by_project[row.project_id]["hours"] += row.total_hours
        by_project[row.project_id]["cost"] += cost

        if row.user_id not in by_user:
            by_user[row.user_id] = {
                "user_id": row.user_id,
                "user_name": f"{row.first_name} {row.last_name}",
                "hourly_rate": rate,
                "hours": 0.0,
                "cost": 0.0,
            }
        by_user[row.user_id]["hours"] += row.total_hours
        by_user[row.user_id]["cost"] += cost

    return {
        "year": year,
        "month": month,
        "total_hours": round(total_hours, 2),
        "total_cost": round(total_cost, 2),
        "projects": list(by_project.values()),
        "users": list(by_user.values()),
    }