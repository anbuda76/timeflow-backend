from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date
from pydantic import BaseModel
from app.db.session import get_db
from app.models.models import Vendor, VendorCost, Project, User
from app.core.deps import require_manager

router = APIRouter(prefix="/vendors", tags=["vendors"])


# ── Schemas inline ────────────────────────────────────────────────────────────

class VendorIn(BaseModel):
    name: str
    tax_id: Optional[str] = None
    category: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = True

class VendorCostIn(BaseModel):
    vendor_id: int
    project_id: int
    amount: float
    cost_date: Optional[date] = None
    description: Optional[str] = None
    category: Optional[str] = None


# ── Vendors CRUD ──────────────────────────────────────────────────────────────

@router.get("/")
def list_vendors(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    vendors = db.query(Vendor).filter(
        Vendor.organization_id == current_user.organization_id
    ).order_by(Vendor.name).all()
    return [
        {
            "id": v.id,
            "name": v.name,
            "tax_id": v.tax_id,
            "category": v.category,
            "contact_email": v.contact_email,
            "contact_phone": v.contact_phone,
            "notes": v.notes,
            "is_active": v.is_active,
            "created_at": v.created_at,
        }
        for v in vendors
    ]


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_vendor(
    body: VendorIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    v = Vendor(
        organization_id=current_user.organization_id,
        name=body.name,
        tax_id=body.tax_id,
        category=body.category,
        contact_email=body.contact_email,
        contact_phone=body.contact_phone,
        notes=body.notes,
        is_active=body.is_active if body.is_active is not None else True,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    return {"id": v.id, "name": v.name, "is_active": v.is_active}


@router.put("/{vendor_id}")
def update_vendor(
    vendor_id: int,
    body: VendorIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    v = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.organization_id == current_user.organization_id,
    ).first()
    if not v:
        raise HTTPException(status_code=404, detail="Fornitore non trovato")
    v.name = body.name
    v.tax_id = body.tax_id
    v.category = body.category
    v.contact_email = body.contact_email
    v.contact_phone = body.contact_phone
    v.notes = body.notes
    if body.is_active is not None:
        v.is_active = body.is_active
    db.commit()
    db.refresh(v)
    return {"id": v.id, "name": v.name, "is_active": v.is_active}


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor(
    vendor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    v = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.organization_id == current_user.organization_id,
    ).first()
    if not v:
        raise HTTPException(status_code=404, detail="Fornitore non trovato")
    # Soft delete — disattiva invece di eliminare se ha costi associati
    has_costs = db.query(VendorCost).filter(VendorCost.vendor_id == vendor_id).first()
    if has_costs:
        v.is_active = False
        db.commit()
    else:
        db.delete(v)
        db.commit()


# ── VendorCosts CRUD ──────────────────────────────────────────────────────────

@router.get("/costs")
def list_vendor_costs(
    project_id: Optional[int] = Query(None),
    vendor_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    q = db.query(VendorCost).filter(
        VendorCost.organization_id == current_user.organization_id
    )
    if project_id:
        q = q.filter(VendorCost.project_id == project_id)
    if vendor_id:
        q = q.filter(VendorCost.vendor_id == vendor_id)
    if year:
        from sqlalchemy import extract
        q = q.filter(extract("year", VendorCost.cost_date) == year)
    costs = q.order_by(VendorCost.cost_date.desc().nullslast(), VendorCost.id.desc()).all()

    vendor_map = {v.id: v.name for v in db.query(Vendor).filter(
        Vendor.organization_id == current_user.organization_id
    ).all()}
    project_map = {p.id: p.name for p in db.query(Project).filter(
        Project.organization_id == current_user.organization_id
    ).all()}

    return [
        {
            "id": c.id,
            "vendor_id": c.vendor_id,
            "vendor_name": vendor_map.get(c.vendor_id, "—"),
            "project_id": c.project_id,
            "project_name": project_map.get(c.project_id, "—"),
            "amount": c.amount,
            "cost_date": c.cost_date,
            "description": c.description,
            "category": c.category,
            "created_at": c.created_at,
        }
        for c in costs
    ]


@router.post("/costs", status_code=status.HTTP_201_CREATED)
def create_vendor_cost(
    body: VendorCostIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    # Verifica vendor e progetto appartengono all'org
    vendor = db.query(Vendor).filter(
        Vendor.id == body.vendor_id,
        Vendor.organization_id == current_user.organization_id,
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Fornitore non trovato")

    project = db.query(Project).filter(
        Project.id == body.project_id,
        Project.organization_id == current_user.organization_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    c = VendorCost(
        organization_id=current_user.organization_id,
        vendor_id=body.vendor_id,
        project_id=body.project_id,
        amount=body.amount,
        cost_date=body.cost_date,
        description=body.description,
        category=body.category,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return {"id": c.id, "amount": c.amount}


@router.put("/costs/{cost_id}")
def update_vendor_cost(
    cost_id: int,
    body: VendorCostIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    c = db.query(VendorCost).filter(
        VendorCost.id == cost_id,
        VendorCost.organization_id == current_user.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Costo non trovato")
    c.vendor_id = body.vendor_id
    c.project_id = body.project_id
    c.amount = body.amount
    c.cost_date = body.cost_date
    c.description = body.description
    c.category = body.category
    db.commit()
    db.refresh(c)
    return {"id": c.id, "amount": c.amount}


@router.delete("/costs/{cost_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vendor_cost(
    cost_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager),
):
    c = db.query(VendorCost).filter(
        VendorCost.id == cost_id,
        VendorCost.organization_id == current_user.organization_id,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Costo non trovato")
    db.delete(c)
    db.commit()
