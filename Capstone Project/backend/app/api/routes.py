import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.db.session import get_db
from app.core.config import settings
from app.core.redis import redis_client
from app.models.billing import Customer, Subscription, Plan, UsageEvent, Invoice
from app.schemas.billing import (
    CustomerCreate,
    CustomerResponse,
    CustomerCreateResponse,
    PlanResponse,
    UsageCreate,
    UsageResponse,
)
from app.api.auth import get_current_customer
from app.services.billing import calculate_usage_cost
import stripe
from fastapi import Request

stripe.api_key = settings.STRIPE_API_KEY

router = APIRouter()

# --- Health check endpoint ---
@router.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    health_status = {
        "status": "healthy",
        "database": "disconnected",
        "redis": "disconnected"
    }
    
    # 1. Verify PostgreSQL connection
    try:
        db.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["database"] = f"error: {str(e)}"
        
    # 2. Verify Redis connection
    try:
        if redis_client.ping():
            health_status["redis"] = "connected"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["redis"] = f"error: {str(e)}"
        
    return health_status


# --- Customer endpoints ---
@router.post(
    "/v1/customers",
    response_model=CustomerCreateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Customers"]
)
def create_customer(payload: CustomerCreate, db: Session = Depends(get_db)):
    # Check if email is already taken
    existing = db.query(Customer).filter(Customer.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )
        
    # Generate unique Bearer API key
    api_key = f"sk_live_{secrets.token_hex(24)}"
    
    # Create customer record
    customer = Customer(
        email=payload.email,
        name=payload.name,
        api_key=api_key
    )
    db.add(customer)
    db.flush()  # Populate customer.id
    
    # Setup default 30-day Free subscription
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    subscription = Subscription(
        customer_id=customer.id,
        plan_id="free",
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=30)
    )
    db.add(subscription)
    db.commit()
    db.refresh(customer)
    
    return customer


@router.get(
    "/v1/customers/me",
    response_model=CustomerResponse,
    tags=["Customers"]
)
def get_my_profile(customer: Customer = Depends(get_current_customer)):
    return customer


# --- Plans endpoints ---
@router.get(
    "/v1/plans",
    response_model=list[PlanResponse],
    tags=["Plans"]
)
def list_plans(db: Session = Depends(get_db)):
    plans = db.query(Plan).all()
    return plans


# --- Usage Metering endpoint ---
@router.post(
    "/v1/usage",
    response_model=UsageResponse,
    tags=["Metering"]
)
def log_usage(
    payload: UsageCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    # Resolve or generate idempotency key
    key = idempotency_key or str(uuid.uuid4())
    
    # Check if duplicate request is sent with the same key for this customer
    existing_event = db.query(UsageEvent).filter(
        UsageEvent.customer_id == customer.id,
        UsageEvent.idempotency_key == key
    ).first()
    
    if existing_event:
        return UsageResponse(
            status="success",
            message="Duplicate request handled idempotently.",
            idempotency_key=key,
            units=existing_event.units
        )
        
    # Fetch active subscription and plan details
    sub = db.query(Subscription).filter(
        Subscription.customer_id == customer.id,
        Subscription.status == "active"
    ).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No active subscription found for customer."
        )
        
    plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Active plan details not found."
        )

    # Define Redis counter key for this billing period
    # Key formatting: usage:{customer_id}:{period_year}-{period_month} based on subscription start date
    redis_key = f"usage:{customer.id}:{sub.current_period_start.year}-{sub.current_period_start.month:02d}"

    # Check if counter exists in Redis cache
    redis_count_str = redis_client.get(redis_key)
    
    if redis_count_str is None:
        # Cache miss: Rebuild the Redis counter from usage events in database
        total_units = db.query(func.sum(UsageEvent.units)).filter(
            UsageEvent.customer_id == customer.id,
            UsageEvent.created_at >= sub.current_period_start,
            UsageEvent.created_at <= sub.current_period_end
        ).scalar() or 0
        
        # Populate Redis with database state and set 30 days expiration (2592000 seconds)
        redis_client.set(redis_key, total_units, ex=2592000)
        current_count = total_units
    else:
        current_count = int(redis_count_str)

    # Enforce quota limits
    if current_count + payload.units > plan.monthly_quota:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Usage quota exceeded. Used: {current_count}/{plan.monthly_quota} units. Limit breached by adding {payload.units} units."
        )

    # Insert new usage event
    event = UsageEvent(
        customer_id=customer.id,
        endpoint=payload.endpoint,
        units=payload.units,
        idempotency_key=key
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    
    # Increment Redis counter
    redis_client.incrby(redis_key, payload.units)
    
    return UsageResponse(
        status="success",
        message="Usage logged successfully.",
        idempotency_key=key,
        units=event.units
    )


# --- Usage Reporting endpoints ---
@router.get(
    "/v1/usage/summary",
    tags=["Reporting"]
)
def get_usage_summary(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    # Fetch active subscription and plan
    sub = db.query(Subscription).filter(
        Subscription.customer_id == customer.id,
        Subscription.status == "active"
    ).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found."
        )
        
    plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan details not found."
        )

    # Calculate total usage and estimated billing cost
    total_units, cost_cents = calculate_usage_cost(
        db=db,
        customer_id=customer.id,
        start_date=sub.current_period_start,
        end_date=sub.current_period_end,
        plan=plan
    )

    percentage_used = round(min(100.0, (total_units / plan.monthly_quota) * 100.0), 2)

    return {
        "plan_id": plan.id,
        "plan_name": plan.name,
        "monthly_quota": plan.monthly_quota,
        "units_used": total_units,
        "percentage_used": percentage_used,
        "estimated_cost_cents": cost_cents,
        "current_period_start": sub.current_period_start,
        "current_period_end": sub.current_period_end
    }


@router.get(
    "/v1/usage/history",
    tags=["Reporting"]
)
def get_usage_history(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    # Fetch active subscription
    sub = db.query(Subscription).filter(
        Subscription.customer_id == customer.id,
        Subscription.status == "active"
    ).first()
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found."
        )

    # Fetch all usage events in current billing period
    events = db.query(UsageEvent).filter(
        UsageEvent.customer_id == customer.id,
        UsageEvent.created_at >= sub.current_period_start,
        UsageEvent.created_at <= sub.current_period_end
    ).order_by(UsageEvent.created_at.asc()).all()

    # Time-series grouping in Python (Database-agnostic: works transparently on SQLite/PostgreSQL)
    daily_usage = {}
    
    # Initialize all dates from subscription start up to current date with 0 units
    start_date = sub.current_period_start.date()
    end_date = sub.current_period_end.date()
    now_date = datetime.now(timezone.utc).replace(tzinfo=None).date()
    
    max_init_date = min(end_date, now_date)
    
    current_date = start_date
    while current_date <= max_init_date:
        daily_usage[current_date.isoformat()] = 0
        current_date += timedelta(days=1)

    # Accumulate usage units per day
    for event in events:
        event_date_str = event.created_at.date().isoformat()
        if event_date_str in daily_usage:
            daily_usage[event_date_str] += event.units
        else:
            daily_usage[event_date_str] = event.units

    # Format output suitable for frontend graphing
    history = [{"date": k, "units": v} for k, v in sorted(daily_usage.items())]
    return history


# --- Stripe Payment Integration endpoints ---
@router.post(
    "/v1/billing/downgrade",
    tags=["Billing"]
)
def downgrade_to_free(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    sub = db.query(Subscription).filter(
        Subscription.customer_id == customer.id,
        Subscription.status == "active"
    ).first()
    if sub:
        sub.plan_id = "free"
        db.commit()
    return {"status": "success"}


@router.post(
    "/v1/billing/checkout",
    tags=["Billing"]
)
def create_checkout_session(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    # Check if running with placeholder Stripe keys
    if settings.STRIPE_API_KEY == "sk_test_placeholder" or not settings.STRIPE_API_KEY.startswith("sk_test"):
        # Sandbox/Mock upgrade mode: Upgrade customer subscription to Pro directly for local testing
        sub = db.query(Subscription).filter(
            Subscription.customer_id == customer.id,
            Subscription.status == "active"
        ).first()
        if sub:
            sub.plan_id = "pro"
            db.commit()
        return {"checkout_url": "mock-checkout"}

    try:
        # Create checkout session (Stripe Test Mode)
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "Pro Plan Subscription",
                            "description": "Unlock 50,000 monthly usage units and lower overage fees."
                        },
                        "unit_amount": 2900,  # $29.00 in cents
                        "recurring": {
                            "interval": "month"
                        }
                    },
                    "quantity": 1
                }
            ],
            mode="subscription",
            success_url="http://localhost:3000/billing?success=true",
            cancel_url="http://localhost:3000/billing?cancel=true",
            client_reference_id=customer.id,
            customer_email=customer.email
        )
        return {"checkout_url": checkout_session.url}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stripe session creation failed: {str(e)}"
        )


@router.post(
    "/v1/webhooks/stripe",
    tags=["Billing"]
)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    
    if not sig_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe-Signature Header"
        )

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload"
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature"
        )

    event_type = event["type"]
    event_object = event["data"]["object"]

    if event_type == "checkout.session.completed":
        customer_id = event_object.get("client_reference_id")
        stripe_customer_id = event_object.get("customer")
        stripe_subscription_id = event_object.get("subscription")

        if not customer_id:
            return {"status": "ignored", "reason": "client_reference_id absent"}

        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            return {"status": "error", "reason": "customer not found"}

        # Store Stripe Customer ID
        customer.stripe_customer_id = stripe_customer_id

        # Update Subscription record to Pro
        subscription = db.query(Subscription).filter(
            Subscription.customer_id == customer.id,
            Subscription.status == "active"
        ).first()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        start_date = now
        end_date = now + timedelta(days=30)

        # If Stripe subscription metadata is available, we load current period timestamps
        if stripe_subscription_id:
            try:
                sub_detail = stripe.Subscription.retrieve(stripe_subscription_id)
                start_date = datetime.fromtimestamp(sub_detail.current_period_start, tz=timezone.utc).replace(tzinfo=None)
                end_date = datetime.fromtimestamp(sub_detail.current_period_end, tz=timezone.utc).replace(tzinfo=None)
            except Exception:
                pass  # Fallback to local 30-day default if API call fails in test/offline modes

        if subscription:
            subscription.plan_id = "pro"
            subscription.stripe_subscription_id = stripe_subscription_id
            subscription.current_period_start = start_date
            subscription.current_period_end = end_date
        else:
            subscription = Subscription(
                customer_id=customer.id,
                plan_id="pro",
                status="active",
                stripe_subscription_id=stripe_subscription_id,
                current_period_start=start_date,
                current_period_end=end_date
            )
            db.add(subscription)

        db.commit()
        print(f"Customer {customer.email} upgraded to Pro. Subscription: {stripe_subscription_id}")

    elif event_type == "customer.subscription.updated":
        stripe_sub_id = event_object.get("id")
        status_str = event_object.get("status")

        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()

        if subscription:
            if status_str in ["canceled", "unpaid"]:
                subscription.status = "canceled"
                # Downgrade plan back to free
                subscription.plan_id = "free"
                subscription.stripe_subscription_id = None
            else:
                subscription.status = status_str
                
            try:
                subscription.current_period_start = datetime.fromtimestamp(event_object.get("current_period_start"), tz=timezone.utc).replace(tzinfo=None)
                subscription.current_period_end = datetime.fromtimestamp(event_object.get("current_period_end"), tz=timezone.utc).replace(tzinfo=None)
            except Exception:
                pass

            db.commit()
            print(f"Subscription {stripe_sub_id} updated locally: status={subscription.status}, plan={subscription.plan_id}")

    elif event_type == "customer.subscription.deleted":
        stripe_sub_id = event_object.get("id")
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_sub_id
        ).first()

        if subscription:
            # Downgrade back to Free plan
            subscription.plan_id = "free"
            subscription.status = "active"  # Active free status
            subscription.stripe_subscription_id = None
            
            # Reset period window to 30 days
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            subscription.current_period_start = now
            subscription.current_period_end = now + timedelta(days=30)
            
            db.commit()
            print(f"Subscription {stripe_sub_id} deleted. Downgraded customer to Free Plan.")

    return {"status": "success"}


@router.get(
    "/v1/invoices",
    tags=["Billing"]
)
def list_invoices(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db)
):
    invoices = db.query(Invoice).filter(Invoice.customer_id == customer.id).order_by(Invoice.period_start.desc()).all()
    return invoices
