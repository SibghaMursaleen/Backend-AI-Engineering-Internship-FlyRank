from datetime import datetime, timedelta, timezone
from app.models import Subscription, Invoice, UsageEvent
from app.jobs.scheduler import reset_rebuild_redis_counters, generate_invoices

def test_job_rebuild_counters(client, db_session, mock_redis):
    # Create customer
    customer = client.post("/v1/customers", json={"email": "job_rebuild@example.com"}).json()
    headers = {"Authorization": f"Bearer {customer['api_key']}"}
    
    # Log usage (under free quota)
    client.post("/v1/usage", json={"endpoint": "api_call", "units": 350}, headers=headers)
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    redis_key = f"usage:{customer['id']}:{now.year}-{now.month:02d}"
    assert mock_redis.get(redis_key) == "350"
    
    # Simulate cache miss
    mock_redis.flushall()
    assert mock_redis.get(redis_key) is None
    
    # Trigger Job 1: Rebuild counters
    reset_rebuild_redis_counters()
    
    # Verify Redis counter successfully rebuilt from Postgres records
    assert mock_redis.get(redis_key) == "350"


def test_job_generate_invoices_idempotency(client, db_session):
    # Create customer
    customer = client.post("/v1/customers", json={"email": "job_invoice@example.com"}).json()
    
    # Fetch active subscription
    sub = db_session.query(Subscription).filter_by(customer_id=customer["id"], status="active").first()
    original_start = sub.current_period_start
    original_end = sub.current_period_end
    
    # 1. Shift billing period dates back 30 days so the period is fully completed/expired
    sub.current_period_start = original_start - timedelta(days=30)
    sub.current_period_end = original_start  # Expired at original_start (which is now)
    db_session.commit()
    
    # 2. Insert over-quota usage (1200 units) directly to the database with a date inside the expired period
    event = UsageEvent(
        customer_id=customer["id"],
        endpoint="api_call",
        units=1200,
        idempotency_key="idemp_invoice_test",
        created_at=sub.current_period_start + timedelta(days=1)
    )
    db_session.add(event)
    db_session.commit()
    
    # Run Invoicing Job
    generate_invoices()
    
    # Verify invoice generated with correct amount (200 units overage * 5 cents = 1000 cents)
    invoice = db_session.query(Invoice).filter_by(customer_id=customer["id"]).first()
    assert invoice is not None
    assert invoice.total_cost_cents == 1000  # $10.00
    assert invoice.status == "draft"
    
    # Verify subscription rolled forward
    db_session.refresh(sub)
    assert sub.current_period_start == original_start  # Rolled forward to original_start
    assert sub.current_period_end == original_start + timedelta(days=30)
    
    # 3. Simulate another job run on the same period to test idempotency
    # Revert dates back to the expired range
    sub.current_period_start = original_start - timedelta(days=30)
    sub.current_period_end = original_start
    db_session.commit()
    
    # Run Invoicing Job again
    generate_invoices()
    
    # Check that duplicate invoice was NOT created
    invoice_count = db_session.query(Invoice).filter_by(customer_id=customer["id"]).count()
    assert invoice_count == 1
