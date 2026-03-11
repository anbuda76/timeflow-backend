from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import Organization, User, UserRole
from app.core.security import hash_password
from app.core.deps import require_super_admin, get_current_user
from app.schemas.schemas import OrganizationCreate, OrganizationUpdate, OrganizationRead
import re

router = APIRouter(prefix="/organizations", tags=["organizations"])

def _make_slug(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug[:100]

@router.get("/", response_model=list[OrganizationRead])
def list_organizations(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    return db.query(Organization).order_by(Organization.created_at.desc()).all()

@router.post("/", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    slug = _make_slug(payload.name)
    if db.query(Organization).filter(Organization.slug == slug).first():
        raise HTTPException(status_code=400, detail=f"Slug '{slug}' già in uso")
    org = Organization(
        name=payload.name,
        slug=slug,
        plan=payload.plan,
        subscription_plan="free",
        max_users=10,
        is_active=True,
        primary_color="#1d4ed8",
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org

@router.get("/me", response_model=OrganizationRead)
def get_my_organization(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = db.get(Organization, current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organizzazione non trovata")
    return org

@router.patch("/me", response_model=OrganizationRead)
def update_my_organization(
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Non autorizzato")
    org = db.get(Organization, current_user.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organizzazione non trovata")
    # Admin può modificare solo logo e colore, non piano o max_users
    allowed_fields = {"logo_url", "primary_color", "name"}
    if current_user.role == UserRole.SUPER_ADMIN:
        allowed_fields = None  # super admin può modificare tutto
    data = payload.model_dump(exclude_none=True)
    for field, value in data.items():
        if allowed_fields is None or field in allowed_fields:
            setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return org

@router.get("/{org_id}", response_model=OrganizationRead)
def get_organization(
    org_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organizzazione non trovata")
    return org

@router.patch("/{org_id}", response_model=OrganizationRead)
def update_organization(
    org_id: int,
    payload: OrganizationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organizzazione non trovata")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return org