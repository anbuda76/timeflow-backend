"""
Modelli SQLAlchemy — TimeFlow
==============================
Struttura multi-tenant: ogni tabella principale ha tenant_id (organization_id)
per isolare completamente i dati tra organizzazioni diverse.
"""
import enum
from datetime import datetime, date, timezone
from sqlalchemy import (
    String, Integer, Float, Boolean, Date, DateTime,
    ForeignKey, Enum as SAEnum, Text, UniqueConstraint, func, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    EMPLOYEE = "employee"


class ContractType(str, enum.Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"


class TimesheetStatus(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class HolidayType(str, enum.Enum):
    NATIONAL = "national"
    COMPANY = "company"


# ── Organization (Tenant) ─────────────────────────────────────────────────────

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    plan: Mapped[str] = mapped_column(String(50), default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
    
	DateTime(timezone=True),server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    # Campi multi-tenant
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True, default="#1d4ed8")
    subscription_plan: Mapped[str] = mapped_column(String(50), default="free")
    max_users: Mapped[int] = mapped_column(default=10)

    # Relationships
    users: Mapped[list["User"]] = relationship(back_populates="organization")
    projects: Mapped[list["Project"]] = relationship(back_populates="organization")
    holidays: Mapped[list["Holiday"]] = relationship(back_populates="organization")


# ── User ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.EMPLOYEE)
    contract_type: Mapped[ContractType] = mapped_column(SAEnum(ContractType), default=ContractType.FULL_TIME)
    hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    manager_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_user_org_email"),
        Index("ix_user_org", "organization_id"),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="users")
    manager: Mapped["User | None"] = relationship("User", remote_side="User.id", foreign_keys=[manager_id])
    timesheets: Mapped[list["Timesheet"]] = relationship(back_populates="user", foreign_keys="[Timesheet.user_id]", cascade="all, delete-orphan")
    project_assignments: Mapped[list["ProjectAssignment"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self):
        return f"<User {self.email} [{self.role}]>"


# ── Project ───────────────────────────────────────────────────────────────────

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    client_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (Index("ix_project_org", "organization_id"),)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="projects")
    assignments: Mapped[list["ProjectAssignment"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    entries: Mapped[list["TimesheetEntry"]] = relationship(back_populates="project")

    def __repr__(self):
        return f"<Project {self.name}>"


# ── ProjectAssignment ─────────────────────────────────────────────────────────

class ProjectAssignment(Base):
    __tablename__ = "project_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_assignment"),
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="assignments")
    user: Mapped["User"] = relationship(back_populates="project_assignments")


# ── Timesheet ─────────────────────────────────────────────────────────────────

class Timesheet(Base):
    __tablename__ = "timesheets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TimesheetStatus] = mapped_column(
        SAEnum(TimesheetStatus), default=TimesheetStatus.DRAFT
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejection_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "year", "month", name="uq_timesheet_user_month"),
        Index("ix_timesheet_user", "user_id"),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", foreign_keys="[Timesheet.user_id]", back_populates="timesheets")
    reviewed_by: Mapped["User | None"] = relationship("User", foreign_keys="[Timesheet.reviewed_by_id]")
    entries: Mapped[list["TimesheetEntry"]] = relationship(back_populates="timesheet", cascade="all, delete-orphan")

    @property
    def total_hours(self) -> float:
        return sum(e.hours for e in self.entries)

    def __repr__(self):
        return f"<Timesheet user={self.user_id} {self.year}/{self.month} [{self.status}]>"


# ── TimesheetEntry ────────────────────────────────────────────────────────────

class TimesheetEntry(Base):
    __tablename__ = "timesheet_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timesheet_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("timesheets.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours: Mapped[float] = mapped_column(Float, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("timesheet_id", "project_id", "entry_date", name="uq_entry"),
        Index("ix_entry_timesheet", "timesheet_id"),
        Index("ix_entry_date", "entry_date"),
    )

    # Relationships
    timesheet: Mapped["Timesheet"] = relationship(back_populates="entries")
    project: Mapped["Project"] = relationship(back_populates="entries")

    def __repr__(self):
        return f"<Entry {self.entry_date} {self.hours}h proj={self.project_id}>"


# ── Holiday ───────────────────────────────────────────────────────────────────

class Holiday(Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[HolidayType] = mapped_column(SAEnum(HolidayType), default=HolidayType.NATIONAL)

    __table_args__ = (
        UniqueConstraint("organization_id", "holiday_date", name="uq_holiday_org_date"),
        Index("ix_holiday_org", "organization_id"),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="holidays")

    def __repr__(self):
        return f"<Holiday {self.holiday_date} — {self.label}>"

# ── WeekendAuthorization ──────────────────────────────────────────────────────

class WeekendAuthorization(Base):
    """Autorizzazione per lavorare in un giorno di weekend."""
    __tablename__ = "weekend_authorizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    authorized_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    auth_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("user_id", "auth_date", name="uq_weekend_auth"),
        Index("ix_weekend_auth_org", "organization_id"),
    )