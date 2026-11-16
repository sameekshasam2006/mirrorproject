from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    password_confirm: str = Field(..., min_length=8)
    display_name: str = Field(..., min_length=2)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPreferencesUpdate(BaseModel):
    available_hours: str | None = None
    preferred_planning_style: str | None = None
    reminder_minutes: int | None = None
    theme: str | None = None
    working_hours: str | None = None
    goals: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    display_name: str
    time_zone: str


class UserPreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    available_hours: str
    preferred_planning_style: str
    reminder_minutes: int
    theme: str
    working_hours: str
    goals: str | None = None


class TaskBase(BaseModel):
    title: str = Field(..., min_length=2)
    description: str | None = None
    category: str = "General"
    priority: str = "medium"
    status: str = "not_started"
    start_time: datetime | None = None
    due_date: datetime | None = None
    estimated_duration: int = Field(default=60, ge=15, le=480)
    actual_duration: int | None = Field(default=None, ge=15, le=480)

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str):
        allowed = {"low", "medium", "high", "critical"}
        if value.lower() not in allowed:
            raise ValueError("Priority must be low, medium, high, or critical")
        return value.lower()

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str):
        allowed = {"not_started", "in_progress", "completed"}
        if value.lower() not in allowed:
            raise ValueError("Status must be not_started, in_progress, or completed")
        return value.lower()


class TaskCreate(TaskBase):
    pass


class TaskUpdate(TaskBase):
    title: str | None = Field(default=None, min_length=2)
    description: str | None = None
    category: str | None = None
    priority: str | None = None
    status: str | None = None
    start_time: datetime | None = None
    due_date: datetime | None = None
    estimated_duration: int | None = Field(default=None, ge=15, le=480)
    actual_duration: int | None = Field(default=None, ge=15, le=480)


class TaskOut(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class SimulationInput(BaseModel):
    task_id: int
    scenario_type: Literal["skip", "postpone", "move", "extend", "priority"]
    new_time: datetime | None = None
    new_duration: int | None = Field(default=None, ge=15, le=480)
    new_priority: str | None = None
    move_to_date: datetime | None = None

    @field_validator("new_priority")
    @classmethod
    def validate_new_priority(cls, value: str | None):
        if value is not None and value.lower() not in {"low", "medium", "high", "critical"}:
            raise ValueError("Priority must be low, medium, high, or critical")
        return value.lower() if value is not None else None

    @model_validator(mode="after")
    def validate_scenario_parameters(self):
        if self.scenario_type == "move" and self.new_time is None and self.move_to_date is None:
            raise ValueError("Move requires a new time or date")
        if self.scenario_type == "move" and self.new_time is not None and self.move_to_date is not None:
            raise ValueError("Provide either a new time or a new date, not both")
        if self.scenario_type == "extend" and self.new_duration is None:
            raise ValueError("Extend requires a new duration")
        if self.scenario_type == "priority" and self.new_priority is None:
            raise ValueError("Priority change requires a new priority")
        return self


class SimulationApprovalInput(BaseModel):
    alternative_id: int | None = None


class SimulationAlternativeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    proposed_schedule: dict[str, Any]
    benefits: str | None = None
    drawbacks: str | None = None
    feasibility_result: str


class SimulationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    scenario_type: str
    original_snapshot: dict[str, Any]
    proposed_snapshot: dict[str, Any]
    impact_analysis: dict[str, Any]
    feasibility_result: str
    status: str
    created_at: datetime
    updated_at: datetime
    alternatives: list[SimulationAlternativeOut] = Field(default_factory=list)


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int | None = None
    message: str
    scheduled_time: datetime | None = None
    sent_time: datetime | None = None
    read_at: datetime | None = None
    delivery_status: str
    created_at: datetime


class AnalyticsSummary(BaseModel):
    total_tasks: int
    completed_tasks: int
    pending_tasks: int
    overdue_tasks: int
    workload_by_day: list[dict[str, Any]]
    priority_distribution: dict[str, int]
    weekly_trend: list[dict[str, Any]]
