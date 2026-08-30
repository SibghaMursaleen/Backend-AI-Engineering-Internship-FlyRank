from datetime import datetime
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.billing import UsageEvent, Plan

def calculate_usage_cost(db: Session, customer_id: str, start_date: datetime, end_date: datetime, plan: Plan):
    """
    Calculates total units consumed and estimated billing cost in cents for a customer.
    Free Plan: Flat $0.00, overage fee of 5 cents ($0.05) per unit.
    Pro Plan: Flat $29.00 (2900 cents), overage fee of 1 cent ($0.01) per unit.
    """
    # Sum the units consumed in the given billing period
    total_units = db.query(func.sum(UsageEvent.units)).filter(
        UsageEvent.customer_id == customer_id,
        UsageEvent.created_at >= start_date,
        UsageEvent.created_at <= end_date
    ).scalar() or 0
    
    # Calculate overage units
    overage = max(0, total_units - plan.monthly_quota)
    
    # Determine overage fee per unit (cents)
    overage_rate = 5 if plan.id == "free" else 1
    
    total_cost_cents = plan.price_cents + (overage * overage_rate)
    
    return total_units, total_cost_cents
