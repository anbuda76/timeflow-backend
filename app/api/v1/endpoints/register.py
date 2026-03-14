from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import Organization, User, UserRole, Project
from app.schemas.schemas import RegisterRequest, RegisterResponse
from app.core.security import hash_password
import re

router = APIRouter(prefix="/register", tags=["register"])

SYSTEM_PROJECTS = [
    {"name": "FERIE", "client_name": None},
    {"name": "PERMESSI", "client_name": None},
    {"name": "MALATTIA", "client_name": None},
    {"name": "STRAORDINARI", "client_name": None},
]

def slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug

def create_system_projects(db: Session, org_id: int):
    for p in SYSTEM_PROJECTS:
        project = Project(
            organization_id=org_id,
            name=p["name"],
            client_name=p["client_name"],
            is_active=True,
            is_system=True,
        )
        db.add(project)

@router.post("/", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register_organization(
    data: RegisterRequest,
    db: Session = Depends(get_db),
):
    # Controlla se email già esistente
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email già registrata"
        )

    # Genera slug univoco
    base_slug = slugify(data.company_name)
    slug = base_slug
    counter = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1

    # Crea organizzazione
    org = Organization(
        name=data.company_name,
        slug=slug,
        plan="free",
        subscription_plan="free",
        max_users=10,
        is_active=True,
        primary_color="#1d4ed8",
    )
    db.add(org)
    db.flush()

    # Crea utente admin
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)

    # Crea progetti di sistema
    create_system_projects(db, org.id)

    db.commit()
    db.refresh(org)
    db.refresh(user)
    return RegisterResponse(organization=org, user=user)

@router.post("/init-system-projects", status_code=status.HTTP_200_OK)
def init_system_projects_for_all(
    db: Session = Depends(get_db),
):
    """Crea i progetti di sistema per tutte le organizzazioni che non li hanno ancora."""
    orgs = db.query(Organization).all()
    created_count = 0
    for org in orgs:
        for p in SYSTEM_PROJECTS:
            existing = db.query(Project).filter(
                Project.organization_id == org.id,
                Project.name == p["name"],
                Project.is_system == True,
            ).first()
            if not existing:
                project = Project(
                    organization_id=org.id,
                    name=p["name"],
                    client_name=None,
                    is_active=True,
                    is_system=True,
                )
                db.add(project)
                created_count += 1
    db.commit()
    return {"message": f"Creati {created_count} progetti di sistema"}