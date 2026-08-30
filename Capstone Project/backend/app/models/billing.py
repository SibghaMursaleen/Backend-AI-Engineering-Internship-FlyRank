import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.session import Base

class Plan(Base):
    __tablename__ = "plans"

    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    monthly_quota = Column(Integer, nullable=False)
    price_cents = Column(Integer, nullable=False)

    subscriptions = relationship("Subscription", back_populates="plan")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True)
    api_key = Column(String(100), unique=True, index=True, nullable=False)
    stripe_customer_id = Column(String(255), unique=True, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False)

    subscriptions = relationship("Subscription", back_populates="customer", cascade="all, delete-orphan")
    usage_events = relationship("UsageEvent", back_populates="customer", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="customer", cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(36), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(String(50), ForeignKey("plans.id"), nullable=False)
    status = Column(String(50), default="active", nullable=False)  # active, trialing, past_due, canceled
    stripe_subscription_id = Column(String(255), unique=True, nullable=True)
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)

    customer = relationship("Customer", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(36), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    endpoint = Column(String(255), nullable=False)
    units = Column(Integer, default=1, nullable=False)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False, index=True)

    customer = relationship("Customer", back_populates="usage_events")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id = Column(String(36), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    total_cost_cents = Column(Integer, nullable=False)
    status = Column(String(50), default="draft", nullable=False)  # draft, paid, void, unpaid

    customer = relationship("Customer", back_populates="invoices")
