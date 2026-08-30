from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class CustomerCreate(BaseModel):
    email: str = Field(..., description="Unique email address for the customer")
    name: Optional[str] = Field(None, description="Display name of the customer")


class SubscriptionResponse(BaseModel):
    id: str
    plan_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime

    class Config:
        from_attributes = True


class CustomerResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    created_at: datetime
    subscriptions: list[SubscriptionResponse] = []

    class Config:
        from_attributes = True


class CustomerCreateResponse(BaseModel):
    id: str
    email: str
    name: Optional[str]
    api_key: str
    created_at: datetime

    class Config:
        from_attributes = True


class PlanResponse(BaseModel):
    id: str
    name: str
    monthly_quota: int
    price_cents: int

    class Config:
        from_attributes = True


class UsageCreate(BaseModel):
    endpoint: str = Field(..., min_length=1, description="The billable action/endpoint name")
    units: int = Field(default=1, ge=1, description="Number of capacity units consumed")


class UsageResponse(BaseModel):
    status: str
    message: str
    idempotency_key: str
    units: int

    class Config:
        from_attributes = True
