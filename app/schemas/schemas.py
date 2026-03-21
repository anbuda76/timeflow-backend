"""
Pydantic Schemas — TimeFlow
============================
Separati in: Base (campi comuni) / Create (input) / Update / Read (output con id).
"""
from pydantic import BaseModel, EmailStr, Field, model_validator
from datetime import datetime, date
from typing import Optional
from app.models.models import UserRole, TimesheetStatus, HolidayType


# ── Organization ──────────────────────────────────────────────────────────────

class OrganizationBase(BaseModel):
    name: str
    slug: str
    plan: str = "free"

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    subscription_plan: str | None = None
    max_users: int | None = None
    is_active: bool | None = None

class OrganizationRead(BaseModel):
    id: int
    name: str
    slug: str
    plan: str
    is_active: bool
    created_at: datetime
    logo_url: str | None = None
    primary_color: str | None = None
    subscription_plan: str = "free"
    max_users: int = 10

    model_config = {"from_attributes": True}


# ── User ──────────────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    email: EmailStr
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    role: UserRole = UserRole.EMPLOYEE
    hourly_rate: Optional[float] = Field(None, ge=0)
    manager_id: Optional[int] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    hourly_rate: Optional[float] = Field(None, ge=0)
    manager_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class UserRead(UserBase):
    id: int
    organization_id: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserReadBrief(BaseModel):
    """Versione compatta per embed in altri schema."""
    id: int
    full_name: str
    email: str
    role: UserRole

    model_config = {"from_attributes": True}


class RegisterRequest(BaseModel):
    company_name: str
    first_name: str
    last_name: str
    email: EmailStr
    password: str = Field(min_length=8)

class RegisterResponse(BaseModel):
    organization: OrganizationRead
    user: UserRead


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserRead


class RefreshRequest(BaseModel):
    refresh_token: str


# ── Project ───────────────────────────────────────────────────────────────────

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    client_name: Optional[str] = None
    budget_hours: Optional[float] = Field(None, ge=0)
    budget_amount: Optional[float] = Field(None, ge=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    client_name: Optional[str] = None
    budget_hours: Optional[float] = Field(None, ge=0)
    budget_amount: Optional[float] = Field(None, ge=0)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None

class AssignmentRead(BaseModel):
    user_id: int
    model_config = {"from_attributes": True}

class ProjectRead(ProjectBase):
    id: int
    organization_id: int
    is_active: bool
    is_system: bool = False
    created_at: datetime
    used_hours: Optional[float] = None
    assignments: list[AssignmentRead] = []

    model_config = {"from_attributes": True}

# ── Timesheet ─────────────────────────────────────────────────────────────────

class TimesheetEntryBase(BaseModel):
    project_id: int
    entry_date: date
    hours: float = Field(..., ge=0, le=24)
    notes: Optional[str] = None


class TimesheetEntryCreate(TimesheetEntryBase):
    pass


class TimesheetEntryRead(TimesheetEntryBase):
    id: int
    timesheet_id: int

    model_config = {"from_attributes": True}


class TimesheetBase(BaseModel):
    year: int = Field(..., ge=2020, le=2100)
    month: int = Field(..., ge=1, le=12)
    notes: Optional[str] = None


class TimesheetCreate(TimesheetBase):
    pass


class TimesheetUpdate(BaseModel):
    notes: Optional[str] = None


class TimesheetSubmit(BaseModel):
    notes: Optional[str] = None


class TimesheetReview(BaseModel):
    approved: bool
    rejection_note: Optional[str] = None

    @model_validator(mode="after")
    def note_required_if_rejected(self):
        if not self.approved and not self.rejection_note:
            raise ValueError("rejection_note è obbligatorio quando si rifiuta")
        return self


class TimesheetRead(TimesheetBase):
    id: int
    user_id: int
    status: TimesheetStatus
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by_id: Optional[int] = None
    rejection_note: Optional[str] = None
    total_hours: float = 0
    entries: list[TimesheetEntryRead] = []

    model_config = {"from_attributes": True}


class TimesheetReadBrief(TimesheetBase):
    """Senza entries — per liste e dashboard."""
    id: int
    user_id: int
    status: TimesheetStatus
    total_hours: float = 0

    model_config = {"from_attributes": True}


# ── Holiday ───────────────────────────────────────────────────────────────────

class HolidayBase(BaseModel):
    holiday_date: date
    label: str = Field(..., min_length=1, max_length=200)
    type: HolidayType = HolidayType.NATIONAL


class HolidayCreate(HolidayBase):
    pass


class HolidayRead(HolidayBase):
    id: int
    organization_id: int

    model_config = {"from_attributes": True}


# ── Report / Stats ────────────────────────────────────────────────────────────

class ProjectCostRead(BaseModel):
    project_id: int
    project_name: str
    total_hours: float
    total_cost: float


class MonthlyCostRead(BaseModel):
    year: int
    month: int
    total_hours: float
    total_cost: float
    avg_hourly_rate: float
    by_project: list[ProjectCostRead]
    by_user: list[dict]