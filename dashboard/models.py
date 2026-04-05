"""
Pydantic models for request validation on all POST/PUT endpoints.

Every user-facing mutation goes through these models. No raw dict access.
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


# --- Projects ---

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    tech_stack: str = Field(default="", max_length=500)
    path: str = Field(default="", max_length=500)
    revenue_monthly: float = Field(default=0, ge=0, le=10_000_000)


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    status: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None, max_length=2000)
    tech_stack: Optional[str] = Field(default=None, max_length=500)
    revenue_monthly: Optional[float] = Field(default=None, ge=0, le=10_000_000)
    path: Optional[str] = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in ("active", "paused", "completed", "archived"):
            raise ValueError("status must be active, paused, completed, or archived")
        return v


# --- Tasks ---

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    priority: str = Field(default="medium")
    due_date: Optional[str] = Field(default=None, max_length=20)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if v not in ("low", "medium", "high", "critical"):
            raise ValueError("priority must be low, medium, high, or critical")
        return v


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    status: Optional[str] = Field(default=None)
    priority: Optional[str] = Field(default=None)
    due_date: Optional[str] = Field(default=None, max_length=20)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in ("pending", "in_progress", "done", "cancelled"):
            raise ValueError("status must be pending, in_progress, done, or cancelled")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if v is not None and v not in ("low", "medium", "high", "critical"):
            raise ValueError("priority must be low, medium, high, or critical")
        return v


# --- Finances ---

class FinanceCreate(BaseModel):
    date: str = Field(..., min_length=8, max_length=20)
    amount: float = Field(..., ge=-10_000_000, le=10_000_000)
    category: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=2000)
    type: str = Field(default="expense")
    source: str = Field(default="", max_length=200)
    recurring: bool = Field(default=False)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in ("expense", "revenue", "investment", "transfer"):
            raise ValueError("type must be expense, revenue, investment, or transfer")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v):
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("date must be YYYY-MM-DD format")
        return v


# --- Goals ---

class GoalCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    target_date: Optional[str] = Field(default=None, max_length=20)
    category: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=5000)


class GoalUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=500)
    target_date: Optional[str] = Field(default=None, max_length=20)
    progress: Optional[float] = Field(default=None, ge=0, le=100)
    category: Optional[str] = Field(default=None, max_length=200)
    notes: Optional[str] = Field(default=None, max_length=5000)
    status: Optional[str] = Field(default=None)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in ("active", "completed", "abandoned"):
            raise ValueError("status must be active, completed, or abandoned")
        return v


# --- Feedback ---

class FeedbackSubmit(BaseModel):
    message_id: int = Field(...)
    session_id: str = Field(default="")
    rating: int = Field(...)

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v):
        if v not in (1, -1):
            raise ValueError("rating must be 1 (up) or -1 (down)")
        return v


# --- Knowledge Learning ---

class LearnContent(BaseModel):
    content: str = Field(..., min_length=50, max_length=50000)
    domain: str = Field(default="learned", max_length=100)
    title: str = Field(default="Conversation Insight", max_length=500)


# --- Chat Session ---

class ChatSessionCreate(BaseModel):
    title: str = Field(default="New Chat", max_length=200)
    domain: Optional[str] = Field(default=None, max_length=100)
    model: str = Field(default="haiku", max_length=50)
