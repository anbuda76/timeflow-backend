from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import Organization, User, UserRole
from app.core.security import hash_password
from app.core.deps import require_super_admin
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
    slug = payload.slug or _make_slug(payload.name)
    if db.query(Organization).filter(Organization.slug == slug).first():
        raise HTTPException(status_code=400, detail=f"Slug '{slug}' già in uso")

    org = Organization(name=payload.name, slug=slug, plan=payload.plan)
    db.add(org)
    db.flush()

    admin = User(
        organization_id=org.id,
        email=payload.admin_email.lower(),
        hashed_password=hash_password(payload.admin_password),
        first_name=payload.admin_first_name,
        last_name=payload.admin_last_name,
        role=UserRole.ADMIN,
    )
    db.add(admin)
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