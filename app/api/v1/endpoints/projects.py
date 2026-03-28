from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.models.models import Project, ProjectAssignment, TimesheetEntry, User, UserRole
from app.core.deps import get_current_user, require_admin, same_org_or_admin
from app.schemas.schemas import ProjectCreate, ProjectUpdate, ProjectRead

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=list[ProjectRead])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.SUPER_ADMIN:
        projects = db.query(Project).order_by(Project.id.desc()).all()
    elif current_user.role == UserRole.EMPLOYEE:
        assigned_ids = [
            a.project_id for a in db.query(ProjectAssignment)
            .filter(ProjectAssignment.user_id == current_user.id).all()
        ]
        projects = db.query(Project).filter(
            Project.organization_id == current_user.organization_id
        ).filter(
            (Project.id.in_(assigned_ids)) | (Project.is_system.is_(True))
        ).order_by(Project.id.desc()).all()
    else:
        projects = db.query(Project).filter(
            Project.organization_id == current_user.organization_id
        ).order_by(Project.id.desc()).all()

    result = []
    for p in projects:
        used = db.query(func.sum(TimesheetEntry.hours)).filter(
            TimesheetEntry.project_id == p.id
        ).scalar() or 0.0
        pr = ProjectRead.model_validate(p)
        pr.used_hours = used
        result.append(pr)
    return result


@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    project = Project(
        organization_id=current_user.organization_id,
        **payload.model_dump(),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    pr = ProjectRead.model_validate(project)
    pr.used_hours = 0.0
    return pr


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    same_org_or_admin(project.organization_id, current_user)
    used = db.query(func.sum(TimesheetEntry.hours)).filter(
        TimesheetEntry.project_id == project_id
    ).scalar() or 0.0
    pr = ProjectRead.model_validate(project)
    pr.used_hours = used
    return pr


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    same_org_or_admin(project.organization_id, current_user)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    pr = ProjectRead.model_validate(project)
    pr.used_hours = 0.0
    return pr


@router.post("/{project_id}/assign/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def assign_user(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    if current_user.role != UserRole.SUPER_ADMIN:
        same_org_or_admin(project.organization_id, current_user)

    existing = db.query(ProjectAssignment).filter(
        ProjectAssignment.project_id == project_id,
        ProjectAssignment.user_id == user_id,
    ).first()
    if existing:
        return

    db.add(ProjectAssignment(project_id=project_id, user_id=user_id))
    db.commit()


@router.delete("/{project_id}/assign/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def unassign_user(
    project_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if current_user.role != UserRole.SUPER_ADMIN:
        project = db.get(Project, project_id)
        if project:
            same_org_or_admin(project.organization_id, current_user)
    db.query(ProjectAssignment).filter(
        ProjectAssignment.project_id == project_id,
        ProjectAssignment.user_id == user_id,
    ).delete()
    db.commit()


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")
    same_org_or_admin(project.organization_id, current_user)

    if project.entries:
        raise HTTPException(
            status_code=400,
            detail="Non è possibile eliminare il progetto perché ha ore caricate"
        )

    db.delete(project)
    db.commit()