from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.core.redis import redis_client
from app.models.billing import Customer, Subscription, Plan, UsageEvent, Invoice
from app.services.billing import calculate_usage_cost

# Initialize BackgroundScheduler
scheduler = BackgroundScheduler()

def reset_rebuild_redis_counters():
    """
    Job 1: Rebuild and align Redis usage counters for all active subscriptions.
    Guarantees Redis is kept in sync with the database.
    """
    print("Running Job 1: Rebuilding Redis usage counters...")
    db = SessionLocal()
    try:
        active_subs = db.query(Subscription).filter(Subscription.status == "active").all()
        for sub in active_subs:
            # Key formatting matches endpoint logic
            redis_key = f"usage:{sub.customer_id}:{sub.current_period_start.year}-{sub.current_period_start.month:02d}"
            
            # Fetch total consumed units inside PostgreSQL for the current period
            total_units = db.query(func.sum(UsageEvent.units)).filter(
                UsageEvent.customer_id == sub.customer_id,
                UsageEvent.created_at >= sub.current_period_start,
                UsageEvent.created_at <= sub.current_period_end
            ).scalar() or 0
            
            # Save value to Redis with 30 days expiration (2592000 seconds)
            redis_client.set(redis_key, total_units, ex=2592000)
            print(f"Rebuilt counter for Customer {sub.customer_id}: {total_units} units")
    except Exception as e:
        print(f"Error executing Job 1 (reset_rebuild_redis_counters): {e}")
    finally:
        db.close()


def generate_invoices():
    """
    Job 2: Generates draft invoice records for expired customer subscriptions.
    Includes idempotency checks to prevent duplicate invoice records.
    """
    print("Running Job 2: Generating invoices...")
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Find active subscriptions whose period has ended
        expired_subs = db.query(Subscription).filter(
            Subscription.status == "active",
            Subscription.current_period_end <= now
        ).all()
        
        for sub in expired_subs:
            # 1. Idempotency Check: check if invoice already generated for this exact period
            existing_invoice = db.query(Invoice).filter(
                Invoice.customer_id == sub.customer_id,
                Invoice.period_start == sub.current_period_start,
                Invoice.period_end == sub.current_period_end
            ).first()
            
            if existing_invoice:
                print(f"Invoice already generated for Customer {sub.customer_id} in period {sub.current_period_start} to {sub.current_period_end}. Skipping.")
                continue
                
            # 2. Get customer's plan
            plan = db.query(Plan).filter(Plan.id == sub.plan_id).first()
            if not plan:
                print(f"Error: plan configuration not found for subscription {sub.id}")
                continue
                
            # 3. Calculate usage and cost
            total_units, cost_cents = calculate_usage_cost(
                db=db,
                customer_id=sub.customer_id,
                start_date=sub.current_period_start,
                end_date=sub.current_period_end,
                plan=plan
            )
            
            # 4. Generate Invoice record
            invoice = Invoice(
                customer_id=sub.customer_id,
                period_start=sub.current_period_start,
                period_end=sub.current_period_end,
                total_cost_cents=cost_cents,
                status="draft"
            )
            db.add(invoice)
            
            # 5. Roll forward subscription period for the next billing cycle
            sub.current_period_start = sub.current_period_end
            sub.current_period_end = sub.current_period_end + timedelta(days=30)
            
            db.commit()
            print(f"Generated Invoice {invoice.id} for Customer {sub.customer_id}: Total Cost: {cost_cents} cents (${cost_cents/100:.2f})")
    except Exception as e:
        print(f"Error executing Job 2 (generate_invoices): {e}")
        db.rollback()
    finally:
        db.close()


# Configure periodic scheduler jobs
# Job 1 runs daily to keep cache fresh
scheduler.add_job(reset_rebuild_redis_counters, 'interval', days=1, id='rebuild_counters_job')
# Job 2 runs daily to invoice expired subscriptions
scheduler.add_job(generate_invoices, 'interval', days=1, id='generate_invoices_job')
