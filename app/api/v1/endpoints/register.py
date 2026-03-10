from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.models import Organization, User, UserRole
from app.schemas.schemas import RegisterRequest, RegisterResponse
from app.core.security import get_password_hash
import re

router = APIRouter(prefix="/register", tags=["register"])

def slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    return slug

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
    db.flush()  # ottieni l'id senza committare

    # Crea utente admin
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        first_name=data.first_name,
        last_name=data.last_name,
        role=UserRole.ADMIN,
        organization_id=org.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(org)
    db.refresh(user)

    return RegisterResponse(organization=org, user=user)