"""Request and response models."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ClaimCreate(BaseModel):
    category_code: str
    expense_date: date
    amount: float = Field(gt=0, le=100_000)
    merchant: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=3, max_length=500)
    attendees: str | None = Field(default=None, max_length=500)
    has_receipt: bool = False


class Claim(BaseModel):
    id: int
    employee_id: int
    employee_name: str
    category_code: str
    category_name: str
    expense_date: date
    amount: float
    currency: str
    merchant: str
    description: str
    attendees: str | None
    has_receipt: bool
    status: str
    policy_flags: list[str]
    ai_review: dict | None
    created_at: str
    submitted_at: str | None


class Decision(BaseModel):
    decision: Literal["approved", "rejected"]
    comment: str | None = Field(default=None, max_length=500)


class Employee(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    department: str
    manager_id: int | None


class Category(BaseModel):
    code: str
    name: str
    limit_per_claim: float
    monthly_limit: float | None
    receipt_required_over: float
    requires_attendees: bool
